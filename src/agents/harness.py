"""Harness engineering utilities for repeatable workflow-loop evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .loop_engine import WorkflowLoop
from .models import Finding, WorkflowState


@dataclass
class HarnessCase:
    """A scenario-level check for the multi-agent workflow loop."""

    name: str
    prompt: str
    min_steps: int = 1
    required_objects: List[str] = field(default_factory=list)
    required_methods: List[str] = field(default_factory=list)


@dataclass
class HarnessResult:
    """Result for one harness case."""

    case: HarnessCase
    state: WorkflowState
    passed: bool
    findings: List[Finding]


class WorkflowHarness:
    """Runs repeatable scenario checks against the workflow loop."""

    def __init__(self, loop: Optional[WorkflowLoop] = None):
        self.loop = loop or WorkflowLoop()

    def run_case(self, case: HarnessCase) -> HarnessResult:
        state = self.loop.run(case.prompt)
        findings = list(state.findings)
        steps = state.workflow.get("steps", []) if isinstance(state.workflow, dict) else []

        if len(steps) < case.min_steps:
            findings.append(
                Finding(
                    "error",
                    "harness_min_steps",
                    f"Expected at least {case.min_steps} steps, got {len(steps)}.",
                )
            )

        objects = {step.get("object") for step in steps if isinstance(step, dict)}
        for required_object in case.required_objects:
            if required_object not in objects:
                findings.append(
                    Finding(
                        "error",
                        "harness_missing_object",
                        f"Missing required object: {required_object}.",
                    )
                )

        methods = {step.get("method") for step in steps if isinstance(step, dict)}
        for required_method in case.required_methods:
            if required_method not in methods:
                findings.append(
                    Finding(
                        "error",
                        "harness_missing_method",
                        f"Missing required method: {required_method}.",
                    )
                )

        passed = state.status == "ready" and not any(finding.is_error for finding in findings)
        return HarnessResult(case=case, state=state, passed=passed, findings=findings)

    def run_cases(self, cases: Iterable[HarnessCase]) -> Dict[str, Any]:
        results = [self.run_case(case) for case in cases]
        passed_count = sum(1 for result in results if result.passed)
        return {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "pass_rate": passed_count / len(results) if results else 0.0,
            "results": results,
        }
