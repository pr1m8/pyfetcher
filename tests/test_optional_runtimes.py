from __future__ import annotations

import pytest


def test_temporal_runtime_imports_with_pydantic_converter() -> None:
    pytest.importorskip("temporalio")
    from pyfetcher.integrations.temporal import (
        FetchkitFlowWorkflow,
        pydantic_data_converter,
    )

    assert FetchkitFlowWorkflow is not None
    assert pydantic_data_converter is not None


def test_redis_stream_message_shapes_are_decoded() -> None:
    pytest.importorskip("redis")
    from pyfetcher.integrations.redis_streams import RedisStreamJobQueue

    fields = {b"job": b"{}"}
    assert RedisStreamJobQueue._message([(b"jobs", [(b"1-0", fields)])]) == (
        "1-0",
        fields,
    )
    assert RedisStreamJobQueue._message([b"0-0", [(b"2-0", fields)], []]) == (
        "2-0",
        fields,
    )


def test_observability_hooks_import() -> None:
    pytest.importorskip("opentelemetry.sdk")
    from pyfetcher.telemetry import OpenTelemetryFetchMiddleware, OpenTelemetryJobHook

    assert OpenTelemetryFetchMiddleware() is not None
    assert OpenTelemetryJobHook() is not None
