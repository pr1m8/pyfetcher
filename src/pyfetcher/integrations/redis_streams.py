"""Redis Streams implementation of the portable at-least-once job queue.

Consumer groups provide leasing, acknowledgement, and stale-message recovery.
Delayed retries use a sorted set and a small atomic Lua promotion step. Queue
messages remain compact because large content is represented by BlobRef values.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pyfetcher.jobs.models import JobRequest
from pyfetcher.jobs.queue import JobLease, QueueStats

_PROMOTE_DUE = """
local values = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[2])
local promoted = 0
for _, member in ipairs(values) do
  if redis.call('ZREM', KEYS[1], member) == 1 then
    local value = cjson.decode(member)
    redis.call('XADD', KEYS[2], '*', 'job', value['job'])
    promoted = promoted + 1
  end
end
return promoted
"""


def _decode(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


class RedisStreamJobQueue:
    """Redis Streams queue with consumer groups and stale lease reclamation.

    Delivery is at-least-once. A crash between a side effect and acknowledgement
    can redeliver a job, so templates should use ``JobRequest.idempotency_key``
    when performing externally visible writes.
    """

    def __init__(
        self,
        redis: object,
        *,
        stream: str = "fetchkit:jobs",
        group: str = "fetchkit",
        dead_stream: str | None = None,
        scheduled_set: str | None = None,
        dedup_ttl_seconds: int = 86_400,
        owns_client: bool = False,
    ) -> None:
        self._redis = redis
        self._stream = stream
        self._group = group
        self._dead_stream = dead_stream or f"{stream}:dead"
        self._scheduled_set = scheduled_set or f"{stream}:scheduled"
        self._dedup_ttl_seconds = dedup_ttl_seconds
        self._owns_client = owns_client
        self._initialized = False
        self._completed = 0
        self._retried = 0
        self._dead = 0

    @classmethod
    def from_url(cls, url: str, **kwargs: object) -> RedisStreamJobQueue:
        """Create an owned async Redis client from a connection URL."""
        try:
            from redis.asyncio import Redis
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Redis queue support requires `pip install 'fetchkit[redis]'`"
            ) from exc
        return cls(Redis.from_url(url), owns_client=True, **kwargs)

    async def _initialize(self) -> None:
        if self._initialized:
            return
        try:
            await self._redis.xgroup_create(  # type: ignore[union-attr]
                self._stream,
                self._group,
                id="0-0",
                mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        self._initialized = True

    def _dedup_key(self, value: str) -> str:
        digest = hashlib.sha256(value.encode()).hexdigest()
        return f"{self._stream}:dedup:{digest}"

    async def enqueue(self, job: JobRequest) -> bool:
        await self._initialize()
        if job.idempotency_key is not None:
            accepted = await self._redis.set(  # type: ignore[union-attr]
                self._dedup_key(job.idempotency_key),
                str(job.id),
                ex=self._dedup_ttl_seconds,
                nx=True,
            )
            if not accepted:
                return False
        try:
            await self._redis.xadd(  # type: ignore[union-attr]
                self._stream,
                {"job": job.model_dump_json()},
            )
        except BaseException:
            if job.idempotency_key is not None:
                await self._redis.delete(  # type: ignore[union-attr]
                    self._dedup_key(job.idempotency_key)
                )
            raise
        return True

    async def _promote_due(self) -> None:
        await self._redis.eval(  # type: ignore[union-attr]
            _PROMOTE_DUE,
            2,
            self._scheduled_set,
            self._stream,
            datetime.now(UTC).timestamp(),
            100,
        )

    @staticmethod
    def _message(value: object) -> tuple[str, dict[object, object]] | None:
        if not value:
            return None
        streams = value
        if (
            isinstance(streams, (list, tuple))
            and len(streams) >= 2
            and isinstance(streams[1], list)
            and not isinstance(streams[0], tuple)
        ):
            streams = streams[1]
        if not isinstance(streams, (list, tuple)) or not streams:
            return None
        first = streams[0]
        if isinstance(first, tuple) and len(first) == 2 and isinstance(first[1], list):
            messages = first[1]
            if not messages:
                return None
            first = messages[0]
        if not isinstance(first, tuple) or len(first) != 2:
            return None
        message_id, fields = first
        return _decode(message_id), dict(fields)

    async def reserve(
        self,
        consumer: str,
        *,
        timeout_seconds: float | None = None,
        lease_seconds: float = 60.0,
    ) -> JobLease | None:
        await self._initialize()
        await self._promote_due()
        reclaimed = await self._redis.xautoclaim(  # type: ignore[union-attr]
            self._stream,
            self._group,
            consumer,
            min_idle_time=max(1, int(lease_seconds * 1_000)),
            start_id="0-0",
            count=1,
        )
        message = self._message(reclaimed)
        if message is None:
            block = 0 if timeout_seconds is None else max(1, int(timeout_seconds * 1_000))
            received = await self._redis.xreadgroup(  # type: ignore[union-attr]
                self._group,
                consumer,
                {self._stream: ">"},
                count=1,
                block=block,
            )
            message = self._message(received)
        if message is None:
            return None
        message_id, fields = message
        raw = fields.get("job", fields.get(b"job"))
        if raw is None:
            raise ValueError(f"Redis stream message {message_id} has no job field")
        now = datetime.now(UTC)
        return JobLease(
            message_id=message_id,
            job=JobRequest.model_validate_json(_decode(raw)),
            consumer=consumer,
            leased_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )

    async def _complete(self, lease: JobLease) -> None:
        await self._redis.xack(self._stream, self._group, lease.message_id)  # type: ignore[union-attr]
        await self._redis.xdel(self._stream, lease.message_id)  # type: ignore[union-attr]

    async def acknowledge(self, lease: JobLease) -> None:
        await self._complete(lease)
        self._completed += 1

    async def retry(self, lease: JobLease, *, delay_seconds: float = 0) -> None:
        job_json = lease.job.next_attempt().model_dump_json()
        if delay_seconds > 0:
            member = json.dumps(
                {"token": str(uuid4()), "job": job_json},
                separators=(",", ":"),
            )
            await self._redis.zadd(  # type: ignore[union-attr]
                self._scheduled_set,
                {member: datetime.now(UTC).timestamp() + delay_seconds},
            )
        else:
            await self._redis.xadd(self._stream, {"job": job_json})  # type: ignore[union-attr]
        await self._complete(lease)
        self._retried += 1

    async def reject(self, lease: JobLease, *, reason: str) -> None:
        await self._redis.xadd(  # type: ignore[union-attr]
            self._dead_stream,
            {
                "job": lease.job.model_dump_json(),
                "reason": reason,
                "source_message_id": lease.message_id,
            },
        )
        await self._complete(lease)
        self._dead += 1

    async def heartbeat(self, lease: JobLease, *, lease_seconds: float = 60.0) -> JobLease:
        claimed = await self._redis.xclaim(  # type: ignore[union-attr]
            self._stream,
            self._group,
            lease.consumer,
            min_idle_time=0,
            message_ids=[lease.message_id],
        )
        if not claimed:
            raise KeyError(f"unknown or completed Redis job lease: {lease.message_id}")
        return lease.model_copy(
            update={"lease_expires_at": datetime.now(UTC) + timedelta(seconds=lease_seconds)}
        )

    async def stats(self) -> QueueStats:
        await self._initialize()
        length = int(await self._redis.xlen(self._stream))  # type: ignore[union-attr]
        scheduled = int(await self._redis.zcard(self._scheduled_set))  # type: ignore[union-attr]
        pending_value: Any = await self._redis.xpending(  # type: ignore[union-attr]
            self._stream,
            self._group,
        )
        if isinstance(pending_value, dict):
            pending = int(pending_value.get("pending", 0))
        elif isinstance(pending_value, (list, tuple)) and pending_value:
            pending = int(pending_value[0])
        else:
            pending = 0
        return QueueStats(
            queued=max(0, length - pending) + scheduled,
            leased=pending,
            completed=self._completed,
            retried=self._retried,
            dead=self._dead,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._redis.aclose()  # type: ignore[union-attr]


__all__ = ["RedisStreamJobQueue"]
