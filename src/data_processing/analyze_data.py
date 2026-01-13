"""
Analyze parsed workflow data and generate statistics.
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_workflows(workflows_path: str):
    """Analyze parsed workflows and print statistics."""
    
    workflows = []
    with open(workflows_path, 'r', encoding='utf-8') as f:
        for line in f:
            workflows.append(json.loads(line))
    
    logger.info(f"Total workflows: {len(workflows)}")
    
    # Basic stats
    high_quality = sum(1 for w in workflows if w['is_high_quality'])
    logger.info(f"High quality (template): {high_quality}")
    logger.info(f"Regular quality: {len(workflows) - high_quality}")
    
    # Steps distribution
    step_counts = [w['total_steps'] for w in workflows]
    step_counter = Counter(step_counts)
    logger.info(f"\nSteps distribution:")
    for steps, count in sorted(step_counter.items())[:10]:
        logger.info(f"  {steps} steps: {count} workflows")
    
    # Average steps
    avg_steps = sum(step_counts) / len(step_counts)
    logger.info(f"Average steps per workflow: {avg_steps:.2f}")
    
    # Applications
    apps = [w['test_app'] for w in workflows]
    app_counter = Counter(apps)
    logger.info(f"\nTop applications:")
    for app, count in app_counter.most_common(5):
        logger.info(f"  {app}: {count}")
    
    # Modules
    all_modules = []
    for w in workflows:
        for step in w['steps']:
            all_modules.append(step['module'])
    
    module_counter = Counter(all_modules)
    logger.info(f"\nTop modules:")
    for module, count in module_counter.most_common(10):
        logger.info(f"  {module}: {count}")
    
    # Methods
    all_methods = []
    for w in workflows:
        for step in w['steps']:
            all_methods.append(step['method'])
    
    method_counter = Counter(all_methods)
    logger.info(f"\nTop methods:")
    for method, count in method_counter.most_common(10):
        logger.info(f"  {method}: {count}")
    
    # Objects
    all_objects = []
    for w in workflows:
        for step in w['steps']:
            if step['object'] and step['object'] != 'Passed':
                all_objects.append(step['object'])
    
    object_counter = Counter(all_objects)
    logger.info(f"\nTop objects:")
    for obj, count in object_counter.most_common(10):
        logger.info(f"  {obj}: {count}")
    
    # Pattern analysis: Open -> Create
    open_create_patterns = 0
    for w in workflows:
        for i in range(len(w['steps']) - 1):
            if (w['steps'][i]['method'] == 'Open Object' and 
                w['steps'][i+1]['method'] == 'Create'):
                open_create_patterns += 1
    
    logger.info(f"\n'Open Object -> Create' patterns: {open_create_patterns}")
    
    # Empty steps (all test_data empty)
    empty_steps = 0
    total_steps = 0
    for w in workflows:
        for step in w['steps']:
            total_steps += 1
            if (not step['test_data']['create'] and 
                not step['test_data']['update'] and 
                not step['test_data']['editor']):
                empty_steps += 1
    
    logger.info(f"\nEmpty steps (no test data): {empty_steps}/{total_steps} ({empty_steps/total_steps*100:.1f}%)")
    
    # Save summary
    summary = {
        "total_workflows": len(workflows),
        "high_quality_count": high_quality,
        "avg_steps": round(avg_steps, 2),
        "top_apps": dict(app_counter.most_common(5)),
        "top_modules": dict(module_counter.most_common(10)),
        "top_methods": dict(method_counter.most_common(10)),
        "top_objects": dict(object_counter.most_common(10)),
        "open_create_patterns": open_create_patterns,
        "empty_steps_ratio": round(empty_steps/total_steps, 3)
    }
    
    summary_path = Path(workflows_path).parent / "data_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    analyze_workflows("data/processed/parsed_workflows.jsonl")
