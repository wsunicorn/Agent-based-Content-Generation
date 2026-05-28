"""Django models for content generation jobs."""
import uuid

from django.db import models
from django.utils import timezone


class Job(models.Model):
    """Top-level unit of work — one article/report generation run."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class ContentType(models.TextChoices):
        BLOG_POST = "blog_post", "Blog Post"
        TECHNICAL_REPORT = "technical_report", "Technical Report"
        NEWS_ARTICLE = "news_article", "News Article"
        TUTORIAL = "tutorial", "Tutorial"

    class QualityMode(models.TextChoices):
        FAST = "fast", "Fast"
        STANDARD = "standard", "Standard"
        STRICT = "strict", "Strict"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500)
    topic = models.TextField(help_text="Primary topic / research question")
    content_type = models.CharField(
        max_length=30, choices=ContentType.choices, default=ContentType.BLOG_POST
    )
    quality_mode = models.CharField(
        max_length=20,
        choices=QualityMode.choices,
        default=QualityMode.STANDARD,
        help_text="Controls revision depth and fact-check strictness",
    )
    target_length = models.PositiveIntegerField(
        default=1500, help_text="Target word count"
    )
    keywords = models.JSONField(default=list, blank=True)
    language = models.CharField(
        max_length=50, default="English", blank=True,
        help_text="Output language (e.g. English, Vietnamese, French, Spanish)"
    )
    additional_instructions = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    celery_task_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    # LLM usage tracking
    llm_calls_count = models.PositiveIntegerField(default=0)
    llm_tokens_used = models.PositiveIntegerField(default=0)
    llm_usage_by_provider = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Job"
        verbose_name_plural = "Jobs"

    def __str__(self):
        return f"[{self.status.upper()}] {self.title[:80]}"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class AgentRun(models.Model):
    """Records a single agent's execution within a job."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    class AgentType(models.TextChoices):
        COORDINATOR = "coordinator", "Coordinator"
        COORDINATOR_ROUTER = "coordinator_router", "Coordinator Router"
        RESEARCH = "research", "Research"
        OUTLINE = "outline", "Outline"
        WRITER = "writer", "Writer"
        SECTION_WRITER = "section_writer", "Section Writer"
        JOIN_DRAFT = "join_draft", "Join Draft"
        EDITOR = "editor", "Editor"
        SEO = "seo", "SEO"
        FACT_CHECKER = "fact_checker", "Fact Checker"
        QA = "qa", "QA"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="agent_runs")
    agent_type = models.CharField(max_length=30, choices=AgentType.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    attempt = models.PositiveSmallIntegerField(default=1)
    error_message = models.TextField(blank=True)

    # Prompt / response snapshots for debugging
    prompt_snapshot = models.TextField(blank=True)
    response_snapshot = models.TextField(blank=True)

    # LLM usage
    provider = models.CharField(max_length=50, blank=True)
    llm_calls_count = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["started_at"]
        verbose_name = "Agent Run"
        verbose_name_plural = "Agent Runs"

    def __str__(self):
        return f"{self.agent_type} — {self.status} (job {self.job_id})"


class Artifact(models.Model):
    """Stores the output produced by an agent run."""

    class ArtifactType(models.TextChoices):
        RESEARCH_SUMMARY = "research_summary", "Research Summary"
        OUTLINE = "outline", "Outline"
        DRAFT = "draft", "Draft"
        EDITED_DRAFT = "edited_draft", "Edited Draft"
        FINAL_CONTENT = "final_content", "Final Content"
        SEO_METADATA = "seo_metadata", "SEO Metadata"
        QA_REPORT = "qa_report", "QA Report"
        FACT_CHECK_REPORT = "fact_check_report", "Fact Check Report"
        SOURCE_DOCUMENTS = "source_documents", "Source Documents"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="artifacts")
    agent_run = models.ForeignKey(
        AgentRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="artifacts",
    )
    artifact_type = models.CharField(max_length=30, choices=ArtifactType.choices)

    # Content stored as JSON (structured data) or plain text
    content_text = models.TextField(blank=True)
    content_json = models.JSONField(default=dict, blank=True)

    word_count = models.PositiveIntegerField(default=0)
    version = models.PositiveSmallIntegerField(default=1)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Artifact"
        verbose_name_plural = "Artifacts"

    def __str__(self):
        return f"{self.artifact_type} v{self.version} (job {self.job_id})"


class Revision(models.Model):
    """Tracks a revision cycle — editor/QA flagging issues to re-run agents."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="revisions")
    revision_number = models.PositiveSmallIntegerField(default=1)
    triggered_by = models.CharField(
        max_length=30,
        choices=AgentRun.AgentType.choices,
        help_text="Agent that triggered this revision",
    )
    reason = models.TextField(help_text="Why the revision was needed")
    issues = models.JSONField(default=list, help_text="List of specific issues to fix")
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["revision_number"]
        verbose_name = "Revision"
        verbose_name_plural = "Revisions"

    def __str__(self):
        return f"Revision #{self.revision_number} (job {self.job_id})"
