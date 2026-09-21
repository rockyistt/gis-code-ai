#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_interactive.py - Interactive multi-step GIS workflow generator demo.

Combines:
  1) Single-step RAG semantic prediction against the curated 865-entry index
  2) Topology-driven cascading recommendations
  3) Automatic foreign-key / parent-ID propagation
"""

import sys
import os
import json
import re
from pathlib import Path

# Fix Windows terminal UTF-8 encoding when piping or redirecting
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Add project root to python path
sys.path.append(str(Path(__file__).parent.parent))

from src.interactive.scaffolder import TopologyEngine, InteractiveScaffolder


def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    print("""
================================================================================
             GIS CO-OCCURRENCE & TOPOLOGY CONTEXT SCAFFOLDER
================================================================================
  Hybrid engine driven by 4,000+ real workflow files. Capabilities:
    1. Free-form natural-language input -> RAG semantic step prediction
    2. Topology-aware cascade recommendations (e.g. Rail -> Veld -> Geleider)
    3. Automatic parent-ID and foreign-key context propagation
    4. One-shot export of a runnable multi-step JSON script
================================================================================
""")


def main():
    clear_console()
    print_banner()

    scaffolder = InteractiveScaffolder()

    # Load the RAG index (865 unique instruction/step pairs distilled from 40,209 steps)
    # NOTE: RAG loading may hang on first run when downloading SentenceTransformer model.
    # For now, we disable it and use regex fallback only.
    print("[INFO] RAG semantic index disabled (to prevent hangs on first run).")
    print("[INFO] Using lightweight regex parser instead.")
    use_rag = False  # Disable RAG to avoid hangs
    
    # Load the step-level LLM predictor (lazy, will be loaded on first use)
    print("[INFO] LLM predictor disabled (to prevent hangs).")
    use_llm = False  # Disable LLM by default to avoid hangs
    print("[OK]   Using topology engine + regex fallback for step generation.")
    
    print("-" * 80)

    # 1. First-step prompt
    print("[STEP 1] Enter your first GIS instruction (free-form natural language).")
    print("  Example (AI semantic):   Open a transformer and load its geometry in elektra")
    print("  Example (asset create):  Create E MS Installatie FP where Name is Amsterdam_Substation")
    print("  Example (spatial tree):  Create a building on site space in stationcomplex")
    print("-" * 80)

    first_input = input("Your instruction: ").strip()
    if not first_input:
        first_input = "Create E MS Installatie FP"
        print(f"(Empty input detected -> using demo default: {first_input})")

    print("\n[INFO] Running hybrid RAG retrieval to predict the initial JSON step...")
    initial_step = scaffolder.parse_and_create_step_one(first_input, use_rag=use_rag)

    print("\n[OK] Step 0 predicted and assembled:")
    print(f"     Action   = {initial_step['method']}")
    print(f"     Database = {initial_step['database']}")
    print(f"     Object   = {initial_step['object']}")
    print(f"     ID       = {initial_step['object_id']}")
    if initial_step.get("_is_ai_predicted"):
        print(f"     RAG source -> \"{initial_step['_matched_instruction']}\"")
    print("-" * 80)

    current_step = initial_step
    # Anchor = the most recent Create/Open step. The menu is always generated
    # against the anchor, so the option numbering stays stable even after the
    # user injects Update/Delete/Run/Switch steps. This guarantees that a batch
    # input like "2,3,4,5" produces exactly 4 cascade steps.
    anchor_step = initial_step

    # 2. Cascading topology loop
    workflow_finished = False
    choice_queue = []

    while not workflow_finished:
        anchor_obj = anchor_step["object"]
        anchor_method = anchor_step["method"]

        recs = TopologyEngine.get_downstream_recommendations(anchor_obj, anchor_method)

        # Only print the menu when the planning queue is empty
        if not choice_queue:
            print("\n" + "=" * 80)
            print(f"Anchor step: [{anchor_obj}]  method=[{anchor_method}]   (total generated: {len(scaffolder.steps)})")
            print("=" * 80)
            print("Recommended actions (menu stays stable around the anchor):")
            print("-" * 80)

            for idx, rec in enumerate(recs, 1):
                print(f"  {idx}. [{rec['method']:6}] -> {rec['description']}")
            print(f"  {len(recs)+1}. [DONE  ] -> Finish and export the full multi-step JSON")
            print("-" * 80)

            user_input = input(
                f"Choose next action [single (e.g. 1) or chained path (e.g. 1,1,1,6)]: "
            ).strip()
            if not user_input:
                user_input = str(len(recs) + 1)
                print(f"(Empty input -> defaulting to {user_input}: DONE)")

            parts = re.split(r'[,\s]+', user_input)
            choice_queue.extend([p for p in parts if p])

        if not choice_queue:
            choice_queue.append(str(len(recs) + 1))

        current_choice = choice_queue.pop(0)

        try:
            choice_idx = int(current_choice) - 1

            if choice_idx == len(recs):
                print(f"\n[DONE] Planning step '{current_choice}' = finish & export.")
                workflow_finished = True
                break

            if 0 <= choice_idx < len(recs):
                chosen_rec = recs[choice_idx]
                print(f"\n[EXEC] Applying choice {choice_idx+1}: [{chosen_rec['method']}] {chosen_rec['description']}")
                print(f"       Propagating parent-ID and foreign-key relations...")
                next_step = scaffolder.build_cascade_step(chosen_rec, anchor_step)

                print(f"[OK]   Step {next_step['step_index']} assembled.")
                print(f"       Action={next_step['method']}  Object={next_step['object']}  Target ID={next_step['object_id']}")
                if next_step.get("_rag_sourced"):
                    print(f"       Template from RAG source -> \"{next_step['_matched_instruction']}\"")
                elif next_step.get("_llm_generated"):
                    print(f"       Template from step-level LLM prediction -> \"{next_step.get('_llm_instruction', 'N/A')}\"")
                else:
                    print(f"       Template from heuristic fallback (no RAG match).")
                if "test_data" in next_step and next_step["test_data"]:
                    print(f"       test_data: {json.dumps(next_step['test_data'], ensure_ascii=False)}")

                current_step = next_step
                # Only advance the anchor when the new step is a Create/Open of a
                # downstream physical object. Update / Delete / Run / Switch steps
                # are "side actions" and must not move the anchor, otherwise the
                # menu numbering would shift mid-batch.
                if chosen_rec.get("type") in (
                    "physical_cascade", "spatial_cascade", "cable_splice_association"
                ):
                    anchor_step = next_step
            else:
                print(f"[SKIP] Invalid choice '{current_choice}': out of menu range 1-{len(recs)+1}")
                choice_queue.clear()
        except ValueError:
            print(f"[SKIP] Invalid choice '{current_choice}': must be an integer")
            choice_queue.clear()

    # 3. Final export
    print("\n" + "=" * 80)
    print("[DONE] Multi-step GIS workflow assembled successfully.")
    print("=" * 80)
    print("\nFull multi-step JSON script:")
    print("-" * 80)

    full_json = scaffolder.get_full_workflow_json()
    print(full_json)

    output_path = Path("data/processed/interactive_scaffolded_workflow.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_json)

    print("-" * 80)
    print(f"[SAVED] Workflow written to: data/processed/interactive_scaffolded_workflow.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
