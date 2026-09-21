"""Optional LangGraph orchestration for the GIS multi-agent loop."""

from __future__ import annotations

from typing import Literal, Sequence, TypedDict

from .agents import (
    ContextManagerAgent,
    FallbackAgent,
    FineTunedModelAgent,
    GenerationInitializerAgent,
    PlannerAgent,
    RAGAgent,
    RepairAgent,
    ReviewerAgent,
    StepMaterializerAgent,
    ValidatorAgent,
    classify_validation_failure,
)
from .models import WorkflowState


class LangGraphLoopState(TypedDict, total=False):
    """State payload passed between LangGraph nodes."""

    workflow_state: WorkflowState


class LangGraphWorkflowLoop:
    """
    LangGraph-backed version of the workflow generator.

    The graph exposes the generation fallback chain explicitly:

    plan -> init_generation -> rag -> fine_tuned_model -> fallback
    -> materialize -> next step or validate -> repair/review
    """

    def __init__(
        self,
        max_steps: int = 5,
        max_repair_iterations: int = 2,
        use_rag: bool = False,
        load_llm: bool = False,
        model_quantization: str | None = None,
        rag_index_dir: str = "data/processed/rag_index",
        model_dir: str = "models/step-level-model-865",
        model_backend: str = "transformers",
        llama_server_url: str = "http://127.0.0.1:8080",
        max_tokens: int = 512,
        temperature: float = 0.0,
        top_p: float = 1.0,
        planner_choices: Sequence[int] | None = None,
        max_replan_iterations: int = 1,
    ):
        self.max_steps = max_steps
        self.max_repair_iterations = max(0, max_repair_iterations)
        self.max_replan_iterations = max(0, max_replan_iterations)
        self.use_rag = use_rag
        self.load_llm = load_llm
        self.model_quantization = model_quantization
        self.rag_index_dir = rag_index_dir
        self.model_dir = model_dir
        self.model_backend = model_backend
        self.llama_server_url = llama_server_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.runtime = {}

        self.context_manager = ContextManagerAgent()
        self.planner = PlannerAgent(max_steps=max_steps, choice_sequence=list(planner_choices or []))
        self.initializer = GenerationInitializerAgent(self.runtime)
        self.rag_agent = RAGAgent(self.runtime)
        self.fine_tuned_model_agent = FineTunedModelAgent(self.runtime)
        self.fallback_agent = FallbackAgent()
        self.materializer = StepMaterializerAgent(self.runtime)
        self.validator = ValidatorAgent()
        self.repairer = RepairAgent()
        self.reviewer = ReviewerAgent()
        self._graph = None

    def run(self, prompt: str) -> WorkflowState:
        graph = self._compiled_graph()
        self.runtime.clear()
        state = WorkflowState(prompt=prompt)
        state.generation_config = {
            "use_rag": self.use_rag,
            "load_llm": self.load_llm,
            "rag_index_dir": self.rag_index_dir,
            "model_dir": self.model_dir,
            "model_quantization": self.model_quantization,
            "model_backend": self.model_backend,
            "llama_server_url": self.llama_server_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        result = graph.invoke({"workflow_state": state})
        return result["workflow_state"]

    def _compiled_graph(self):
        if self._graph is not None:
            return self._graph

        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise ImportError(
                "LangGraphWorkflowLoop requires langgraph. "
                "Install optional dependencies with: pip install -r requirements-langgraph.txt"
            ) from exc

        builder = StateGraph(LangGraphLoopState)
        builder.add_node("context", self._context)
        builder.add_node("plan", self._plan)
        builder.add_node("init_generation", self._init_generation)
        builder.add_node("rag", self._rag)
        builder.add_node("fine_tuned_model", self._fine_tuned_model)
        builder.add_node("fallback", self._fallback)
        builder.add_node("materialize", self._materialize)
        builder.add_node("validate", self._validate)
        builder.add_node("repair", self._repair)
        builder.add_node("replan", self._replan)
        builder.add_node("human_review", self._human_review)
        builder.add_node("review", self._review)

        builder.add_edge(START, "context")
        builder.add_edge("context", "plan")
        builder.add_edge("plan", "init_generation")
        builder.add_edge("init_generation", "rag")
        builder.add_conditional_edges(
            "rag",
            self._route_after_rag,
            {
                "materialize": "materialize",
                "fine_tuned_model": "fine_tuned_model",
                "fallback": "fallback",
            },
        )
        builder.add_conditional_edges(
            "fine_tuned_model",
            self._route_after_fine_tuned_model,
            {
                "materialize": "materialize",
                "fallback": "fallback",
            },
        )
        builder.add_edge("fallback", "materialize")
        builder.add_conditional_edges(
            "materialize",
            self._route_after_materialize,
            {
                "rag": "rag",
                "validate": "validate",
            },
        )
        builder.add_conditional_edges(
            "validate",
            self._route_after_validation,
            {
                "repair": "repair",
                "replan": "replan",
                "human_review": "human_review",
                "review": "review",
            },
        )
        builder.add_edge("repair", "validate")
        builder.add_edge("replan", "init_generation")
        builder.add_edge("human_review", "review")
        builder.add_edge("review", END)

        self._graph = builder.compile()
        return self._graph

    def _state(self, payload: LangGraphLoopState) -> WorkflowState:
        state = payload.get("workflow_state")
        if state is None:
            raise ValueError("LangGraph payload is missing workflow_state.")
        return state

    def _plan(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.planner.run(self._state(payload))}

    def _context(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.context_manager.run(self._state(payload))}

    def _init_generation(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.initializer.run(self._state(payload))}

    def _rag(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.rag_agent.run(self._state(payload))}

    def _fine_tuned_model(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.fine_tuned_model_agent.run(self._state(payload))}

    def _fallback(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.fallback_agent.run(self._state(payload))}

    def _materialize(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.materializer.run(self._state(payload))}

    def _validate(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        state = self._state(payload)
        state.iteration += 1
        return {"workflow_state": self.validator.run(state)}

    def _repair(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.repairer.run(self._state(payload))}

    def _replan(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        state = self._state(payload)
        state.replan_attempts += 1
        failed_codes = [finding.code for finding in state.error_findings()]
        state.add_trace(
            "LangGraphRouter",
            "replan",
            ", ".join(failed_codes) or "validation failure",
            "Routing validation failure back to PlannerAgent.",
            {
                "replan_attempts": state.replan_attempts,
                "contract": {
                    "outcome": "replan_requested",
                    "reason": "semantic_or_planning_validation_failure",
                    "next": "plan",
                },
            },
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
        return {"workflow_state": self.planner.run(state)}

    def _human_review(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        state = self._state(payload)
        state.status = "needs_human_review"
        state.add_trace(
            "LangGraphRouter",
            "human_review",
            ", ".join(finding.code for finding in state.error_findings()) or "ambiguous failure",
            "Validation failure is not safe to auto-repair.",
            {
                "validation_route": state.validation_route,
                "contract": {
                    "outcome": "human_review_required",
                    "reason": "ambiguous_or_replan_budget_exhausted",
                    "next": "review",
                },
            },
        )
        return {"workflow_state": state}

    def _review(self, payload: LangGraphLoopState) -> LangGraphLoopState:
        return {"workflow_state": self.reviewer.run(self._state(payload))}

    def _route_after_rag(
        self,
        payload: LangGraphLoopState,
    ) -> Literal["materialize", "fine_tuned_model", "fallback"]:
        state = self._state(payload)
        if state.active_template is not None:
            return "materialize"
        if state.generation_config.get("load_llm", False):
            return "fine_tuned_model"
        return "fallback"

    def _route_after_fine_tuned_model(
        self,
        payload: LangGraphLoopState,
    ) -> Literal["materialize", "fallback"]:
        state = self._state(payload)
        if state.active_template is not None:
            return "materialize"
        return "fallback"

    def _route_after_materialize(
        self,
        payload: LangGraphLoopState,
    ) -> Literal["rag", "validate"]:
        state = self._state(payload)
        return "validate" if state.generation_complete else "rag"

    def _route_after_validation(
        self,
        payload: LangGraphLoopState,
    ) -> Literal["repair", "replan", "human_review", "review"]:
        state = self._state(payload)
        if not state.error_findings():
            return "review"
        route = state.validation_route or classify_validation_failure(state.findings)
        state.validation_route = route
        if route == "repair" and state.iteration <= self.max_repair_iterations:
            return "repair"
        if route == "replan" and state.replan_attempts < self.max_replan_iterations:
            return "replan"
        return "human_review"
