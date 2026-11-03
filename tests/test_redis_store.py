"""Offline contract tests for the durable Redis job store."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from pyfetcher.integrations.redis_store import RedisJobStore
from pyfetcher.jobs import JobRequest, JobResult, TemplateRef


class FakePipeline:
    """Small async-pipeline surface used by ``RedisJobStore.list``."""

    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._keys: list[str] = []

    def hgetall(self, key: str) -> FakePipeline:
        self._keys.append(key)
        return self

    async def execute(self) -> list[dict[bytes, bytes]]:
        return [await self._redis.hgetall(key) for key in self._keys]


class FakeRedis:
    """Redis subset that executes the store's named Lua transitions atomically."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}
        self.closed = False

    @staticmethod
    def _status_key(keys: Sequence[str], status: str) -> str | None:
        statuses = ("queued", "running", "retrying", "succeeded", "failed", "cancelled")
        try:
            return keys[2 + statuses.index(status)]
        except ValueError:
            return None

    def _transition(self, keys: Sequence[str], job_id: str, status: str) -> None:
        record = self.hashes[keys[0]]
        old_key = self._status_key(keys, record["status"])
        if old_key is not None:
            self.sorted_sets.setdefault(old_key, {}).pop(job_id, None)
        new_key = self._status_key(keys, status)
        if new_key is not None:
            self.sorted_sets.setdefault(new_key, {})[job_id] = float(record["created_score"])

    async def eval(self, script: str, numkeys: int, *values: object) -> object:
        keys = tuple(str(value) for value in values[:numkeys])
        args = tuple(str(value) for value in values[numkeys:])

        if "fetchkit:create-record" in script:
            job_id = args[0]
            if keys[0] in self.hashes:
                return [0, job_id.encode()]
            idempotency_hash = args[12]
            idempotency = self.hashes.setdefault(keys[8], {})
            if idempotency_hash and idempotency_hash in idempotency:
                return [0, idempotency[idempotency_hash].encode()]
            self.hashes[keys[0]] = {
                "job": args[1],
                "status": args[2],
                "result": args[3],
                "worker_id": args[4],
                "delivery_count": args[5],
                "cancel_requested": args[6],
                "created_at": args[7],
                "updated_at": args[8],
                "started_at": args[9],
                "completed_at": args[10],
                "created_score": args[11],
                "idempotency_hash": idempotency_hash,
            }
            score = float(args[11])
            self.sorted_sets.setdefault(keys[1], {})[job_id] = score
            self.sorted_sets.setdefault(keys[2], {})[job_id] = score
            if idempotency_hash:
                idempotency[idempotency_hash] = job_id
            return [1, job_id.encode()]

        if "fetchkit:mark-running" in script:
            if keys[0] not in self.hashes:
                return 0
            job_id, job, worker_id, delivery_count, updated_at = args
            self._transition(keys, job_id, "running")
            record = self.hashes[keys[0]]
            record.update(
                job=job,
                status="running",
                worker_id=worker_id,
                delivery_count=delivery_count,
                updated_at=updated_at,
            )
            if not record["started_at"]:
                record["started_at"] = updated_at
            return 1

        if "fetchkit:mark-retry" in script:
            if keys[0] not in self.hashes:
                return 0
            job_id, job, result, updated_at = args
            self._transition(keys, job_id, "retrying")
            self.hashes[keys[0]].update(
                job=job,
                status="retrying",
                result=result,
                worker_id="",
                updated_at=updated_at,
                completed_at="",
            )
            return 1

        if "fetchkit:save-result" in script:
            if keys[0] not in self.hashes:
                return 0
            job_id, status, result, updated_at = args
            self._transition(keys, job_id, status)
            self.hashes[keys[0]].update(
                status=status,
                result=result,
                updated_at=updated_at,
                completed_at=updated_at,
            )
            return 1

        if "fetchkit:request-cancel" in script:
            record = self.hashes.get(keys[0])
            if record is None:
                return 0
            if record["status"] not in {"succeeded", "failed", "cancelled"}:
                record.update(cancel_requested="1", updated_at=args[0])
            return 1

        if "fetchkit:delete-record" in script:
            record = self.hashes.get(keys[0])
            if record is None:
                return 0
            job_id = args[0]
            status_key = self._status_key(keys, record["status"])
            if status_key is not None:
                self.sorted_sets.setdefault(status_key, {}).pop(job_id, None)
            self.sorted_sets.setdefault(keys[1], {}).pop(job_id, None)
            if record["idempotency_hash"]:
                self.hashes.setdefault(keys[8], {}).pop(record["idempotency_hash"], None)
            del self.hashes[keys[0]]
            return 1

        raise AssertionError("unexpected Lua script")

    async def hgetall(self, key: str) -> dict[bytes, bytes]:
        return {field.encode(): value.encode() for field, value in self.hashes.get(key, {}).items()}

    async def hget(self, key: str, field: str) -> bytes | None:
        value = self.hashes.get(key, {}).get(field)
        return value.encode() if value is not None else None

    async def zrevrange(self, key: str, start: int, stop: int) -> list[bytes]:
        ordered = sorted(
            self.sorted_sets.get(key, {}).items(),
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
        return [member.encode() for member, _ in ordered[start : stop + 1]]

    async def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, {}))

    def pipeline(self, *, transaction: bool) -> FakePipeline:
        assert transaction is False
        return FakePipeline(self)

    async def aclose(self) -> None:
        self.closed = True


def _job(*, idempotency_key: str | None = None) -> JobRequest:
    return JobRequest(
        template=TemplateRef(name="test.redis"),
        idempotency_key=idempotency_key,
    )


async def test_redis_store_atomically_deduplicates_and_pages() -> None:
    redis = FakeRedis()
    store = RedisJobStore(redis)
    jobs = tuple(_job(idempotency_key="shared") for _ in range(8))

    results = await asyncio.gather(*(store.create(job) for job in jobs))

    assert sum(created for _, created in results) == 1
    assert {record.job.id for record, _ in results} == {jobs[0].id}
    assert await store.count() == 1
    assert await store.count(status="queued") == 1
    assert await store.list(limit=1, offset=0) == (results[0][0],)


async def test_redis_store_tracks_retry_and_terminal_indexes() -> None:
    store = RedisJobStore(FakeRedis())
    job = _job()
    await store.create(job)

    running = await store.mark_running(job, worker_id="worker-1", delivery_count=2)
    retry = JobResult(job_id=job.id, status="retry", error="try again")
    next_job = job.next_attempt()
    retrying = await store.mark_retry(next_job, retry)
    rerunning = await store.mark_running(
        next_job,
        worker_id="worker-2",
        delivery_count=3,
    )
    succeeded = await store.save_result(JobResult.succeeded(next_job, output={"attempt": 2}))

    assert running.started_at is not None
    assert retrying.status == "retrying"
    assert retrying.job.attempt == 2
    assert rerunning.started_at == running.started_at
    assert succeeded.status == "succeeded"
    assert succeeded.result is not None
    assert succeeded.result.output == {"attempt": 2}
    assert succeeded.completed_at is not None
    assert await store.count(status="running") == 0
    assert await store.count(status="retrying") == 0
    assert await store.count(status="succeeded") == 1


async def test_redis_store_cancellation_is_cooperative_and_terminal_safe() -> None:
    store = RedisJobStore(FakeRedis())
    job = _job()
    await store.create(job)

    requested = await store.request_cancel(job.id)
    assert requested is not None
    assert requested.cancel_requested is True
    assert await store.cancel_requested(job.id) is True

    terminal = await store.save_result(JobResult.succeeded(job))
    unchanged = await store.request_cancel(job.id)
    missing = await store.request_cancel(_job().id)

    assert unchanged == terminal
    assert missing is None


async def test_redis_store_delete_releases_idempotency_key() -> None:
    redis = FakeRedis()
    store = RedisJobStore(redis)
    first = _job(idempotency_key="reusable")
    replacement = _job(idempotency_key="reusable")
    await store.create(first)

    await store.delete(first.id)
    record, created = await store.create(replacement)

    assert created is True
    assert record.job.id == replacement.id
    assert await store.get(first.id) is None
    assert await store.count() == 1


async def test_redis_store_closes_only_owned_client() -> None:
    borrowed = FakeRedis()
    owned = FakeRedis()

    await RedisJobStore(borrowed).aclose()
    await RedisJobStore(owned, owns_client=True).aclose()

    assert borrowed.closed is False
    assert owned.closed is True


async def test_redis_store_rejects_invalid_page_bounds() -> None:
    store = RedisJobStore(FakeRedis())

    for kwargs in ({"limit": 0}, {"offset": -1}):
        try:
            await store.list(**kwargs)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError("invalid paging bound was accepted")


def test_redis_store_rejects_empty_prefix() -> None:
    try:
        RedisJobStore(FakeRedis(), prefix=":")
    except ValueError as exc:
        assert "prefix cannot be empty" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("empty prefix was accepted")
