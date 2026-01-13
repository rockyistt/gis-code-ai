"""
Display a workflow with empty steps visualization.
"""

import json
import sys

def visualize_workflow(workflow_file: str, workflow_index: int = 12):
    """Display a workflow showing which steps have data and which are empty."""
    
    with open(workflow_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i == workflow_index:
                workflow = json.loads(line)
                break
    
    print("=" * 80)
    print(f"📋 工作流: {workflow['file_id']}")
    print(f"📱 应用: {workflow['test_app']}")
    print(f"🔢 总步骤数: {workflow['total_steps']}")
    print(f"⭐ 高质量: {'是' if workflow['is_high_quality'] else '否'}")
    print("=" * 80)
    print()
    
    empty_count = 0
    has_data_count = 0
    
    for step in workflow['steps']:
        step_num = step['step_index']
        module = step['module']
        method = step['method']
        obj = step['object']
        
        # Check if step has any data
        has_create = bool(step['test_data']['create'])
        has_update = bool(step['test_data']['update'])
        has_editor = bool(step['test_data']['editor'])
        
        has_any_data = has_create or has_update or has_editor
        
        if has_any_data:
            has_data_count += 1
            status = "✅ 有数据"
            color = ""
        else:
            empty_count += 1
            status = "⚪ 空步骤"
            color = ""
        
        print(f"步骤 {step_num}: {status}")
        print(f"  模块: {module}")
        print(f"  方法: {method}")
        print(f"  对象: {obj}")
        
        if has_any_data:
            data_types = []
            if has_create:
                data_types.append("create")
            if has_update:
                data_types.append("update")
            if has_editor:
                data_types.append("editor")
            print(f"  📦 包含数据: {', '.join(data_types)}")
            
            # Show sample of editor data if present
            if has_editor:
                editor_data = step['test_data']['editor']
                if 'FLD_CSTM0_' + str(step_num) in editor_data:
                    custom_data = editor_data['FLD_CSTM0_' + str(step_num)]
                    print(f"  💾 示例字段: {list(custom_data.keys())[:3]}")
        else:
            print(f"  ⚠️  三个数据字段都为空")
        
        print()
    
    print("=" * 80)
    print("📊 总结")
    print(f"  有数据的步骤: {has_data_count}/{workflow['total_steps']} ({has_data_count/workflow['total_steps']*100:.1f}%)")
    print(f"  空步骤: {empty_count}/{workflow['total_steps']} ({empty_count/workflow['total_steps']*100:.1f}%)")
    print("=" * 80)
    print()
    print("💡 解释:")
    print("  - '空步骤' 通常是 UI 导航操作（切换标签页、点击按钮）")
    print("  - '有数据' 的步骤是实质性操作（打开对象、创建/更新数据）")
    print("  - 对于指令生成:")
    print("    * 空步骤：可以生成简单导航指令（'Select the Routes tab'）")
    print("    * 有数据步骤：生成详细操作指令（'Open E Probleem Object in elektra database'）")
    print("=" * 80)


if __name__ == "__main__":
    index = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    visualize_workflow("data/processed/parsed_workflows.jsonl", workflow_index=index)
