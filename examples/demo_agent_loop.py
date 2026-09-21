#!/usr/bin/env python3
"""Demo: multi-agent loop for GIS workflow generation."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents import (
    LangGraphWorkflowLoop,
    WorkflowLoop,
    build_workflow_trace,
    clean_workflow,
    write_clean_workflow,
    write_workflow_trace,
)
from demo_plan_execute import run_ask


def parse_choices(raw: str | None) -> list[int]:
    if not raw:
        return []
    choices: list[int] = []
    for part in re.split(r"[,\s]+", raw.strip()):
        if part:
            choices.append(int(part))
    return choices


def resolve_prompt(raw_parts: list[str]) -> str:
    prompt = " ".join(raw_parts).strip()
    if prompt:
        return prompt
    if sys.stdin.isatty():
        try:
            user_prompt = input("Enter initial GIS instruction: ").strip()
        except EOFError:
            user_prompt = ""
        if user_prompt:
            return user_prompt
        raise SystemExit("No GIS instruction provided.")
    raise SystemExit("No GIS instruction provided. Pass a prompt argument or run this script in an interactive terminal.")


def resolve_planning_mode(raw_mode: str | None) -> str:
    if raw_mode:
        return raw_mode
    if sys.stdin.isatty():
        print("Planning mode:")
        print("  1. auto - agents generate the workflow in one pass")
        print("  2. ask  - pause at each decision and ask for your choice")
        selected = input("Choose planning mode [1/2, default=2]: ").strip()
        return "auto" if selected == "1" else "ask"
    return "auto"


def print_planning_decisions(state) -> None:
    planner_traces = [trace for trace in state.traces if trace.agent == "PlannerAgent"]
    if not planner_traces:
        return
    decisions = planner_traces[-1].metadata.get("decisions", [])
    if not decisions:
        return

    print("\nplanning decisions:")
    for idx, decision in enumerate(decisions, start=1):
        anchor = decision.get("anchor", {})
        source = decision.get("selection_source", "auto")
        selected_choice = decision.get("selected_choice")
        selected = decision.get("selected") or {}
        print(
            f"- decision {idx}: anchor=[{anchor.get('method')} {anchor.get('object')}] "
            f"choice={selected_choice} source={source}"
        )
        for item in decision.get("menu", []):
            marker = "*" if item.get("choice") == selected_choice else " "
            support = (
                f" support={item.get('support_count')}"
                if item.get("support_count")
                else ""
            )
            source = f" source={item.get('source')}" if item.get("source") else ""
            planner = f" planner={item.get('planner')}" if item.get("planner") else ""
            print(
                f"  {marker} {item.get('choice')}. [{item.get('method')}] "
                f"{item.get('object')} - {item.get('description')}{source}{planner}{support}"
            )
            examples = item.get("examples") or []
            if examples:
                example_bits = [
                    f"{ex.get('file_id')}:{ex.get('from_step')}->{ex.get('to_step')}"
                    for ex in examples[:2]
                ]
                print(f"      examples: {', '.join(example_bits)}")
        if selected:
            print(f"  selected: {selected.get('type')} -> {selected.get('description')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GIS multi-agent workflow loop.")
    parser.add_argument("prompt", nargs="*", help="Initial GIS instruction.")
    parser.add_argument(
        "--engine",
        choices=["native", "langgraph"],
        default="native",
        help="Loop implementation to use.",
    )
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--max-repairs", type=int, default=2)
    parser.add_argument(
        "--planning-mode",
        choices=["auto", "ask"],
        default=None,
        help="auto generates in one pass; ask pauses at each planning decision.",
    )
    parser.add_argument(
        "--choices",
        default=None,
        help="Comma/space-separated topology menu choices, e.g. '1,2,6'. The last menu item is DONE.",
    )
    parser.add_argument("--show-decisions", action="store_true", help="Print planner menus and selected choices.")
    parser.add_argument("--use-rag", action="store_true", help="Load the local RAG index.")
    parser.add_argument("--load-llm", action="store_true", help="Load the fine-tuned local model as fallback.")
    parser.add_argument(
        "--quantization",
        choices=["int4", "int8"],
        default=None,
        help="Optional model quantization for the LLM fallback.",
    )
    parser.add_argument(
        "--model-backend",
        choices=["transformers", "llama_cpp_server"],
        default="transformers",
        help="Fine-tuned model backend used when --load-llm is enabled.",
    )
    parser.add_argument(
        "--llama-server-url",
        default="http://127.0.0.1:8080",
        help="llama.cpp server URL for --model-backend llama_cpp_server.",
    )
    parser.add_argument("--rag-index-dir", default="data/processed/rag_index")
    parser.add_argument("--model-dir", default="models/step-level-model-865")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument(
        "--show-debug-fields",
        action="store_true",
        help="Print the raw internal workflow instead of the clean exported workflow.",
    )
    parser.add_argument(
        "--show-agent-trace",
        action="store_true",
        help="Print internal agent trace summaries.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the final workflow JSON.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path for the clean workflow JSON output.",
    )
    parser.add_argument(
        "--trace-output",
        default=None,
        help="Optional path for the provenance/agent trace JSON output.",
    )
    args = parser.parse_args()

    prompt = resolve_prompt(args.prompt)
    planning_mode = resolve_planning_mode(args.planning_mode)
    planner_choices = parse_choices(args.choices)
    if planning_mode == "ask":
        state = run_ask(prompt, args)
    elif args.engine == "langgraph":
        loop = LangGraphWorkflowLoop(
            max_steps=args.max_steps,
            max_repair_iterations=args.max_repairs,
            use_rag=args.use_rag,
            load_llm=args.load_llm,
            model_quantization=args.quantization,
            rag_index_dir=args.rag_index_dir,
            model_dir=args.model_dir,
            model_backend=args.model_backend,
            llama_server_url=args.llama_server_url,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            planner_choices=planner_choices,
        )
        state = loop.run(prompt)
    else:
        loop = WorkflowLoop(
            max_steps=args.max_steps,
            max_repair_iterations=args.max_repairs,
            use_rag=args.use_rag,
            load_llm=args.load_llm,
            model_quantization=args.quantization,
            model_backend=args.model_backend,
            llama_server_url=args.llama_server_url,
            planner_choices=planner_choices,
        )
        state = loop.run(prompt)

    workflow_for_display = state.workflow if args.show_debug_fields else clean_workflow(state.workflow)

    if args.json_only:
        print(json.dumps(workflow_for_display, indent=2, ensure_ascii=False))
        return

    print(f"engine: {args.engine}")
    print(f"planning_mode: {planning_mode}")
    print(f"prompt: {prompt}")
    print(f"status: {state.status}")
    print(f"confidence: {state.confidence:.2f}")
    print(f"steps: {state.workflow.get('total_steps', 0)}")

    if args.show_agent_trace:
        print("\nagent trace:")
        for trace in state.traces:
            print(f"- {trace.agent}: {trace.output_summary}")

    if args.show_decisions or planner_choices:
        print_planning_decisions(state)

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

    print("\nworkflow:")
    print(json.dumps(workflow_for_display, indent=2, ensure_ascii=False))

    if args.show_debug_fields:
        print("\ntrace:")
        print(json.dumps(build_workflow_trace(state), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
