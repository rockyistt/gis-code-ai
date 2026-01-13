"""
基于您的实际数据的完整反向推理示例
可以直接运行，展示不同方法的效果对比
"""

import json
from pathlib import Path
from typing import Dict, List


class SimpleInferencer:
    """简单但实用的推理器 - 不需要任何API"""
    
    def __init__(self):
        # 操作动词映射
        self.action_verbs = {
            "Create": "Create",
            "Update": "Update", 
            "Delete": "Delete",
            "Open Object": "Open",
            "Open Object with ID": "Open",
            "Switch Spatial Context": "Switch to",
            "Verify Field": "Verify",
            "Select Tab": "Navigate to",
            "Click Oneshot Button": "Click",
            "Select first HV object": "Select",
            "Select second HV object": "Select",
            "Datamodel Check": "Perform consistency check on"
        }
        
        # 模块描述
        self.module_desc = {
            "Editor(s)": "editor",
            "Datamodel CRUD": "datamodel",
            "Tabs": "tab",
            "Buttons": "button",
            "Hierarchy Viewer": "hierarchy viewer",
            "Datamodel Consistency Check": "consistency check"
        }
    
    def clean_object_name(self, obj: str) -> str:
        """清理对象名称"""
        # 移除数据库前缀
        if obj.startswith(':'):
            obj = obj[1:]
        return obj
    
    def extract_key_fields(self, test_data: Dict) -> Dict:
        """提取关键字段"""
        result = {}
        
        for section in ['create', 'update', 'editor']:
            if section in test_data and test_data[section]:
                data = test_data[section]
                
                # 查找自定义字段
                for key, value in data.items():
                    if key.startswith('FLD_CSTM') and isinstance(value, dict):
                        # 提取有用的字段
                        if 'Spatial Context' in value:
                            result['spatial_context'] = value['Spatial Context']
                        if 'Station Nummer' in value:
                            result['station'] = value['Station Nummer']
                        
                        # 计算非ID字段数量
                        non_id_fields = [k for k in value.keys() if k != 'ID' and not k.startswith('FLD')]
                        result['field_count'] = len(non_id_fields)
                        
                        # 提取关键属性（前3个）
                        result['key_attributes'] = non_id_fields[:3]
        
        return result
    
    def infer_step_instruction(self, step: Dict) -> str:
        """为单个步骤生成指令"""
        module = step.get('module', '')
        method = step.get('method', '')
        obj = self.clean_object_name(step.get('object', ''))
        database = step.get('database', '').replace(':', '')
        
        # 获取动作动词
        action = self.action_verbs.get(method, method)
        
        # 提取关键字段
        test_data = step.get('test_data', {})
        key_info = self.extract_key_fields(test_data)
        
        # 构建指令
        if method == "Create":
            if key_info.get('field_count'):
                return f"{action} a new {obj} with {key_info['field_count']} specified attributes"
            else:
                return f"{action} a new {obj} object"
        
        elif method == "Update":
            return f"{action} the {obj} with modified values"
        
        elif method == "Delete":
            return f"{action} the {obj} object"
        
        elif method in ["Open Object", "Open Object with ID"]:
            if key_info.get('spatial_context'):
                return f"{action} {obj} in {key_info['spatial_context']} context"
            else:
                return f"{action} {obj} in the {database} dataset"
        
        elif method == "Switch Spatial Context":
            context = key_info.get('spatial_context', 'specified')
            return f"{action} {context} spatial context"
        
        elif method == "Select Tab":
            return f"{action} the {obj} tab"
        
        elif method == "Click Oneshot Button":
            return f"{action} the '{obj}' button"
        
        elif "Select" in method and "HV object" in method:
            position = "first" if "first" in method else "second"
            return f"{action} the {position} {obj} in hierarchy viewer"
        
        elif method == "Datamodel Check":
            return f"{action} {obj}"
        
        else:
            # 通用模板
            module_name = self.module_desc.get(module, module)
            return f"{action} {obj} in {module_name}"
    
    def infer_workflow_instruction(self, workflow: Dict) -> str:
        """为整个工作流生成指令"""
        steps = workflow.get('steps', [])
        file_id = workflow.get('file_id', '')
        
        # 分析工作流模式
        operations = {
            'create': [],
            'update': [],
            'delete': [],
            'navigation': []
        }
        
        for step in steps:
            method = step.get('method', '')
            obj = self.clean_object_name(step.get('object', ''))
            
            if method == 'Create':
                operations['create'].append(obj)
            elif method == 'Update':
                operations['update'].append(obj)
            elif method == 'Delete':
                operations['delete'].append(obj)
            elif method in ['Select Tab', 'Click Oneshot Button']:
                operations['navigation'].append(obj)
        
        # 构建描述
        parts = []
        
        if operations['create']:
            unique_objects = list(set(operations['create']))
            if len(unique_objects) == 1:
                parts.append(f"create {unique_objects[0]}")
            else:
                parts.append(f"create multiple objects ({', '.join(unique_objects[:3])})")
        
        if operations['update']:
            parts.append("update their properties")
        
        if operations['delete']:
            parts.append("delete specified objects")
        
        # 生成最终描述
        if parts:
            action_desc = ", ".join(parts)
            return f"Test workflow to {action_desc} in the GIS system"
        else:
            return f"Test workflow for {file_id}: perform editor operations and navigation"
    
    def analyze_workflow_pattern(self, workflow: Dict) -> str:
        """分析工作流模式类型"""
        steps = workflow.get('steps', [])
        methods = [step.get('method') for step in steps]
        
        # CRUD模式
        has_create = 'Create' in methods
        has_update = 'Update' in methods
        has_delete = 'Delete' in methods
        
        if has_create and has_update and has_delete:
            return "Full CRUD test workflow"
        elif has_create:
            return "Object creation workflow"
        elif has_update:
            return "Object modification workflow"
        
        # 导航模式
        nav_methods = ['Select Tab', 'Click Oneshot Button']
        if any(m in methods for m in nav_methods):
            return "Navigation and UI test workflow"
        
        return "General test workflow"


def demo_with_real_data():
    """使用真实数据演示"""
    
    # 读取一些真实数据
    data_file = Path("data/processed/parsed_workflows.jsonl")
    
    if not data_file.exists():
        print(f"❌ 数据文件不存在: {data_file}")
        print("请确保已运行数据处理脚本")
        return
    
    # 加载前3个工作流作为示例
    workflows = []
    with open(data_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 3:  # 只取前3个
                break
            if line.strip():
                workflows.append(json.loads(line))
    
    print("="*70)
    print("从真实JSON反向推理用户指令 - 演示")
    print("="*70)
    
    inferencer = SimpleInferencer()
    
    for wf_idx, workflow in enumerate(workflows, 1):
        print(f"\n{'='*70}")
        print(f"工作流 #{wf_idx}: {workflow['file_id']}")
        print(f"高质量模板: {'✅' if workflow.get('is_high_quality') else '❌'}")
        print(f"总步骤数: {workflow['total_steps']}")
        print(f"{'='*70}")
        
        # 工作流级别指令
        workflow_instruction = inferencer.infer_workflow_instruction(workflow)
        pattern = inferencer.analyze_workflow_pattern(workflow)
        
        print(f"\n📋 整体描述:")
        print(f"   类型: {pattern}")
        print(f"   指令: {workflow_instruction}")
        
        # 步骤级别指令（只显示前5步）
        print(f"\n📝 步骤详情 (前5步):")
        for step in workflow['steps'][:5]:
            instruction = inferencer.infer_step_instruction(step)
            print(f"\n   步骤 {step['step_index']}:")
            print(f"   - 模块: {step['module']}")
            print(f"   - 方法: {step['method']}")
            print(f"   - 对象: {step['object']}")
            print(f"   - 指令: {instruction}")
        
        if len(workflow['steps']) > 5:
            print(f"\n   ... 还有 {len(workflow['steps']) - 5} 个步骤")
    
    print(f"\n{'='*70}")
    print("✅ 演示完成!")
    print("="*70)
    
    # 统计信息
    print("\n📊 生成统计:")
    total_workflows = len(workflows)
    total_steps = sum(len(wf['steps']) for wf in workflows)
    print(f"   - 处理的工作流: {total_workflows}")
    print(f"   - 生成的工作流指令: {total_workflows}")
    print(f"   - 生成的步骤指令: {total_steps}")
    print(f"\n💡 提示: 这种方法不需要任何API，完全离线可用！")


def generate_all_instructions():
    """为所有工作流生成指令并保存"""
    
    input_file = Path("data/processed/parsed_workflows.jsonl")
    output_file = Path("data/processed/generated_instructions_simple.jsonl")
    
    if not input_file.exists():
        print(f"❌ 输入文件不存在: {input_file}")
        return
    
    print("开始处理所有工作流...")
    
    # 加载所有工作流
    workflows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                workflows.append(json.loads(line))
    
    print(f"加载了 {len(workflows)} 个工作流")
    
    inferencer = SimpleInferencer()
    results = []
    
    # 处理每个工作流
    for i, workflow in enumerate(workflows):
        if (i + 1) % 100 == 0:
            print(f"进度: {i + 1}/{len(workflows)}")
        
        # 生成工作流级别指令
        file_instruction = inferencer.infer_workflow_instruction(workflow)
        pattern = inferencer.analyze_workflow_pattern(workflow)
        
        # 生成步骤级别指令
        step_instructions = []
        for step in workflow['steps']:
            step_inst = inferencer.infer_step_instruction(step)
            step_instructions.append({
                "step_index": step['step_index'],
                "module": step['module'],
                "method": step['method'],
                "object": step['object'],
                "instruction": step_inst
            })
        
        # 保存结果
        result = {
            "file_id": workflow['file_id'],
            "is_high_quality": workflow.get('is_high_quality', False),
            "workflow_pattern": pattern,
            "file_level_instruction": file_instruction,
            "step_level_instructions": step_instructions
        }
        results.append(result)
    
    # 保存到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    print(f"\n✅ 完成!")
    print(f"   - 处理的工作流: {len(workflows)}")
    print(f"   - 生成的工作流指令: {len(results)}")
    print(f"   - 总步骤指令: {sum(len(r['step_level_instructions']) for r in results)}")
    print(f"   - 输出文件: {output_file}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # 生成所有指令
        generate_all_instructions()
    else:
        # 演示模式
        demo_with_real_data()
        
        print("\n" + "="*70)
        print("💡 提示:")
        print("   - 运行 'python examples/demo_inference.py' 查看演示")
        print("   - 运行 'python examples/demo_inference.py --all' 处理所有数据")
        print("="*70)
