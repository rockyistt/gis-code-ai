"""Loop engineering orchestration for multi-agent GIS workflow generation."""

from __future__ import annotations

from typing import Sequence

from .agents import (
    ContextManagerAgent,
    GeneratorAgent,
    PlannerAgent,
    RepairAgent,
    ReviewerAgent,
    ValidatorAgent,
    classify_validation_failure,
)
from .models import WorkflowState


class WorkflowLoop:
    """
    Coordinates planner, generator, validator, repairer, and reviewer agents.

    The loop is deliberately small: plan once, generate once, then validate/repair
    until the workflow passes checks or the repair budget is exhausted.
    """

    def __init__(
        self,
        max_steps: int = 5,
        max_repair_iterations: int = 2,
        use_rag: bool = False,
        load_llm: bool = False,
        model_quantization: str | None = None,
        model_backend: str = "transformers",
        llama_server_url: str = "http://127.0.0.1:8080",
        planner_choices: Sequence[int] | None = None,
        max_replan_iterations: int = 1,
    ):
        self.max_steps = max_steps
        self.max_repair_iterations = max(0, max_repair_iterations)
        self.max_replan_iterations = max(0, max_replan_iterations)
        self.context_manager = ContextManagerAgent()
        self.planner = PlannerAgent(max_steps=max_steps, choice_sequence=list(planner_choices or []))
        self.generator = GeneratorAgent(
            use_rag=use_rag,
            load_llm=load_llm,
            model_quantization=model_quantization,
            model_backend=model_backend,
            llama_server_url=llama_server_url,
        )
        self.validator = ValidatorAgent()
        self.repairer = RepairAgent()
        self.reviewer = ReviewerAgent()

    def run(self, prompt: str) -> WorkflowState:
        state = WorkflowState(prompt=prompt)
        state = self.context_manager.run(state)
        state = self.planner.run(state)
        state = self.generator.run(state)

        iteration = 0
        while iteration <= self.max_repair_iterations:
            state.iteration = iteration + 1
            state = self.validator.run(state)
            if not state.error_findings():
                break
            route = state.validation_route or classify_validation_failure(state.findings)
            state.validation_route = route
            if route == "repair" and iteration < self.max_repair_iterations:
                state = self.repairer.run(state)
                iteration += 1
                continue
            if route == "replan" and state.replan_attempts < self.max_replan_iterations:
                state = self._replan_and_generate(state)
                iteration = 0
                continue
            if route == "human_review" or route == "replan":
                state.status = "needs_human_review"
                state.add_trace(
                    "WorkflowLoopRouter",
                    "human_review",
                    ", ".join(finding.code for finding in state.error_findings()),
                    "Validation failure is not safe to auto-repair.",
                    {"validation_route": route},
                )
                break
            iteration += 1

        state = self.reviewer.run(state)
        return state

    def _replan_and_generate(self, state: WorkflowState) -> WorkflowState:
        state.replan_attempts += 1
        failed_codes = [finding.code for finding in state.error_findings()]
        state.add_trace(
            "WorkflowLoopRouter",
            "replan",
            ", ".join(failed_codes) or "validation failure",
            "Routing validation failure back to PlannerAgent.",
            {"replan_attempts": state.replan_attempts},
        )
        state.plan = []
        state.workflow = {}
        state.findings = []
        state.repairs = []
        state.active_template = None
        state.active_template_source = ""
        state.active_intent_index = 0
        state.generation_complete = False
        state.iteration = 0
        state.status = "draft"
        state = self.planner.run(state)
        return self.generator.run(state)
