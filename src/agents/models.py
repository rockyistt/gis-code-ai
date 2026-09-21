"""Shared data models for the multi-agent workflow loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


VALID_METHODS = {
    "Create",
    "Update",
    "Delete",
    "Click Oneshot Button",
    "Datamodel Check",
    "Open",
    "Open Object",
    "Open Object with ID",
    "Run",
    "Select Tab",
    "Select first HV object",
    "Select second HV object",
    "Switch",
    "Switch Spatial Context",
    "Verify",
    "Verify Field",
}

REQUIRED_STEP_KEYS = {
    "step_index",
    "database",
    "object",
    "object_id",
    "module",
    "method",
    "command",
    "test_data",
}


@dataclass
class StepIntent:
    """A high-level planned operation before concrete JSON is generated."""

    method: str
    object: str
    reason: str = ""
    source: str = "planner"


@dataclass
class Finding:
    """Validation or review finding emitted by an agent."""

    severity: str
    code: str
    message: str
    step_index: Optional[int] = None

    @property
    def is_error(self) -> bool:
        return self.severity.lower() == "error"


@dataclass
class AgentTrace:
    """Compact trace record for explaining the agent collaboration."""

    agent: str
    action: str
    input_summary: str
    output_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowState:
    """Mutable state passed through the loop."""

    prompt: str
    original_prompt: str = ""
    condensed_prompt: str = ""
    context_intents: List[StepIntent] = field(default_factory=list)
    context_warnings: List[str] = field(default_factory=list)
    plan: List[StepIntent] = field(default_factory=list)
    workflow: Dict[str, Any] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)
    repairs: List[str] = field(default_factory=list)
    traces: List[AgentTrace] = field(default_factory=list)
    iteration: int = 0
    status: str = "draft"
    confidence: float = 0.0
    active_intent_index: int = 0
    active_template: Optional[Dict[str, Any]] = None
    active_template_source: str = ""
    generation_complete: bool = False
    replan_attempts: int = 0
    validation_route: str = ""
    generation_config: Dict[str, Any] = field(default_factory=dict)
    runtime: Dict[str, Any] = field(default_factory=dict)

    def error_findings(self) -> List[Finding]:
        return [finding for finding in self.findings if finding.is_error]

    def add_trace(
        self,
        agent: str,
        action: str,
        input_summary: str,
        output_summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.traces.append(
            AgentTrace(
                agent=agent,
                action=action,
                input_summary=input_summary,
                output_summary=output_summary,
                metadata=metadata or {},
            )
        )
