"""Tests for the optional FastAPI durable-job adapter."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from pyfetcher.integrations.api import create_job_api
from pyfetcher.jobs import (
    JobApplication,
    JobContext,
    JobRequest,
    JobResult,
    TemplateRef,
    TemplateRegistry,
    WorkerConfig,
)


class EchoTemplate:
    name = "test.echo"
    version = "1"

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        return JobResult.succeeded(job, output={"echo": job.payload.get("value")})


def _application() -> JobApplication:
    registry = TemplateRegistry()
    registry.register(EchoTemplate(), description="Echo one JSON value")  # type: ignore[arg-type]
    return JobApplication.create(
        registry=registry,
        worker_config=WorkerConfig(
            name="api-test-worker",
            concurrency=1,
            reserve_timeout_seconds=0.01,
            lease_seconds=0.2,
            heartbeat_seconds=0.01,
            error_backoff_seconds=0,
        ),
    )


def test_job_api_submits_lists_and_inspects_jobs() -> None:
    job = JobRequest(
        template=TemplateRef(name="test.echo"),
        payload={"value": "hello"},
        idempotency_key="api-echo",
    )
    api = create_job_api(_application())

    with TestClient(api) as client:
        assert client.get("/health").json()["status"] == "ok"
        templates = client.get("/v1/templates").json()
        assert templates[0]["ref"] == {"name": "test.echo", "version": "1"}

        submitted = client.post("/v1/jobs", json=job.model_dump(mode="json"))
        assert submitted.status_code == 202
        assert submitted.json()["accepted"] is True

        duplicate = client.post("/v1/jobs", json=job.model_dump(mode="json"))
        assert duplicate.status_code == 202
        assert duplicate.json()["duplicate"] is True

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            record = client.get(f"/v1/jobs/{job.id}")
            if record.json()["status"] == "succeeded":
                break
            time.sleep(0.01)
        else:  # pragma: no cover - protects against a stalled test worker
            pytest.fail("job did not complete")

        assert record.json()["result"]["output"] == {"echo": "hello"}
        page = client.get("/v1/jobs", params={"status": "succeeded"}).json()
        assert page["total"] == 1
        assert page["items"][0]["job"]["id"] == str(job.id)
        assert client.get("/v1/worker").json()["status"] == "running"


def test_job_api_reports_missing_jobs_and_validates_filters() -> None:
    api = create_job_api(_application())

    with TestClient(api) as client:
        missing = "00000000-0000-0000-0000-000000000001"
        assert client.get(f"/v1/jobs/{missing}").status_code == 404
        assert client.post(f"/v1/jobs/{missing}/cancel").status_code == 404
        assert client.get("/v1/jobs", params={"status": "unknown"}).status_code == 422
