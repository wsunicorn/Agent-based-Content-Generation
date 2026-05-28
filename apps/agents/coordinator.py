"""
Coordinator Agent - initialises pipeline input and routes revision loops.

The first coordinator node validates job input. The router node then runs after
quality gates and decides which agent should run next.
"""
from __future__ import annotations

import logging
from typing import Any

from apps.pipeline.state import PipelineState

from .base import BaseAgent

logger = logging.getLogger(__name__)

VALID_CONTENT_TYPES = {"blog_post", "technical_report", "news_article", "tutorial"}


class CoordinatorAgent(BaseAgent):
    name = "coordinator"

    def run(self, state: PipelineState) -> PipelineState:
        logger.info(
            "[CoordinatorAgent] Initialising pipeline - job_id=%s topic=%s",
            state.job_id,
            state.topic[:80],
        )
        state.current_agent = self.name

        if state.content_type not in VALID_CONTENT_TYPES:
            state.content_type = "blog_post"

        state.target_length = max(300, min(5000, state.target_length))
        state.keywords = [kw.strip() for kw in state.keywords if kw.strip()][:10]

        logger.info(
            "[CoordinatorAgent] Pipeline configured - type=%s, target=%d words, keywords=%s",
            state.content_type,
            state.target_length,
            state.keywords,
        )
        return state

    def run_router(self, state: PipelineState) -> PipelineState:
        """Route after quality gates without spending an LLM call."""
        previous_gate = state.current_agent or state.last_quality_gate
        state.last_quality_gate = previous_gate
        state.current_agent = "coordinator_router"

        logger.info(
            "[CoordinatorAgent] Routing after %s (revision=%d/%d)",
            previous_gate,
            state.revision_count,
            state.max_revisions,
        )

        if previous_gate == "editor":
            return self._route_after_editor(state)
        if previous_gate == "fact_checker":
            return self._route_after_fact_checker(state)
        if previous_gate == "seo":
            return self._route_after_seo(state)
        if previous_gate == "qa":
            return self._route_after_qa(state)

        return self._apply_decision(
            state,
            next_action="approve",
            target_agent="",
            decision="approve",
            issues=[],
            instructions="Pipeline finished.",
        )

    def _route_after_editor(self, state: PipelineState) -> PipelineState:
        if state.needs_revision:
            reason = state.revision_reason or "Editor requested a writer rewrite."
            if not self._can_retry(state, "writer"):
                return self._apply_decision(
                    state,
                    next_action="approve",
                    target_agent="fact_checker",
                    decision="warning",
                    issues=[reason, "Writer retry budget exhausted."],
                    instructions="Continue with the best edited draft available.",
                )
            return self._request_revision(
                state,
                next_action="rewrite_section",
                target_agent="writer",
                issues=[reason],
                instructions=reason,
                target_section_ids=[],
            )

        return self._apply_decision(
            state,
            next_action="approve",
            target_agent="fact_checker",
            decision="continue",
            issues=[],
            instructions="Editor approved the draft.",
        )

    def _route_after_fact_checker(self, state: PipelineState) -> PipelineState:
        unverified_count = len(state.unverified_claims or [])
        if state.fact_check_passed or unverified_count == 0:
            return self._apply_decision(
                state,
                next_action="approve",
                target_agent="seo",
                decision="continue",
                issues=[],
                instructions="Fact check passed.",
            )

        issues = [
            item.get("claim", "Unverified claim")
            for item in (state.unverified_claims or [])[:5]
            if isinstance(item, dict)
        ] or ["Unverified factual claims remain."]

        evidence_weak = not state.sources or not state.research_summary or unverified_count >= 3
        if evidence_weak and self._can_retry(state, "research"):
            return self._request_revision(
                state,
                next_action="redo_research",
                target_agent="research",
                issues=issues,
                instructions=(
                    "Gather stronger evidence and rebuild the article around claims "
                    "that can be supported by sources."
                ),
            )

        if self._can_retry(state, "editor"):
            return self._request_revision(
                state,
                next_action="revise_editor",
                target_agent="editor",
                issues=issues,
                instructions="Rewrite or remove unsupported factual claims.",
            )

        return self._apply_decision(
            state,
            next_action="approve",
            target_agent="seo",
            decision="warning",
            issues=issues + ["Fact-check retry budget exhausted."],
            instructions="Continue with warnings and let QA make the final call.",
        )

    def _route_after_seo(self, state: PipelineState) -> PipelineState:
        metadata = state.seo_metadata
        issues: list[str] = []
        if not metadata.meta_title:
            issues.append("Missing meta title.")
        if not metadata.meta_description:
            issues.append("Missing meta description.")
        if not metadata.slug:
            issues.append("Missing slug.")
        if not metadata.focus_keyword:
            issues.append("Missing focus keyword.")

        if issues and self._can_retry(state, "seo"):
            return self._request_revision(
                state,
                next_action="redo_seo",
                target_agent="seo",
                issues=issues,
                instructions="Regenerate complete SEO metadata for the article.",
            )

        if issues:
            return self._apply_decision(
                state,
                next_action="approve",
                target_agent="qa",
                decision="warning",
                issues=issues + ["SEO retry budget exhausted."],
                instructions="Continue with incomplete SEO metadata and let QA score it.",
            )

        return self._apply_decision(
            state,
            next_action="approve",
            target_agent="qa",
            decision="continue",
            issues=[],
            instructions="SEO metadata passed structural checks.",
        )

    def _route_after_qa(self, state: PipelineState) -> PipelineState:
        report = state.qa_report
        if report.passed:
            state.final_content = state.final_content or state.edited_draft or state.draft
            state.completed = True
            return self._apply_decision(
                state,
                next_action="approve",
                target_agent="",
                decision="approve",
                issues=[],
                instructions="QA approved the final content.",
            )

        return self._request_revision(
            state,
            next_action=report.next_action or "revise_editor",
            target_agent=report.target_agent or "editor",
            issues=report.issues or report.feedback or ["QA score below threshold."],
            instructions=(
                report.revision_instructions
                or "Address QA feedback and preserve the article structure."
            ),
            target_section_ids=report.target_section_ids,
            decision=report.decision or "revise",
        )

    def _request_revision(
        self,
        state: PipelineState,
        *,
        next_action: str,
        target_agent: str,
        issues: list[str],
        instructions: str,
        target_section_ids: list[int] | None = None,
        decision: str = "revise",
    ) -> PipelineState:
        if next_action == "fail_with_warning":
            return self._fail_with_warning(
                state,
                issues=issues,
                instructions=instructions,
            )

        if not target_agent:
            target_agent = self._target_for_action(next_action)

        if not self._can_retry(state, target_agent):
            reason = (
                f"Retry limit reached for {target_agent or 'pipeline'} "
                f"({state.revision_count}/{state.max_revisions} total revisions)."
            )
            return self._fail_with_warning(
                state,
                issues=(issues or []) + [reason],
                instructions=instructions or reason,
            )

        return self._apply_decision(
            state,
            next_action=next_action,
            target_agent=target_agent,
            decision=decision,
            issues=issues,
            instructions=instructions,
            target_section_ids=target_section_ids or [],
            increments_revision=True,
        )

    def _apply_decision(
        self,
        state: PipelineState,
        *,
        next_action: str,
        target_agent: str,
        decision: str,
        issues: list[str],
        instructions: str,
        target_section_ids: list[int] | None = None,
        increments_revision: bool = False,
    ) -> PipelineState:
        state.routing_decision = decision
        state.next_action = next_action
        state.target_agent = target_agent
        state.routing_issues = issues or []
        state.revision_instructions = instructions or ""
        state.revision_target_section_ids = target_section_ids or []

        if increments_revision:
            state.revision_count += 1
            state.retry_counts[target_agent] = state.retry_counts.get(target_agent, 0) + 1
            event = self._revision_event(
                state,
                next_action=next_action,
                target_agent=target_agent,
                issues=issues,
                instructions=instructions,
                target_section_ids=target_section_ids or [],
            )
            state.revision_events.append(event)
            state.completed = False

        logger.info(
            "[CoordinatorAgent] Decision=%s next_action=%s target=%s issues=%d",
            decision,
            next_action,
            target_agent or "END",
            len(issues or []),
        )
        return state

    def _fail_with_warning(
        self,
        state: PipelineState,
        *,
        issues: list[str],
        instructions: str,
    ) -> PipelineState:
        state.final_content = state.final_content or state.edited_draft or state.draft
        state.completed = True
        return self._apply_decision(
            state,
            next_action="fail_with_warning",
            target_agent="",
            decision="warning",
            issues=issues or ["Pipeline completed with unresolved quality warnings."],
            instructions=instructions,
            target_section_ids=[],
            increments_revision=False,
        )

    def _can_retry(self, state: PipelineState, target_agent: str) -> bool:
        if not target_agent:
            return False
        if state.revision_count >= state.max_revisions:
            return False
        return state.retry_counts.get(target_agent, 0) < state.max_agent_retries

    def _revision_event(
        self,
        state: PipelineState,
        *,
        next_action: str,
        target_agent: str,
        issues: list[str],
        instructions: str,
        target_section_ids: list[int],
    ) -> dict[str, Any]:
        return {
            "revision_number": state.revision_count,
            "triggered_by": state.last_quality_gate or "qa",
            "target_agent": target_agent,
            "next_action": next_action,
            "reason": instructions or "; ".join(issues or []),
            "issues": issues or [],
            "target_section_ids": target_section_ids,
        }

    @staticmethod
    def _target_for_action(next_action: str) -> str:
        return {
            "redo_research": "research",
            "redo_outline": "outline",
            "rewrite_section": "writer",
            "revise_editor": "editor",
            "redo_fact_check": "fact_checker",
            "redo_seo": "seo",
        }.get(next_action, "")
