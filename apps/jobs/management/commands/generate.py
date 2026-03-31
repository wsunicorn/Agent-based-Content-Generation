"""
Management command: python manage.py generate

Usage:
  python manage.py generate "AI in Healthcare" --type blog_post --length 1200 --keywords "AI,healthcare,diagnosis"
  python manage.py generate "Quantum computing" --type technical_report --async
"""
from __future__ import annotations

import json
import time

from django.core.management.base import BaseCommand, CommandError

from apps.jobs.models import Job


class Command(BaseCommand):
    help = "Generate content using the multi-agent pipeline."

    def add_arguments(self, parser):
        parser.add_argument("topic", type=str, help="Topic or research question")
        parser.add_argument(
            "--title",
            type=str,
            default="",
            help="Article title (defaults to topic if not provided)",
        )
        parser.add_argument(
            "--type",
            dest="content_type",
            type=str,
            default="blog_post",
            choices=["blog_post", "technical_report", "news_article", "tutorial"],
            help="Content type (default: blog_post)",
        )
        parser.add_argument(
            "--length",
            dest="target_length",
            type=int,
            default=1500,
            help="Target word count (default: 1500)",
        )
        parser.add_argument(
            "--keywords",
            type=str,
            default="",
            help="Comma-separated keywords (e.g. 'AI,healthcare,2024')",
        )
        parser.add_argument(
            "--instructions",
            type=str,
            default="",
            help="Additional instructions for the agents",
        )
        parser.add_argument(
            "--async",
            dest="run_async",
            action="store_true",
            default=False,
            help="Dispatch to Celery and return immediately (default: run synchronously)",
        )

    def handle(self, *args, **options):
        topic = options["topic"].strip()
        title = options["title"].strip() or topic
        content_type = options["content_type"]
        target_length = options["target_length"]
        keywords = [k.strip() for k in options["keywords"].split(",") if k.strip()]
        instructions = options["instructions"].strip()
        run_async = options["run_async"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== Content Pipeline ==="))
        self.stdout.write(f"  Topic      : {topic}")
        self.stdout.write(f"  Type       : {content_type}")
        self.stdout.write(f"  Length     : {target_length} words")
        self.stdout.write(f"  Keywords   : {keywords or 'none'}")
        self.stdout.write("")

        # Create job record
        job = Job.objects.create(
            title=title,
            topic=topic,
            content_type=content_type,
            target_length=target_length,
            keywords=keywords,
            additional_instructions=instructions,
        )
        self.stdout.write(f"  Job ID     : {job.id}")

        if run_async:
            from apps.jobs.tasks import run_pipeline
            task = run_pipeline.delay(str(job.id))
            job.celery_task_id = task.id
            job.status = Job.Status.RUNNING
            job.save(update_fields=["celery_task_id", "status"])
            self.stdout.write(
                self.style.SUCCESS(f"\nDispatched to Celery — task_id={task.id}")
            )
            self.stdout.write(f"Monitor at: http://localhost:8000/admin/jobs/job/{job.id}/change/")
            return

        # Synchronous run (blocks until done)
        self.stdout.write("\nRunning pipeline synchronously...\n")
        self._run_sync(job)

    def _run_sync(self, job: Job):
        """Run the pipeline directly in this process (no Celery)."""
        import dataclasses
        from django.utils import timezone

        from apps.jobs.tasks import _save_artifacts
        from apps.pipeline.graph import get_pipeline_graph
        from apps.pipeline.state import PipelineState

        job.status = Job.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])

        state = PipelineState(
            job_id=str(job.id),
            topic=job.topic,
            content_type=job.content_type,
            target_length=job.target_length,
            keywords=job.keywords or [],
            additional_instructions=job.additional_instructions or "",
        )

        try:
            graph = get_pipeline_graph()
            initial = dataclasses.asdict(state)
            t0 = time.time()

            self.stdout.write("  [coordinator] → ", ending="")
            self.stdout.flush()

            final = graph.invoke(initial)
            elapsed = time.time() - t0

            valid_fields = {f.name for f in dataclasses.fields(PipelineState)}
            state = PipelineState.from_dict(final)

            _save_artifacts(job, state)

            job.status = Job.Status.COMPLETED
            job.completed_at = timezone.now()
            job.llm_calls_count = state.llm_calls_total
            job.llm_tokens_used = state.llm_tokens_total
            job.save(update_fields=["status", "completed_at", "llm_calls_count", "llm_tokens_used"])

            self.stdout.write(self.style.SUCCESS("\n\n=== PIPELINE COMPLETE ==="))
            self.stdout.write(f"  Elapsed    : {elapsed:.1f}s")
            self.stdout.write(f"  Words      : {state.word_count}")
            self.stdout.write(f"  LLM calls  : {state.llm_calls_total}")
            self.stdout.write(f"  QA score   : {state.qa_report.overall_score if state.qa_report else 'N/A'}")
            self.stdout.write(f"  QA passed  : {state.qa_report.passed if state.qa_report else False}")

            if state.final_content:
                self.stdout.write("\n--- FINAL CONTENT (first 500 chars) ---")
                self.stdout.write(state.final_content[:500] + "...")

        except Exception as exc:
            job.status = Job.Status.FAILED
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message"])
            raise CommandError(f"Pipeline failed: {exc}") from exc
