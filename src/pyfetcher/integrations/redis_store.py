"""Redis-backed durable job status and result storage.

Purpose:
    Persist queryable job state separately from Redis Streams delivery so API
    processes and workers share status, cancellation, and idempotency records.

Design:
    Records live in Redis hashes. Global and per-status sorted sets provide
    stable paging, while Lua transitions keep records and indexes consistent.
    The default prefix uses a Redis Cluster hash tag so every script key is in
    the same slot. Large response and media bytes still belong in a BlobStore.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from pyfetcher.jobs.models import JobRequest, JobResult
from pyfetcher.jobs.store import JobRecord, JobRecordStatus

_CREATE_RECORD = """
-- fetchkit:create-record
if redis.call('EXISTS', KEYS[1]) == 1 then
  return {0, ARGV[1]}
end
if ARGV[13] ~= '' then
  local existing = redis.call('HGET', KEYS[9], ARGV[13])
  if existing then
    return {0, existing}
  end
end
redis.call('HSET', KEYS[1],
  'job', ARGV[2],
  'status', ARGV[3],
  'result', ARGV[4],
  'worker_id', ARGV[5],
  'delivery_count', ARGV[6],
  'cancel_requested', ARGV[7],
  'created_at', ARGV[8],
  'updated_at', ARGV[9],
  'started_at', ARGV[10],
  'completed_at', ARGV[11],
  'created_score', ARGV[12],
  'idempotency_hash', ARGV[13])
redis.call('ZADD', KEYS[2], ARGV[12], ARGV[1])
redis.call('ZADD', KEYS[3], ARGV[12], ARGV[1])
if ARGV[13] ~= '' then
  redis.call('HSET', KEYS[9], ARGV[13], ARGV[1])
end
return {1, ARGV[1]}
"""

_STATUS_KEY_FUNCTION = """
local function status_key(value)
  if value == 'queued' then return KEYS[3] end
  if value == 'running' then return KEYS[4] end
  if value == 'retrying' then return KEYS[5] end
  if value == 'succeeded' then return KEYS[6] end
  if value == 'failed' then return KEYS[7] end
  if value == 'cancelled' then return KEYS[8] end
  return nil
end
"""

_MARK_RUNNING = (
    "-- fetchkit:mark-running\n"
    + _STATUS_KEY_FUNCTION
    + """
local old = redis.call('HGET', KEYS[1], 'status')
if not old then return 0 end
local score = redis.call('HGET', KEYS[1], 'created_score')
local old_key = status_key(old)
if old_key then redis.call('ZREM', old_key, ARGV[1]) end
redis.call('ZADD', KEYS[4], score, ARGV[1])
redis.call('HSET', KEYS[1],
  'job', ARGV[2],
  'status', 'running',
  'worker_id', ARGV[3],
  'delivery_count', ARGV[4],
  'updated_at', ARGV[5])
redis.call('HSETNX', KEYS[1], 'started_at', ARGV[5])
local started = redis.call('HGET', KEYS[1], 'started_at')
if started == '' then redis.call('HSET', KEYS[1], 'started_at', ARGV[5]) end
return 1
"""
)

_MARK_RETRY = (
    "-- fetchkit:mark-retry\n"
    + _STATUS_KEY_FUNCTION
    + """
local old = redis.call('HGET', KEYS[1], 'status')
if not old then return 0 end
local score = redis.call('HGET', KEYS[1], 'created_score')
local old_key = status_key(old)
if old_key then redis.call('ZREM', old_key, ARGV[1]) end
redis.call('ZADD', KEYS[5], score, ARGV[1])
redis.call('HSET', KEYS[1],
  'job', ARGV[2],
  'status', 'retrying',
  'result', ARGV[3],
  'worker_id', '',
  'updated_at', ARGV[4],
  'completed_at', '')
return 1
"""
)

_SAVE_RESULT = (
    "-- fetchkit:save-result\n"
    + _STATUS_KEY_FUNCTION
    + """
local old = redis.call('HGET', KEYS[1], 'status')
if not old then return 0 end
local score = redis.call('HGET', KEYS[1], 'created_score')
local old_key = status_key(old)
local new_key = status_key(ARGV[2])
if old_key then redis.call('ZREM', old_key, ARGV[1]) end
if new_key then redis.call('ZADD', new_key, score, ARGV[1]) end
redis.call('HSET', KEYS[1],
  'status', ARGV[2],
  'result', ARGV[3],
  'updated_at', ARGV[4],
  'completed_at', ARGV[4])
return 1
"""
)

_REQUEST_CANCEL = """
-- fetchkit:request-cancel
local status = redis.call('HGET', KEYS[1], 'status')
if not status then return 0 end
if status ~= 'succeeded' and status ~= 'failed' and status ~= 'cancelled' then
  redis.call('HSET', KEYS[1],
    'cancel_requested', '1',
    'updated_at', ARGV[1])
end
return 1
"""

_DELETE_RECORD = (
    "-- fetchkit:delete-record\n"
    + _STATUS_KEY_FUNCTION
    + """
local status = redis.call('HGET', KEYS[1], 'status')
if not status then return 0 end
local idempotency_hash = redis.call('HGET', KEYS[1], 'idempotency_hash')
local status_index = status_key(status)
if status_index then redis.call('ZREM', status_index, ARGV[1]) end
redis.call('ZREM', KEYS[2], ARGV[1])
if idempotency_hash and idempotency_hash ~= '' then
  redis.call('HDEL', KEYS[9], idempotency_hash)
end
redis.call('DEL', KEYS[1])
return 1
"""
)

_STATUSES: tuple[JobRecordStatus, ...] = (
    "queued",
    "running",
    "retrying",
    "succeeded",
    "failed",
    "cancelled",
)


def _decode(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


class RedisJobStore:
    """Durable Redis implementation of :class:`pyfetcher.jobs.JobStore`.

    Queue delivery and result storage remain independent contracts. Use this
    store with :class:`RedisStreamJobQueue` for a restart-safe Redis worker
    deployment; neither component claims exactly-once side effects.
    """

    def __init__(
        self,
        redis: object,
        *,
        prefix: str = "fetchkit:{jobs}:store",
        owns_client: bool = False,
    ) -> None:
        normalized = prefix.rstrip(":")
        if not normalized:
            raise ValueError("Redis job-store prefix cannot be empty")
        self._redis = redis
        self._prefix = normalized
        self._owns_client = owns_client

    @classmethod
    def from_url(cls, url: str, **kwargs: object) -> RedisJobStore:
        """Create a store with an owned async Redis client."""
        try:
            from redis.asyncio import Redis
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Redis job-store support requires `pip install 'fetchkit[redis]'`"
            ) from exc
        return cls(Redis.from_url(url), owns_client=True, **kwargs)

    def _record_key(self, job_id: UUID | str) -> str:
        return f"{self._prefix}:record:{job_id}"

    @property
    def _index_key(self) -> str:
        return f"{self._prefix}:index"

    @property
    def _idempotency_key(self) -> str:
        return f"{self._prefix}:idempotency"

    def _status_key(self, status: JobRecordStatus) -> str:
        return f"{self._prefix}:status:{status}"

    def _script_keys(self, job_id: UUID | str) -> tuple[str, ...]:
        return (
            self._record_key(job_id),
            self._index_key,
            *(self._status_key(status) for status in _STATUSES),
            self._idempotency_key,
        )

    @staticmethod
    def _idempotency_hash(job: JobRequest) -> str:
        if job.idempotency_key is None:
            return ""
        return hashlib.sha256(job.idempotency_key.encode()).hexdigest()

    @staticmethod
    def _deserialize(raw: object) -> JobRecord | None:
        if not raw:
            return None
        values = {_decode(key): _decode(value) for key, value in dict(raw).items()}
        result_json = values.get("result", "")
        return JobRecord(
            job=JobRequest.model_validate_json(values["job"]),
            status=values["status"],  # type: ignore[arg-type]
            result=JobResult.model_validate_json(result_json) if result_json else None,
            worker_id=values.get("worker_id") or None,
            delivery_count=int(values.get("delivery_count", 0)),
            cancel_requested=values.get("cancel_requested") == "1",
            created_at=values["created_at"],  # type: ignore[arg-type]
            updated_at=values["updated_at"],  # type: ignore[arg-type]
            started_at=values.get("started_at") or None,  # type: ignore[arg-type]
            completed_at=values.get("completed_at") or None,  # type: ignore[arg-type]
        )

    async def _require_after(self, job_id: UUID) -> JobRecord:
        record = await self.get(job_id)
        if record is None:
            raise KeyError(f"unknown job record: {job_id}")
        return record

    async def create(self, job: JobRequest) -> tuple[JobRecord, bool]:
        record = JobRecord(job=job)
        created_at = record.created_at.isoformat()
        result = await self._redis.eval(  # type: ignore[union-attr]
            _CREATE_RECORD,
            9,
            *self._script_keys(job.id),
            str(job.id),
            job.model_dump_json(),
            record.status,
            "",
            "",
            0,
            0,
            created_at,
            record.updated_at.isoformat(),
            "",
            "",
            record.created_at.timestamp(),
            self._idempotency_hash(job),
        )
        created, resolved_id = result
        stored = await self.get(UUID(_decode(resolved_id)))
        if stored is None:
            raise RuntimeError("Redis job-store create did not persist a record")
        return stored, bool(int(created))

    async def get(self, job_id: UUID) -> JobRecord | None:
        raw = await self._redis.hgetall(self._record_key(job_id))  # type: ignore[union-attr]
        return self._deserialize(raw)

    async def list(
        self,
        *,
        status: JobRecordStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[JobRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        index = self._index_key if status is None else self._status_key(status)
        identifiers = await self._redis.zrevrange(  # type: ignore[union-attr]
            index,
            offset,
            offset + limit - 1,
        )
        if not identifiers:
            return ()
        pipeline = self._redis.pipeline(transaction=False)  # type: ignore[union-attr]
        for identifier in identifiers:
            pipeline.hgetall(self._record_key(_decode(identifier)))
        values = await pipeline.execute()
        return tuple(record for raw in values if (record := self._deserialize(raw)) is not None)

    async def count(self, *, status: JobRecordStatus | None = None) -> int:
        index = self._index_key if status is None else self._status_key(status)
        return int(await self._redis.zcard(index))  # type: ignore[union-attr]

    async def mark_running(
        self,
        job: JobRequest,
        *,
        worker_id: str,
        delivery_count: int,
    ) -> JobRecord:
        updated_at = datetime.now(UTC).isoformat()
        changed = await self._redis.eval(  # type: ignore[union-attr]
            _MARK_RUNNING,
            9,
            *self._script_keys(job.id),
            str(job.id),
            job.model_dump_json(),
            worker_id,
            delivery_count,
            updated_at,
        )
        if not changed:
            raise KeyError(f"unknown job record: {job.id}")
        return await self._require_after(job.id)

    async def mark_retry(self, job: JobRequest, result: JobResult) -> JobRecord:
        changed = await self._redis.eval(  # type: ignore[union-attr]
            _MARK_RETRY,
            9,
            *self._script_keys(job.id),
            str(job.id),
            job.model_dump_json(),
            result.model_dump_json(),
            datetime.now(UTC).isoformat(),
        )
        if not changed:
            raise KeyError(f"unknown job record: {job.id}")
        return await self._require_after(job.id)

    async def save_result(self, result: JobResult) -> JobRecord:
        status: JobRecordStatus = "failed" if result.status == "retry" else result.status
        changed = await self._redis.eval(  # type: ignore[union-attr]
            _SAVE_RESULT,
            9,
            *self._script_keys(result.job_id),
            str(result.job_id),
            status,
            result.model_dump_json(),
            datetime.now(UTC).isoformat(),
        )
        if not changed:
            raise KeyError(f"unknown job record: {result.job_id}")
        return await self._require_after(result.job_id)

    async def request_cancel(self, job_id: UUID) -> JobRecord | None:
        changed = await self._redis.eval(  # type: ignore[union-attr]
            _REQUEST_CANCEL,
            1,
            self._record_key(job_id),
            datetime.now(UTC).isoformat(),
        )
        return await self.get(job_id) if changed else None

    async def cancel_requested(self, job_id: UUID) -> bool:
        value = await self._redis.hget(  # type: ignore[union-attr]
            self._record_key(job_id),
            "cancel_requested",
        )
        return value is not None and _decode(value) == "1"

    async def delete(self, job_id: UUID) -> None:
        await self._redis.eval(  # type: ignore[union-attr]
            _DELETE_RECORD,
            9,
            *self._script_keys(job_id),
            str(job_id),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._redis.aclose()  # type: ignore[union-attr]


__all__ = ["RedisJobStore"]
