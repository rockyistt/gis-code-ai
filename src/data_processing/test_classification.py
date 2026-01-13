"""
Test the updated instruction generator with module classification (no API calls).
"""

import json
import sys
sys.path.insert(0, 'src')

from data_processing.instruction_generator import InstructionGenerator, NAVIGATION_MODULES, DATA_RICH_MODULES


def test_step_classification():
    """Test step classification logic without API calls."""
    
    # Load first template workflow
    with open("data/processed/parsed_workflows.jsonl", 'r', encoding='utf-8') as f:
        workflow = json.loads(f.readline())
    
    print("=" * 80)
    print(f"📋 Testing workflow: {workflow['file_id']}")
    print(f"⭐ High quality: {workflow['is_high_quality']}")
    print(f"🔢 Total steps: {workflow['total_steps']}")
    print("=" * 80)
    print()
    
    # Create generator (we won't call API, just test classification)
    generator = InstructionGenerator(provider="openai", api_key="test")
    
    # Test each step
    navigation_count = 0
    data_rich_count = 0
    empty_count = 0
    
    for step in workflow['steps']:
        step_type = generator._classify_step(step)
        
        if step_type in ["navigation", "validation"]:
            navigation_count += 1
            icon = "🔵"
        elif step_type == "empty":
            empty_count += 1
            icon = "⚪"
        else:
            data_rich_count += 1
            icon = "🟢"
        
        print(f"{icon} Step {step['step_index']}: {step_type.upper()}")
        print(f"   Module: {step['module']}")
        print(f"   Method: {step['method']}")
        print(f"   Object: {step['object']}")
        
        # Show what instruction would be generated
        if step_type in ["navigation", "validation"]:
            if step['method'] == "Select Tab":
                instruction = f"Select the {step['object']} tab."
            elif step['method'] == "Click Oneshot Button":
                instruction = f"Click the {step['object']} button."
            else:
                instruction = f"Perform datamodel consistency check on {step['object']}."
            print(f"   💬 Template instruction: \"{instruction}\"")
        else:
            # Get context
            if step['step_index'] > 0:
                context_steps = generator._get_context_steps(workflow, step['step_index'])
                context_str = generator._format_context(context_steps)
                print(f"   📝 Context: {context_str}")
            print(f"   💬 Would generate detailed LLM instruction (with API)")
        
        print()
    
    print("=" * 80)
    print("📊 Classification Summary")
    print("=" * 80)
    print(f"🔵 Navigation/Validation steps: {navigation_count}/{workflow['total_steps']} ({navigation_count/workflow['total_steps']*100:.1f}%)")
    print(f"🟢 Data-rich steps: {data_rich_count}/{workflow['total_steps']} ({data_rich_count/workflow['total_steps']*100:.1f}%)")
    print(f"⚪ Empty steps: {empty_count}/{workflow['total_steps']} ({empty_count/workflow['total_steps']*100:.1f}%)")
    print("=" * 80)
    print()
    
    print("💡 Strategy:")
    print(f"  - {navigation_count} steps will use template instructions (no API cost)")
    print(f"  - {data_rich_count} steps will call LLM with context (API cost)")
    print(f"  - {empty_count} steps will be skipped if skip_navigation=True")
    print()
    
    # Test with a regular workflow
    print("\n" + "=" * 80)
    print("📋 Testing regular workflow (non-template)")
    print("=" * 80)
    print()
    
    with open("data/processed/parsed_workflows.jsonl", 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i == 12:  # Skip templates, get first regular workflow
                regular_workflow = json.loads(line)
                break
    
    print(f"📋 Workflow: {regular_workflow['file_id']}")
    print(f"⭐ High quality: {regular_workflow['is_high_quality']}")
    print(f"🔢 Total steps: {regular_workflow['total_steps']}")
    print()
    
    nav_count = 0
    data_count = 0
    
    for step in regular_workflow['steps']:
        step_type = generator._classify_step(step)
        if step_type in ["navigation", "validation", "empty"]:
            nav_count += 1
        else:
            data_count += 1
    
    print(f"🔵 Navigation/Empty: {nav_count}/{regular_workflow['total_steps']} ({nav_count/regular_workflow['total_steps']*100:.1f}%)")
    print(f"🟢 Data-rich: {data_count}/{regular_workflow['total_steps']} ({data_count/regular_workflow['total_steps']*100:.1f}%)")
    print()
    print(f"💰 Cost estimation:")
    print(f"  - If skip_navigation=True: {data_count} LLM calls")
    print(f"  - If skip_navigation=False: {regular_workflow['total_steps']} instructions ({nav_count} templates + {data_count} LLM)")


if __name__ == "__main__":
    test_step_classification()
