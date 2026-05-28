"""DRF serializers for the jobs app."""
from rest_framework import serializers

from .models import AgentRun, Artifact, Job, Revision


class AgentRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentRun
        fields = [
            "id",
            "agent_type",
            "status",
            "attempt",
            "provider",
            "llm_calls_count",
            "input_tokens",
            "output_tokens",
            "prompt_snapshot",
            "response_snapshot",
            "error_message",
            "started_at",
            "completed_at",
        ]


class ArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artifact
        fields = [
            "id",
            "artifact_type",
            "version",
            "word_count",
            "content_text",
            "content_json",
            "created_at",
        ]


class RevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Revision
        fields = [
            "id",
            "revision_number",
            "triggered_by",
            "reason",
            "issues",
            "resolved",
            "created_at",
        ]


class JobListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "topic",
            "content_type",
            "quality_mode",
            "status",
            "language",
            "llm_calls_count",
            "llm_usage_by_provider",
            "created_at",
            "completed_at",
        ]


class JobDetailSerializer(serializers.ModelSerializer):
    agent_runs = AgentRunSerializer(many=True, read_only=True)
    artifacts = ArtifactSerializer(many=True, read_only=True)
    revisions = RevisionSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "topic",
            "content_type",
            "quality_mode",
            "target_length",
            "keywords",
            "language",
            "additional_instructions",
            "status",
            "celery_task_id",
            "error_message",
            "llm_calls_count",
            "llm_tokens_used",
            "llm_usage_by_provider",
            "created_at",
            "started_at",
            "completed_at",
            "agent_runs",
            "artifacts",
            "revisions",
        ]


class JobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "title",
            "topic",
            "content_type",
            "quality_mode",
            "target_length",
            "keywords",
            "language",
            "additional_instructions",
        ]
