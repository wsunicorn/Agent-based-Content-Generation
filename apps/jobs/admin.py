"""Django Admin configuration for jobs app."""
from django.contrib import admin
from django.utils.html import format_html

from .models import AgentRun, Artifact, Job, Revision


class AgentRunInline(admin.TabularInline):
    model = AgentRun
    extra = 0
    readonly_fields = (
        "id",
        "agent_type",
        "status",
        "attempt",
        "llm_calls_count",
        "input_tokens",
        "output_tokens",
        "started_at",
        "completed_at",
    )
    can_delete = False
    show_change_link = True
    fields = readonly_fields


class ArtifactInline(admin.TabularInline):
    model = Artifact
    extra = 0
    readonly_fields = ("id", "artifact_type", "version", "word_count", "created_at")
    can_delete = False
    show_change_link = True
    fields = readonly_fields


class RevisionInline(admin.TabularInline):
    model = Revision
    extra = 0
    readonly_fields = (
        "id",
        "revision_number",
        "triggered_by",
        "reason",
        "resolved",
        "created_at",
    )
    can_delete = False
    fields = readonly_fields


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title_short",
        "content_type",
        "status_badge",
        "llm_calls_count",
        "duration_display",
        "created_at",
    )
    list_filter = ("status", "content_type", "created_at")
    search_fields = ("title", "topic")
    readonly_fields = (
        "id",
        "celery_task_id",
        "llm_calls_count",
        "llm_tokens_used",
        "started_at",
        "completed_at",
        "created_at",
    )
    ordering = ("-created_at",)
    inlines = [AgentRunInline, ArtifactInline, RevisionInline]

    fieldsets = (
        (
            "Job Details",
            {
                "fields": (
                    "id",
                    "title",
                    "topic",
                    "content_type",
                    "target_length",
                    "keywords",
                    "additional_instructions",
                )
            },
        ),
        (
            "Execution",
            {
                "fields": (
                    "status",
                    "celery_task_id",
                    "error_message",
                    "llm_calls_count",
                    "llm_tokens_used",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "started_at", "completed_at")},
        ),
    )

    def title_short(self, obj):
        return obj.title[:60] + "…" if len(obj.title) > 60 else obj.title

    title_short.short_description = "Title"

    def status_badge(self, obj):
        colours = {
            "pending": "#6c757d",
            "running": "#0d6efd",
            "completed": "#198754",
            "failed": "#dc3545",
            "cancelled": "#ffc107",
            "paused": "#fd7e14",
        }
        colour = colours.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px">{}</span>',
            colour,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def duration_display(self, obj):
        secs = obj.duration_seconds
        if secs is None:
            return "—"
        mins, s = divmod(int(secs), 60)
        return f"{mins}m {s}s" if mins else f"{s}s"

    duration_display.short_description = "Duration"


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = (
        "agent_type",
        "status",
        "attempt",
        "llm_calls_count",
        "job",
        "started_at",
    )
    list_filter = ("agent_type", "status")
    search_fields = ("job__title",)
    readonly_fields = (
        "id",
        "job",
        "started_at",
        "completed_at",
        "prompt_snapshot",
        "response_snapshot",
    )


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ("artifact_type", "version", "word_count", "job", "created_at")
    list_filter = ("artifact_type",)
    search_fields = ("job__title",)
    readonly_fields = ("id", "job", "agent_run", "created_at")


@admin.register(Revision)
class RevisionAdmin(admin.ModelAdmin):
    list_display = (
        "revision_number",
        "triggered_by",
        "resolved",
        "job",
        "created_at",
    )
    list_filter = ("resolved", "triggered_by")
    readonly_fields = ("id", "job", "created_at")
