"""End-to-end tests for the optional gRPC job control plane."""

from __future__ import annotations

import asyncio

import pytest

grpc = pytest.importorskip("grpc")
pytest.importorskip("google.protobuf")

from google.protobuf import empty_pb2, wrappers_pb2

from pyfetcher.integrations.grpc import create_job_grpc_server
from pyfetcher.jobs import (
    JobApplication,
    JobContext,
    JobRecord,
    JobRecordPage,
    JobRequest,
    JobResult,
    JobServiceHealth,
    JobSubmission,
    TemplateRef,
    TemplateRegistry,
    WorkerConfig,
    WorkerEvent,
)
from pyfetcher.protocol import JobLookupRequest, WorkerEventSubscription

_SERVICE = "fetchkit.jobs.v1.JobControlPlane"


class EchoTemplate:
    name = "test.grpc.echo"
    version = "1"

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        return JobResult.succeeded(job, output={"echo": job.payload.get("value")})


def _application() -> JobApplication:
    registry = TemplateRegistry()
    registry.register(EchoTemplate(), description="Echo one JSON value")  # type: ignore[arg-type]
    return JobApplication.create(
        registry=registry,
        worker_config=WorkerConfig(
            name="grpc-test-worker",
            concurrency=1,
            reserve_timeout_seconds=0.01,
            lease_seconds=0.2,
            heartbeat_seconds=0.01,
            error_backoff_seconds=0,
        ),
    )


def _unary(channel, method: str, *, empty: bool = False):
    return channel.unary_unary(
        f"/{_SERVICE}/{method}",
        request_serializer=(
            empty_pb2.Empty.SerializeToString
            if empty
            else wrappers_pb2.BytesValue.SerializeToString
        ),
        response_deserializer=wrappers_pb2.BytesValue.FromString,
    )


async def test_grpc_control_plane_submits_inspects_and_streams_events() -> None:
    server = create_job_grpc_server(_application(), address="127.0.0.1:0")
    async with server, grpc.aio.insecure_channel(f"127.0.0.1:{server.bound_port}") as channel:
        health_value = await _unary(channel, "Health", empty=True)(empty_pb2.Empty())
        health = JobServiceHealth.model_validate_json(health_value.value)
        assert health.status == "ok"

        job = JobRequest(
            template=TemplateRef(name="test.grpc.echo"),
            payload={"value": "hello"},
            idempotency_key="grpc-echo",
        )
        watch = channel.unary_stream(
            f"/{_SERVICE}/WatchEvents",
            request_serializer=wrappers_pb2.BytesValue.SerializeToString,
            response_deserializer=wrappers_pb2.BytesValue.FromString,
        )
        event_call = watch(
            wrappers_pb2.BytesValue(
                value=WorkerEventSubscription(job_id=job.id).model_dump_json().encode()
            )
        )
        first_event = asyncio.create_task(event_call.read())
        await asyncio.sleep(0)

        submit_call = _unary(channel, "Submit")(
            wrappers_pb2.BytesValue(value=job.model_dump_json().encode())
        )
        submitted_value = await submit_call
        submission = JobSubmission.model_validate_json(submitted_value.value)
        assert submission.accepted is True
        metadata = dict(await submit_call.initial_metadata())
        assert metadata["fetchkit-response-contract"] == "job.submission@1"

        event = WorkerEvent.model_validate_json((await first_event).value)
        assert event.job_id == job.id

        get_job = _unary(channel, "Get")
        lookup = wrappers_pb2.BytesValue(
            value=JobLookupRequest(job_id=job.id).model_dump_json().encode()
        )
        async with asyncio.timeout(2):
            while True:
                record_value = await get_job(lookup)
                record = JobRecord.model_validate_json(record_value.value)
                if record.status == "succeeded":
                    break
                await asyncio.sleep(0.005)
        assert record.result is not None
        assert record.result.output == {"echo": "hello"}

        page_value = await _unary(channel, "List")(
            wrappers_pb2.BytesValue(value=b'{"status":"succeeded"}')
        )
        page = JobRecordPage.model_validate_json(page_value.value)
        assert page.total == 1
        assert page.items[0].job.id == job.id
        event_call.cancel()


async def test_grpc_control_plane_maps_validation_and_missing_jobs() -> None:
    server = create_job_grpc_server(
        _application(),
        address="127.0.0.1:0",
        start_worker=False,
    )
    async with server, grpc.aio.insecure_channel(f"127.0.0.1:{server.bound_port}") as channel:
        with pytest.raises(grpc.aio.AioRpcError) as invalid:
            await _unary(channel, "List")(wrappers_pb2.BytesValue(value=b'{"limit":0}'))
        assert invalid.value.code() == grpc.StatusCode.INVALID_ARGUMENT

        missing = JobLookupRequest(job_id="00000000-0000-0000-0000-000000000001")
        with pytest.raises(grpc.aio.AioRpcError) as not_found:
            await _unary(channel, "Get")(
                wrappers_pb2.BytesValue(value=missing.model_dump_json().encode())
            )
        assert not_found.value.code() == grpc.StatusCode.NOT_FOUND
