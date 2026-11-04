"""Optional gRPC adapter for the durable-job control plane.

The adapter uses protobuf ``BytesValue`` frames containing UTF-8 JSON governed
by fetchkit's versioned JSON Schema catalog. This keeps Pydantic contracts as
the single domain-model source while giving Python and TypeScript systems a
standard gRPC transport and server-streaming worker events.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

try:
    import grpc
    from google.protobuf import empty_pb2, wrappers_pb2
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError("gRPC support requires `pip install 'fetchkit[grpc]'`") from exc

from pyfetcher.jobs import JobApplication, JobNotFoundError, JobRequest, WorkerEventBroker
from pyfetcher.protocol.rpc import (
    JOB_CONTROL_PLANE_SERVICE,
    JobListRequest,
    JobLookupRequest,
    TemplateCatalog,
    WorkerEventSubscription,
)


def _encode(value: BaseModel) -> wrappers_pb2.BytesValue:
    return wrappers_pb2.BytesValue(value=value.model_dump_json(by_alias=True).encode())


async def _decode[ModelT: BaseModel](
    request: wrappers_pb2.BytesValue,
    model: type[ModelT],
    context: grpc.aio.ServicerContext,
) -> ModelT:
    try:
        return model.model_validate_json(request.value)
    except (ValidationError, ValueError, UnicodeDecodeError) as exc:
        await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        raise AssertionError("gRPC abort returned unexpectedly") from exc


class _JobControlPlaneServicer:
    def __init__(self, application: JobApplication, broker: WorkerEventBroker) -> None:
        self._application = application
        self._broker = broker
        self._methods = {method.name: method for method in JOB_CONTROL_PLANE_SERVICE.methods}

    async def _announce(self, name: str, context: grpc.aio.ServicerContext) -> None:
        method = self._methods[name]
        await context.send_initial_metadata(
            (("fetchkit-response-contract", method.response_contract),)
        )

    async def submit(
        self,
        request: wrappers_pb2.BytesValue,
        context: grpc.aio.ServicerContext,
    ) -> wrappers_pb2.BytesValue:
        job = await _decode(request, JobRequest, context)
        await self._announce("Submit", context)
        return _encode(await self._application.service.submit(job))

    async def get(
        self,
        request: wrappers_pb2.BytesValue,
        context: grpc.aio.ServicerContext,
    ) -> wrappers_pb2.BytesValue:
        query = await _decode(request, JobLookupRequest, context)
        await self._announce("Get", context)
        try:
            return _encode(await self._application.service.get(query.job_id))
        except JobNotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, "job not found")
            raise AssertionError("gRPC abort returned unexpectedly") from exc

    async def list_jobs(
        self,
        request: wrappers_pb2.BytesValue,
        context: grpc.aio.ServicerContext,
    ) -> wrappers_pb2.BytesValue:
        query = await _decode(request, JobListRequest, context)
        await self._announce("List", context)
        page = await self._application.service.list_jobs(
            status=query.status,
            limit=query.limit,
            offset=query.offset,
        )
        return _encode(page)

    async def cancel(
        self,
        request: wrappers_pb2.BytesValue,
        context: grpc.aio.ServicerContext,
    ) -> wrappers_pb2.BytesValue:
        query = await _decode(request, JobLookupRequest, context)
        await self._announce("Cancel", context)
        try:
            return _encode(await self._application.service.cancel(query.job_id))
        except JobNotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, "job not found")
            raise AssertionError("gRPC abort returned unexpectedly") from exc

    async def health(
        self,
        request: empty_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> wrappers_pb2.BytesValue:
        await self._announce("Health", context)
        return _encode(await self._application.service.health())

    async def templates(
        self,
        request: empty_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> wrappers_pb2.BytesValue:
        await self._announce("Templates", context)
        return _encode(TemplateCatalog(items=self._application.service.templates()))

    async def worker(
        self,
        request: empty_pb2.Empty,
        context: grpc.aio.ServicerContext,
    ) -> wrappers_pb2.BytesValue:
        await self._announce("Worker", context)
        return _encode(self._application.worker.snapshot())

    async def watch_events(
        self,
        request: wrappers_pb2.BytesValue,
        context: grpc.aio.ServicerContext,
    ):
        subscription = await _decode(request, WorkerEventSubscription, context)
        await self._announce("WatchEvents", context)
        async for event in self._broker.subscribe(job_id=subscription.job_id):
            yield _encode(event)


def _add_job_control_plane(
    server: grpc.aio.Server,
    application: JobApplication,
    broker: WorkerEventBroker,
) -> None:
    servicer = _JobControlPlaneServicer(application, broker)
    bytes_deserializer = wrappers_pb2.BytesValue.FromString
    bytes_serializer = wrappers_pb2.BytesValue.SerializeToString
    empty_deserializer = empty_pb2.Empty.FromString
    methods = {
        "Submit": grpc.unary_unary_rpc_method_handler(
            servicer.submit,
            request_deserializer=bytes_deserializer,
            response_serializer=bytes_serializer,
        ),
        "Get": grpc.unary_unary_rpc_method_handler(
            servicer.get,
            request_deserializer=bytes_deserializer,
            response_serializer=bytes_serializer,
        ),
        "List": grpc.unary_unary_rpc_method_handler(
            servicer.list_jobs,
            request_deserializer=bytes_deserializer,
            response_serializer=bytes_serializer,
        ),
        "Cancel": grpc.unary_unary_rpc_method_handler(
            servicer.cancel,
            request_deserializer=bytes_deserializer,
            response_serializer=bytes_serializer,
        ),
        "Health": grpc.unary_unary_rpc_method_handler(
            servicer.health,
            request_deserializer=empty_deserializer,
            response_serializer=bytes_serializer,
        ),
        "Templates": grpc.unary_unary_rpc_method_handler(
            servicer.templates,
            request_deserializer=empty_deserializer,
            response_serializer=bytes_serializer,
        ),
        "Worker": grpc.unary_unary_rpc_method_handler(
            servicer.worker,
            request_deserializer=empty_deserializer,
            response_serializer=bytes_serializer,
        ),
        "WatchEvents": grpc.unary_stream_rpc_method_handler(
            servicer.watch_events,
            request_deserializer=bytes_deserializer,
            response_serializer=bytes_serializer,
        ),
    }
    server.add_generic_rpc_handlers(
        (grpc.method_handlers_generic_handler(JOB_CONTROL_PLANE_SERVICE.name, methods),)
    )


class JobGrpcServer:
    """Lifecycle owner for a gRPC server and its injected job application."""

    def __init__(
        self,
        application: JobApplication,
        *,
        address: str = "127.0.0.1:50051",
        credentials: grpc.ServerCredentials | None = None,
        start_worker: bool = True,
        event_broker: WorkerEventBroker | None = None,
        interceptors: Iterable[grpc.aio.ServerInterceptor] = (),
        options: Sequence[tuple[str, Any]] = (),
        maximum_concurrent_rpcs: int | None = None,
    ) -> None:
        self.application = application
        self.event_broker = event_broker or WorkerEventBroker()
        self.application.worker.add_event_sink(self.event_broker.publish)
        self.server = grpc.aio.server(
            interceptors=tuple(interceptors),
            options=tuple(options),
            maximum_concurrent_rpcs=maximum_concurrent_rpcs,
        )
        _add_job_control_plane(self.server, application, self.event_broker)
        self.bound_port = (
            self.server.add_insecure_port(address)
            if credentials is None
            else self.server.add_secure_port(address, credentials)
        )
        if self.bound_port == 0:
            raise ValueError(f"gRPC server could not bind to {address}")
        self._start_worker = start_worker
        self._started = False
        self._closed = False
        self._close_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the worker and gRPC listener once."""
        if self._closed:
            raise RuntimeError("gRPC job server is closed")
        if self._started:
            raise RuntimeError("gRPC job server is already running")
        if self._start_worker:
            await self.application.start()
        try:
            await self.server.start()
        except BaseException:
            await self.application.aclose()
            raise
        self._started = True

    async def wait_for_termination(self, timeout: float | None = None) -> bool:
        """Wait until the underlying gRPC server terminates."""
        if not self._started:
            raise RuntimeError("gRPC job server has not been started")
        return await self.server.wait_for_termination(timeout=timeout)

    async def aclose(self, *, grace: float | None = 5.0) -> None:
        """Stop accepting RPCs and close application-owned resources."""
        async with self._close_lock:
            if self._closed:
                return
            if self._started:
                await self.server.stop(grace)
            await self.application.aclose()
            self._closed = True

    async def __aenter__(self) -> JobGrpcServer:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


def create_job_grpc_server(
    application: JobApplication,
    **kwargs: Any,
) -> JobGrpcServer:
    """Create a lifecycle-aware gRPC adapter over one job application."""
    return JobGrpcServer(application, **kwargs)


__all__ = ["JobGrpcServer", "create_job_grpc_server"]
