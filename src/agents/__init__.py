"""
Multi-agent loop and harness layer for GIS workflow generation.

This package wraps the existing interactive scaffolder with explicit planning,
generation, validation, repair, and review agents. The default implementation is
dependency-free so it can run in local demos and tests without loading the LLM.
"""

from .agents import (
    BaseAgent,
    ContextManagerAgent,
    FallbackAgent,
    FineTunedModelAgent,
    GenerationInitializerAgent,
    GeneratorAgent,
    PlannerAgent,
    RAGAgent,
    RAGReranker,
    RepairAgent,
    ReviewerAgent,
    StepMaterializerAgent,
    ValidatorAgent,
    classify_validation_failure,
)
from .harness import HarnessCase, HarnessResult, WorkflowHarness
from .decision_support import (
    CandidateProvider,
    CrudLifecyclePlanner,
    HistoricalPatternPlanner,
    HistoricalTransitionIndex,
    PlanningContext,
    PlanningSpecialist,
    StepTemplateNormalizer,
    TopologyCascadePlanner,
    UiNavigationPlanner,
    ValidationPlanner,
)
from .exporters import (
    build_workflow_trace,
    clean_workflow,
    write_clean_workflow,
    write_workflow_trace,
)
from .langgraph_loop import LangGraphWorkflowLoop
from .loop_engine import WorkflowLoop
from .models import AgentTrace, Finding, StepIntent, WorkflowState

__all__ = [
    "AgentTrace",
    "BaseAgent",
    "CandidateProvider",
    "ContextManagerAgent",
    "CrudLifecyclePlanner",
    "FallbackAgent",
    "FineTunedModelAgent",
    "Finding",
    "GenerationInitializerAgent",
    "GeneratorAgent",
    "HarnessCase",
    "HarnessResult",
    "HistoricalPatternPlanner",
    "HistoricalTransitionIndex",
    "LangGraphWorkflowLoop",
    "PlannerAgent",
    "PlanningContext",
    "PlanningSpecialist",
    "RAGAgent",
    "RAGReranker",
    "RepairAgent",
    "ReviewerAgent",
    "StepMaterializerAgent",
    "StepTemplateNormalizer",
    "TopologyCascadePlanner",
    "UiNavigationPlanner",
    "ValidationPlanner",
    "StepIntent",
    "ValidatorAgent",
    "WorkflowHarness",
    "WorkflowLoop",
    "WorkflowState",
    "build_workflow_trace",
    "classify_validation_failure",
    "clean_workflow",
    "write_clean_workflow",
    "write_workflow_trace",
]
