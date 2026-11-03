"""Serializable jobs, template registries, queues, and local execution."""

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
from pyfetcher.jobs.templates import (
    MediaAcquisitionInput,
    MediaAcquisitionTemplate,
    PaginationInput,
    PaginationTemplate,
    SearchInput,
    SearchTemplate,
    register_builtin_templates,
)

__all__ = [
    "FlowRequest",
    "FlowResult",
    "InMemoryJobQueue",
    "InProcessJobRuntime",
    "JobContext",
    "JobExecutor",
    "JobLease",
    "JobPolicy",
    "JobQueue",
    "JobRequest",
    "JobResult",
    "JobTemplate",
    "JobTraceContext",
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
    "register_builtin_templates",
]
