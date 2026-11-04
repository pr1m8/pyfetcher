"""Serializable jobs, template registries, queues, and local execution."""

from pyfetcher.jobs.application import JobApplication
from pyfetcher.jobs.events import WorkerEventBroker
from pyfetcher.jobs.logging import JsonLogFormatter, configure_job_logging
from pyfetcher.jobs.models import (
    FlowRequest,
    FlowResult,
    JobPolicy,
    JobRequest,
    JobResult,
    JobTraceContext,
    TemplateRef,
)
from pyfetcher.jobs.queue import InMemoryJobQueue, JobLease, JobQueue, QueueStats
from pyfetcher.jobs.registry import (
    JobContext,
    JobExecutor,
    JobTemplate,
    TemplateDescriptor,
    TemplateRegistry,
)
from pyfetcher.jobs.runtime import InProcessJobRuntime
from pyfetcher.jobs.service import (
    JobCancellation,
    JobControlPlane,
    JobNotFoundError,
    JobRecordPage,
    JobService,
    JobServiceHealth,
    JobSubmission,
)
from pyfetcher.jobs.store import (
    InMemoryJobStore,
    JobRecord,
    JobRecordStatus,
    JobStore,
)
from pyfetcher.jobs.templates import (
    MediaAcquisitionInput,
    MediaAcquisitionTemplate,
    PaginationInput,
    PaginationTemplate,
    SearchInput,
    SearchTemplate,
    register_builtin_templates,
)
from pyfetcher.jobs.worker import (
    JobWorker,
    WorkerConfig,
    WorkerEvent,
    WorkerEventSink,
    WorkerSnapshot,
)

__all__ = [
    "FlowRequest",
    "FlowResult",
    "InMemoryJobStore",
    "InMemoryJobQueue",
    "InProcessJobRuntime",
    "JobApplication",
    "JobCancellation",
    "JobContext",
    "JobControlPlane",
    "JobExecutor",
    "JobLease",
    "JobNotFoundError",
    "JobPolicy",
    "JobQueue",
    "JobRecord",
    "JobRecordPage",
    "JobRecordStatus",
    "JobRequest",
    "JobResult",
    "JobService",
    "JobServiceHealth",
    "JobStore",
    "JobSubmission",
    "JobTemplate",
    "JobTraceContext",
    "JobWorker",
    "JsonLogFormatter",
    "MediaAcquisitionInput",
    "MediaAcquisitionTemplate",
    "PaginationInput",
    "PaginationTemplate",
    "QueueStats",
    "SearchInput",
    "SearchTemplate",
    "TemplateDescriptor",
    "TemplateRef",
    "TemplateRegistry",
    "WorkerConfig",
    "WorkerEvent",
    "WorkerEventBroker",
    "WorkerEventSink",
    "WorkerSnapshot",
    "configure_job_logging",
    "register_builtin_templates",
]
