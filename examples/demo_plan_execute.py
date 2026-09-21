#!/usr/bin/env python3
"""Plan-and-execute demo with optional human decisions at planning boundaries."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents import (  # noqa: E402
    CandidateProvider,
    ContextManagerAgent,
    LangGraphWorkflowLoop,
    ReviewerAgent,
    ValidatorAgent,
    WorkflowState,
    clean_workflow,
    write_clean_workflow,
    write_workflow_trace,
)
from src.agents.decision_support import STRUCTURAL_RECOMMENDATION_TYPES  # noqa: E402
from src.interactive.scaffolder import InteractiveScaffolder  # noqa: E402


def parse_choices(raw: str | None) -> List[int]:
    if not raw:
        return []
    return [int(part) for part in re.split(r"[,\s]+", raw.strip()) if part]


def choose_mode(cli_mode: Optional[str]) -> str:
    if cli_mode:
        return cli_mode
    if not sys.stdin.isatty():
        return "auto"
    print("Planning mode:")
    print("  1. auto - model plans and executes without asking")
    print("  2. ask  - pause at each decision and ask you to choose")
    raw = input("Choose planning mode [1/2, default=2]: ").strip()
    return "auto" if raw == "1" else "ask"


def configure_llm(scaffolder: InteractiveScaffolder, args: argparse.Namespace) -> bool:
    if not args.load_llm:
        return False
    try:
        if args.model_backend == "llama_cpp_server":
            from src.inference.llama_cpp_predictor import LlamaCppServerPredictor

            scaffolder.llm_predictor = LlamaCppServerPredictor(
                server_url=args.llama_server_url,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                top_p=args.top_p,
            )
            return True

        from src.inference.step_llm_predictor import StepLevelPredictor

        scaffolder.llm_predictor = StepLevelPredictor(
            model_dir=args.model_dir,
            verbose=False,
            quantization=args.quantization,
        )
        return True
    except Exception as exc:
        print(f"[WARN] fine-tuned model unavailable: {exc}")
        scaffolder.llm_predictor = None
        return False


def split_menu(candidates: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    primary = [candidate for candidate in candidates if candidate.get("source") != "history"]
    history = [candidate for candidate in candidates if candidate.get("source") == "history"]
    done_choice = len(primary) + 1
    return primary, history, done_choice


def print_menu(
    candidates: Sequence[Dict[str, Any]],
    anchor_step: Dict[str, Any],
    total_steps: int,
) -> int:
    primary, history, done_choice = split_menu(candidates)
    print("\n" + "=" * 80)
    print(
        f"Anchor: [{anchor_step.get('method')}] {anchor_step.get('object')} "
        f"(generated steps: {total_steps})"
    )
    print("=" * 80)
    for idx, candidate in enumerate(primary, start=1):
        print_candidate(idx, candidate)
    print(f"  {done_choice}. [DONE  ] Finish and export")
    for idx, candidate in enumerate(history, start=done_choice + 1):
        print_candidate(idx, candidate)
    print("-" * 80)
    return done_choice


def print_candidate(index: int, candidate: Dict[str, Any]) -> None:
    support = f" support={candidate.get('support_count')}" if candidate.get("support_count") else ""
    source = f" source={candidate.get('source', '')}" if candidate.get("source") else ""
    planner = f" planner={candidate.get('planner', '')}" if candidate.get("planner") else ""
    print(
        f"  {index}. [{candidate.get('method', ''):<6}] "
        f"{candidate.get('object', '')} - {candidate.get('description', '')}{source}{planner}{support}"
    )
    examples = candidate.get("examples") or []
    if examples:
        bits = [
            f"{example.get('file_id')}:{example.get('from_step')}->{example.get('to_step')}"
            for example in examples[:2]
        ]
        print(f"       examples: {', '.join(bits)}")


def resolve_choice(
    candidates: Sequence[Dict[str, Any]],
    choice: int,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    primary, history, done_choice = split_menu(candidates)
    menu = []
    for idx, candidate in enumerate(primary, start=1):
        menu.append(menu_record(idx, candidate))
    menu.append(
        {
            "choice": done_choice,
            "method": "DONE",
            "object": "",
            "type": "done",
            "description": "Finish planning",
        }
    )
    for idx, candidate in enumerate(history, start=done_choice + 1):
        menu.append(menu_record(idx, candidate))

    decision = {
        "menu": menu,
        "selected_choice": choice,
        "selected": None,
    }

    if choice == done_choice:
        decision["selected"] = {"type": "done", "description": "User-selected planning stop."}
        return None, decision
    if 1 <= choice <= len(primary):
        decision["selected"] = primary[choice - 1]
        return primary[choice - 1], decision
    if done_choice < choice <= done_choice + len(history):
        selected = history[choice - done_choice - 1]
        decision["selected"] = selected
        return selected, decision

    decision["selected"] = {
        "type": "invalid_choice",
        "description": f"Invalid choice {choice}; stopped planning.",
    }
    return None, decision


def menu_record(choice: int, candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "choice": choice,
        "method": candidate.get("method"),
        "object": candidate.get("object"),
        "type": candidate.get("type"),
        "description": candidate.get("description"),
        "source": candidate.get("source"),
        "planner": candidate.get("planner"),
        "planning_category": candidate.get("planning_category"),
        "support_count": candidate.get("support_count", 0),
        "examples": candidate.get("examples", []),
    }


def run_auto(prompt: str, args: argparse.Namespace) -> WorkflowState:
    loop = LangGraphWorkflowLoop(
        max_steps=args.max_steps,
        max_repair_iterations=args.max_repairs,
        use_rag=args.use_rag,
        load_llm=args.load_llm,
        model_quantization=args.quantization,
        model_dir=args.model_dir,
        model_backend=args.model_backend,
        llama_server_url=args.llama_server_url,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
    )
    return loop.run(prompt)


def run_ask(prompt: str, args: argparse.Namespace) -> WorkflowState:
    context_state = ContextManagerAgent().run(WorkflowState(prompt=prompt))
    effective_prompt = context_state.condensed_prompt or context_state.prompt
    scaffolder = InteractiveScaffolder()
    rag_loaded = scaffolder.load_rag_engine(args.rag_index_dir) if args.use_rag else False
    llm_loaded = configure_llm(scaffolder, args)
    provider = CandidateProvider()
    choice_queue = parse_choices(args.choices)
    decisions: List[Dict[str, Any]] = []

    initial_step = scaffolder.parse_and_create_step_one(effective_prompt, use_rag=rag_loaded)
    anchor_step = initial_step
    print_step(initial_step, "Initial step")

    while len(scaffolder.steps) < args.max_steps:
        candidates = provider.get_candidates(anchor_step["object"], anchor_step["method"])
        done_choice = print_menu(candidates, anchor_step, len(scaffolder.steps))

        if choice_queue:
            choice = choice_queue.pop(0)
            print(f"Choice from --choices: {choice}")
        else:
            raw_choice = input(
                f"Choose next action [one number, or queue like '2 4 6'; default={done_choice} DONE]: "
            ).strip()
            if raw_choice:
                try:
                    parsed_choices = parse_choices(raw_choice)
                except ValueError:
                    print(f"Invalid choice input: {raw_choice!r}. Please enter numbers separated by spaces or commas.")
                    continue
                if not parsed_choices:
                    choice = done_choice
                else:
                    choice = parsed_choices[0]
                    choice_queue = parsed_choices[1:] + choice_queue
                    if choice_queue:
                        print(f"Queued next choices: {' '.join(str(item) for item in choice_queue)}")
            else:
                choice = done_choice

        selected, decision = resolve_choice(candidates, choice)
        decision["anchor"] = {
            "method": anchor_step.get("method"),
            "object": anchor_step.get("object"),
        }
        decision["selection_source"] = "choice_sequence" if args.choices else "user"
        decisions.append(decision)

        if selected is None:
            break

        next_step = scaffolder.build_cascade_step(selected, anchor_step)
        print_step(next_step, "Executed step")
        if selected.get("type") in STRUCTURAL_RECOMMENDATION_TYPES:
            anchor_step = next_step

    workflow = json.loads(scaffolder.get_full_workflow_json())
    state = WorkflowState(
        prompt=effective_prompt,
        original_prompt=context_state.original_prompt or prompt,
        condensed_prompt=context_state.condensed_prompt,
        context_intents=list(context_state.context_intents),
        context_warnings=list(context_state.context_warnings),
        workflow=workflow,
    )
    state.traces.extend(context_state.traces)
    state.status = "generated"
    state.add_trace(
        "PlanAndExecuteController",
        "initialize",
        prompt,
        f"Created first step with rag_loaded={rag_loaded}, llm_loaded={llm_loaded}.",
    )
    state.add_trace(
        "HumanChoiceAgent",
        "choose",
        "candidate menus",
        f"Captured {len(decisions)} planning decision(s).",
        {"decisions": decisions},
    )
    state = ValidatorAgent().run(state)
    state = ReviewerAgent().run(state)
    return state


def print_step(step: Dict[str, Any], label: str) -> None:
    source = "heuristic"
    if step.get("_rag_sourced") or step.get("_is_ai_predicted"):
        source = "rag"
    if step.get("_llm_generated") or step.get("_llm_raw_template"):
        source = "fine_tuned_model"
    print(
        f"\n[{label}] step={step.get('step_index')} method={step.get('method')} "
        f"object={step.get('object')} source={source}"
    )


def print_summary(state: WorkflowState, mode: str, args: argparse.Namespace) -> None:
    print("\n" + "=" * 80)
    print(f"mode: {mode}")
    print(f"status: {state.status}")
    print(f"confidence: {state.confidence:.2f}")
    print(f"steps: {state.workflow.get('total_steps', 0)}")
    if state.findings:
        print("\nfindings:")
        for finding in state.findings:
            print(f"- {finding.severity.upper()} {finding.code}: {finding.message}")

    if args.output:
        output_path = write_clean_workflow(args.output, state.workflow)
        print(f"\nclean workflow saved: {output_path}")
    if args.trace_output:
        trace_path = write_workflow_trace(args.trace_output, state)
        print(f"trace saved: {trace_path}")

    print("\nclean workflow:")
    print(json.dumps(clean_workflow(state.workflow), indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan-and-execute GIS workflow demo.")
    parser.add_argument("prompt", nargs="*", help="Initial GIS instruction.")
    parser.add_argument("--mode", choices=["auto", "ask"], default=None)
    parser.add_argument("--choices", default=None, help="Preselected menu choices for ask mode, e.g. '2,3,6'.")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--max-repairs", type=int, default=2)
    parser.add_argument("--use-rag", action="store_true")
    parser.add_argument("--rag-index-dir", default="data/processed/rag_index")
    parser.add_argument("--load-llm", action="store_true")
    parser.add_argument("--model-dir", default="models/step-level-model-865")
    parser.add_argument("--quantization", choices=["int4", "int8"], default=None)
    parser.add_argument("--model-backend", choices=["transformers", "llama_cpp_server"], default="llama_cpp_server")
    parser.add_argument("--llama-server-url", default="http://127.0.0.1:8080")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--output", default=None)
    parser.add_argument("--trace-output", default=None)
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        if sys.stdin.isatty():
            try:
                prompt = input("Enter initial GIS instruction: ").strip()
            except EOFError:
                prompt = ""
        if not prompt:
            raise SystemExit(
                "No GIS instruction provided. Pass a prompt argument or run this script in an interactive terminal."
            )
    mode = choose_mode(args.mode)
    state = run_auto(prompt, args) if mode == "auto" else run_ask(prompt, args)
    print_summary(state, mode, args)


if __name__ == "__main__":
    main()
