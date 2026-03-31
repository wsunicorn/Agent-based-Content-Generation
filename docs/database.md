# Database Schema

## 1. Entity Relationship Overview

```
User ──────< Job >──────< AgentRun
                │
                └──────< Artifact
                │
                └──────< Revision
```

---

## 2. Django Models

### Job

```python
class Job(models.Model):
    """
    Một yêu cầu tạo content. Entry point của toàn bộ pipeline.
    """

    class Status(models.TextChoices):
        PENDING   = "pending",   "Pending"
        RUNNING   = "running",   "Running"
        COMPLETED = "completed", "Completed"
        FAILED    = "failed",    "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class ContentType(models.TextChoices):
        BLOG_POST = "blog_post", "Blog Post"
        REPORT    = "report",    "Report"
        ARTICLE   = "article",   "Article"

    # Identity
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.CASCADE,
                                     related_name="jobs")

    # Input parameters
    topic        = models.CharField(max_length=500)
    audience     = models.CharField(max_length=300)
    tone         = models.CharField(max_length=200)
    content_type = models.CharField(max_length=20, choices=ContentType.choices,
                                    default=ContentType.BLOG_POST)
    target_words = models.IntegerField(default=1500)
    language     = models.CharField(max_length=10, default="en")
    focus_keywords = models.JSONField(default=list)    # ["keyword1", "keyword2"]
    max_budget_usd = models.DecimalField(max_digits=6, decimal_places=2,
                                         default=Decimal("2.00"))

    # Pipeline settings
    num_sources      = models.IntegerField(default=10)
    max_revisions    = models.IntegerField(default=3)
    qa_threshold     = models.FloatField(default=7.5)
    require_human_fact_check = models.BooleanField(default=False)

    # State
    status          = models.CharField(max_length=20, choices=Status.choices,
                                       default=Status.PENDING)
    current_stage   = models.CharField(max_length=50, blank=True)
    revision_count  = models.IntegerField(default=0)
    error_message   = models.TextField(blank=True)

    # Metrics
    cost_usd        = models.DecimalField(max_digits=8, decimal_places=4,
                                          default=Decimal("0"))
    total_tokens    = models.IntegerField(default=0)
    duration_seconds = models.IntegerField(null=True)
    final_qa_score  = models.FloatField(null=True)
    final_word_count = models.IntegerField(null=True)

    # Timestamps
    created_at   = models.DateTimeField(auto_now_add=True)
    started_at   = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "status"]),
        ]
```

---

### AgentRun

```python
class AgentRun(models.Model):
    """
    Log chi tiết mỗi lần một agent chạy trong pipeline.
    """

    class Status(models.TextChoices):
        RUNNING   = "running",   "Running"
        COMPLETED = "completed", "Completed"
        FAILED    = "failed",    "Failed"
        SKIPPED   = "skipped",   "Skipped"

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4)
    job         = models.ForeignKey(Job, on_delete=models.CASCADE,
                                    related_name="agent_runs")

    # Agent info
    agent_name   = models.CharField(max_length=50)   # "research", "writer_body_1"...
    agent_model  = models.CharField(max_length=50)   # "gemini-2.5-flash"
    revision_round = models.IntegerField(default=0)

    # Execution
    status       = models.CharField(max_length=20, choices=Status.choices)
    input_data   = models.JSONField()
    output_data  = models.JSONField(null=True)
    error        = models.TextField(blank=True)

    # Cost & Performance
    input_tokens  = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    cost_usd      = models.DecimalField(max_digits=8, decimal_places=6,
                                        default=Decimal("0"))
    duration_ms   = models.IntegerField(default=0)

    # Timestamps
    started_at    = models.DateTimeField(auto_now_add=True)
    completed_at  = models.DateTimeField(null=True)

    class Meta:
        ordering = ["started_at"]
        indexes = [
            models.Index(fields=["job", "agent_name"]),
        ]
```

---

### Artifact

```python
class Artifact(models.Model):
    """
    Lưu trữ output của từng bước trong pipeline.
    Mỗi revision tạo thêm artifact version mới.
    """

    class ArtifactType(models.TextChoices):
        RESEARCH_DOSSIER = "research_dossier", "Research Dossier"
        OUTLINE          = "outline",           "Outline"
        SECTION_DRAFT    = "section_draft",     "Section Draft"
        MERGED_DRAFT     = "merged_draft",      "Merged Draft"
        EDITED_DRAFT     = "edited_draft",      "Edited Draft"
        SEO_OPTIMIZED    = "seo_optimized",     "SEO Optimized"
        FACT_CHECKED     = "fact_checked",      "Fact Checked"
        FINAL            = "final",             "Final"

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4)
    job          = models.ForeignKey(Job, on_delete=models.CASCADE,
                                     related_name="artifacts")

    artifact_type = models.CharField(max_length=30, choices=ArtifactType.choices)
    version       = models.IntegerField(default=1)    # Tăng per revision round
    section_id    = models.CharField(max_length=50, blank=True)  # Cho section drafts

    content       = models.TextField()         # Nội dung chính (text)
    metadata      = models.JSONField(default=dict)  # SEO data, scores, reports...

    word_count    = models.IntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = [("job", "artifact_type", "version", "section_id")]
        indexes = [
            models.Index(fields=["job", "artifact_type", "version"]),
        ]

    def save(self, *args, **kwargs):
        if self.content and not self.word_count:
            self.word_count = len(self.content.split())
        super().save(*args, **kwargs)
```

---

### Revision

```python
class Revision(models.Model):
    """
    Tracks mỗi revision cycle (QA fail → Editor → QA lại).
    """

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4)
    job             = models.ForeignKey(Job, on_delete=models.CASCADE,
                                        related_name="revisions")

    round           = models.IntegerField()      # 1, 2, 3
    qa_score_before = models.FloatField()        # Score gây ra revision
    qa_feedback     = models.TextField()         # Feedback từ QA agent
    qa_score_after  = models.FloatField(null=True) # Score sau revision
    approved        = models.BooleanField(default=False)

    created_at      = models.DateTimeField(auto_now_add=True)
    resolved_at     = models.DateTimeField(null=True)

    class Meta:
        ordering = ["round"]
        unique_together = [("job", "round")]
```

---

### ContentTemplate (Optional — Phase 4)

```python
class ContentTemplate(models.Model):
    """
    Pre-defined templates cho các loại content phổ biến.
    """

    name         = models.CharField(max_length=100)
    content_type = models.CharField(max_length=20)
    description  = models.TextField()

    # Default parameters
    default_tone         = models.CharField(max_length=200)
    default_target_words = models.IntegerField(default=1500)
    outline_structure    = models.JSONField()    # Section definitions

    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
```

---

## 3. Database Diagrams

```
jobs
├── id (UUID PK)
├── user_id (FK → auth_user)
├── topic
├── audience
├── tone
├── content_type
├── target_words
├── status
├── current_stage
├── revision_count
├── cost_usd
├── final_qa_score
├── created_at
└── completed_at

agent_runs
├── id (UUID PK)
├── job_id (FK → jobs)
├── agent_name
├── agent_model
├── revision_round
├── status
├── input_data (JSONB)
├── output_data (JSONB)
├── cost_usd
├── duration_ms
└── started_at

artifacts
├── id (UUID PK)
├── job_id (FK → jobs)
├── artifact_type
├── version
├── section_id
├── content (TEXT)
├── metadata (JSONB)
├── word_count
└── created_at

revisions
├── id (UUID PK)
├── job_id (FK → jobs)
├── round
├── qa_score_before
├── qa_feedback
├── qa_score_after
└── created_at
```

---

## 4. Key Queries

### Get full job timeline
```python
job = Job.objects.prefetch_related(
    "agent_runs",
    "artifacts",
    "revisions"
).get(id=job_id)
```

### Get final artifact
```python
final = Artifact.objects.filter(
    job=job,
    artifact_type=Artifact.ArtifactType.FINAL
).order_by("-version").first()
```

### Analytics: Average cost per job
```python
from django.db.models import Avg
Job.objects.filter(status="completed").aggregate(
    avg_cost=Avg("cost_usd"),
    avg_duration=Avg("duration_seconds"),
    avg_score=Avg("final_qa_score"),
)
```

### Most expensive agent
```python
from django.db.models import Sum
AgentRun.objects.values("agent_name").annotate(
    total_cost=Sum("cost_usd"),
    total_runs=Count("id"),
    avg_duration=Avg("duration_ms")
).order_by("-total_cost")
```

---

## 5. Migrations Strategy

```bash
# Khởi tạo
python manage.py makemigrations jobs
python manage.py migrate

# Seed templates (Phase 4)
python manage.py loaddata content_templates.json
```

---

## 6. PostgreSQL Specific Features

### JSONB Indexes (Cho performance)
```sql
-- Index trên metadata trong artifacts
CREATE INDEX idx_artifacts_metadata ON artifacts USING GIN (metadata);

-- Index trên input/output data
CREATE INDEX idx_agent_runs_output ON agent_runs USING GIN (output_data);
```

### Full-text search trên content
```sql
CREATE INDEX idx_artifacts_content_fts
ON artifacts USING GIN (to_tsvector('english', content));
```
