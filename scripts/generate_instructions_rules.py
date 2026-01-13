"""
使用规则模板生成指令（无需API）

基于项目中的evaluate_methods.py改编，提供三种规则方法：
1. Method1_BasicRules - 基础规则（简洁快速）
2. Method2_EnhancedRules - 增强规则（推荐）
3. Method3_ContextAware - 上下文感知（最详细）
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Method1_BasicRules:
    """方法1: 基础规则模板"""
    
    def __init__(self):
        self.templates = {
            "Create": "Create {object}",
            "Update": "Update {object}",
            "Delete": "Delete {object}",
            "Open Object": "Open {object}",
            "Open Object with ID": "Open {object} with specific ID",
            "Select Tab": "Select {object} tab",
            "Click Oneshot Button": "Click {object} button",
            "Verify Field": "Verify {object} field values",
            "Switch Spatial Context": "Switch spatial context for {object}",
        }
    
    def generate_step_instruction(self, step: Dict) -> str:
        """生成步骤级指令"""
        method = step.get('method', '')
        obj = step.get('object', '')
        
        template = self.templates.get(method, "{method} {object}")
        return template.format(method=method, object=obj)
    
    def generate_file_instruction(self, workflow: Dict) -> str:
        """生成文件级指令"""
        steps = workflow.get('steps', [])
        objects = set()
        
        for step in steps:
            obj = step.get('object', '')
            if obj and obj not in ['Default', 'Object Control']:
                objects.add(obj)
        
        if len(objects) > 3:
            obj_list = f"{len(objects)} objects"
        else:
            obj_list = ", ".join(list(objects)[:3])
        
        app = workflow.get('test_app', 'GIS system')
        return f"Test workflow to work with {obj_list} in {app}"


class Method2_EnhancedRules:
    """方法2: 增强规则模板（推荐）"""
    
    def __init__(self):
        self.action_verbs = {
            "Create": "Create a new",
            "Update": "Update the existing",
            "Delete": "Delete the",
            "Open Object": "Open",
            "Open Object with ID": "Open",
            "Switch Spatial Context": "Switch spatial context to",
            "Verify Field": "Verify field values for",
            "Select Tab": "Navigate to",
            "Click Oneshot Button": "Click",
            "Select first HV object": "Select the first",
            "Select second HV object": "Select the second",
            "Datamodel Check": "Perform consistency check on"
        }
    
    def clean_object_name(self, obj: str) -> str:
        """清理对象名"""
        if obj.startswith(':'):
            obj = obj[1:]
        return obj
    
    def extract_attributes_count(self, step: Dict) -> int:
        """提取属性数量"""
        test_data = step.get('test_data', {})
        for section in ['create', 'update']:
            if section in test_data and test_data[section]:
                data = test_data[section]
                for key, value in data.items():
                    if key.startswith('FLD_CSTM') and isinstance(value, dict):
                        return len([k for k in value.keys() if k != 'ID'])
        return 0
    
    def generate_step_instruction(self, step: Dict) -> str:
        """生成步骤级指令"""
        method = step.get('method', '')
        obj = self.clean_object_name(step.get('object', ''))
        database = step.get('database', '').replace(':', '')
        
        action = self.action_verbs.get(method, method)
        
        # 根据方法类型生成更详细的描述
        if method == "Create":
            attr_count = self.extract_attributes_count(step)
            if attr_count > 0 and database:
                return f"{action} {obj} object with {attr_count} attributes in {database} database"
            elif database:
                return f"{action} {obj} object in {database} database"
            return f"{action} {obj} object"
        
        elif method in ["Open Object", "Open Object with ID"]:
            if database:
                return f"{action} {obj} object in {database} dataset"
            return f"{action} {obj} object"
        
        elif method == "Update":
            return f"{action} {obj} object with modified field values"
        
        elif method == "Select Tab":
            return f"{action} {obj} tab"
        
        elif method == "Click Oneshot Button":
            return f"{action} {obj} button"
        
        elif "HV object" in method:
            return f"{action} {obj} in hierarchy viewer"
        
        else:
            return f"{action} {obj}"
    
    def generate_file_instruction(self, workflow: Dict) -> str:
        """生成文件级指令"""
        steps = workflow.get('steps', [])
        app = workflow.get('test_app', 'GIS system')
        
        # 收集关键信息
        objects = set()
        databases = set()
        actions = set()
        
        for step in steps:
            obj = step.get('object', '')
            db = step.get('database', '').replace(':', '')
            method = step.get('method', '')
            
            if obj and obj not in ['Default', 'Object Control', 'Routes', 'Object Editor']:
                objects.add(obj)
            if db:
                databases.add(db)
            if method in ['Create', 'Update', 'Delete']:
                actions.add(method.lower())
        
        # 生成描述
        action_str = ", ".join(sorted(actions)) if actions else "work with"
        
        if len(objects) <= 3:
            obj_str = ", ".join(list(objects))
        else:
            obj_str = f"multiple objects ({', '.join(list(objects)[:2])}, ...)"
        
        db_str = f" in {list(databases)[0]}" if len(databases) == 1 else ""
        
        return f"Workflow for {app}: {action_str} {obj_str}{db_str}"


class Method3_ContextAware:
    """方法3: 上下文感知规则"""
    
    def __init__(self):
        # 友好的对象名称映射
        self.friendly_names = {
            "E MS Kabel": "Medium Voltage Cable",
            "E HS Kabel": "High Voltage Cable",
            "E LS Kabel": "Low Voltage Cable",
            "E MS Mof": "Medium Voltage Joint",
            "E MS Installatie FP": "Medium Voltage Installation",
        }
    
    def get_friendly_name(self, obj: str) -> str:
        """获取友好名称"""
        obj = obj.replace(':', '')
        return self.friendly_names.get(obj, obj)
    
    def generate_step_instruction(self, step: Dict, context: List[Dict] = None) -> str:
        """生成步骤级指令（带上下文）"""
        method = step.get('method', '')
        obj = self.get_friendly_name(step.get('object', ''))
        
        # 基于上下文生成
        if context and len(context) > 0:
            prev_method = context[-1].get('method', '')
            if method == "Verify Field" and prev_method == "Create":
                return f"Verify the created {obj} has correct field values"
        
        # 默认描述
        actions = {
            "Create": f"Create a new {obj} object",
            "Open Object": f"Open {obj} for editing",
            "Update": f"Update {obj} properties",
            "Select Tab": f"Navigate to {obj} section",
        }
        
        return actions.get(method, f"{method} {obj}")
    
    def generate_file_instruction(self, workflow: Dict) -> str:
        """生成文件级指令"""
        steps = workflow.get('steps', [])
        
        # 识别主要操作
        main_objects = []
        for step in steps:
            if step.get('method') in ['Create', 'Update']:
                obj = self.get_friendly_name(step.get('object', ''))
                if obj and obj not in main_objects:
                    main_objects.append(obj)
        
        if len(main_objects) > 2:
            return f"Electrical network workflow: object management for {', '.join(main_objects[:2])} and others"
        elif main_objects:
            return f"Electrical network workflow: object creation and management for {', '.join(main_objects)}"
        else:
            return "GIS workflow for object management and verification"


class RuleBasedGenerator:
    """规则生成器主类"""
    
    def __init__(self, method: str = "enhanced"):
        """
        Args:
            method: "basic", "enhanced", 或 "context"
        """
        if method == "basic":
            self.generator = Method1_BasicRules()
        elif method == "enhanced":
            self.generator = Method2_EnhancedRules()
        elif method == "context":
            self.generator = Method3_ContextAware()
        else:
            raise ValueError(f"Unknown method: {method}")
        
        self.method_name = method
    
    def generate_file_level(self, workflows: List[Dict], output_path: Path):
        """生成文件级指令"""
        logger.info(f"Generating file-level instructions using {self.method_name} method...")
        
        results = []
        for workflow in tqdm(workflows, desc="File-level"):
            instruction = self.generator.generate_file_instruction(workflow)
            
            result = {
                "file_id": workflow.get("file_id", ""),
                "is_high_quality": workflow.get("is_high_quality", False),
                "instruction": instruction,
                "provider": f"rule_{self.method_name}",
                "test_app": workflow.get("test_app", ""),
                "total_steps": len(workflow.get("steps", []))
            }
            results.append(result)
        
        # 保存结果
        with open(output_path, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        
        logger.info(f"✅ File-level instructions saved to {output_path}")
        logger.info(f"   Total: {len(results)} workflows")
    
    def generate_step_level(self, workflows: List[Dict], output_path: Path):
        """生成步骤级指令"""
        logger.info(f"Generating step-level instructions using {self.method_name} method...")
        
        results = []
        for workflow in tqdm(workflows, desc="Step-level"):
            file_id = workflow.get("file_id", "")
            is_hq = workflow.get("is_high_quality", False)
            steps = workflow.get("steps", [])
            
            for i, step in enumerate(steps):
                # 生成指令
                if self.method_name == "context" and hasattr(self.generator, 'generate_step_instruction'):
                    # 提供上下文
                    context = steps[:i] if i > 0 else []
                    instruction = self.generator.generate_step_instruction(step, context)
                else:
                    instruction = self.generator.generate_step_instruction(step)
                
                result = {
                    "file_id": file_id,
                    "step_index": i,
                    "step_type": step.get("module", ""),
                    "is_high_quality": is_hq,
                    "instruction": instruction,
                    "provider": f"rule_{self.method_name}",
                    "module": step.get("module", ""),
                    "method": step.get("method", "")
                }
                results.append(result)
        
        # 保存结果
        with open(output_path, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        
        logger.info(f"✅ Step-level instructions saved to {output_path}")
        logger.info(f"   Total: {len(results)} steps")


def main():
    parser = argparse.ArgumentParser(description="使用规则模板生成指令（无需API）")
    parser.add_argument('--input', type=str, 
                       default='data/processed/parsed_workflows.jsonl',
                       help='输入文件路径')
    parser.add_argument('--output-dir', type=str,
                       default='data/processed',
                       help='输出目录')
    parser.add_argument('--method', type=str, 
                       choices=['basic', 'enhanced', 'context'],
                       default='enhanced',
                       help='生成方法: basic(基础), enhanced(增强-推荐), context(上下文)')
    parser.add_argument('--max-workflows', type=int,
                       help='最大处理工作流数量（用于测试）')
    
    args = parser.parse_args()
    
    # 读取工作流数据
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"❌ Input file not found: {input_path}")
        return
    
    logger.info(f"📖 Reading workflows from {input_path}")
    workflows = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                workflows.append(json.loads(line))
    
    logger.info(f"✅ Loaded {len(workflows)} workflows")
    
    # 限制数量（如果指定）
    if args.max_workflows:
        workflows = workflows[:args.max_workflows]
        logger.info(f"📊 Limited to {len(workflows)} workflows for testing")
    
    # 创建生成器
    generator = RuleBasedGenerator(method=args.method)
    
    # 输出路径
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    file_output = output_dir / f"file_level_instructions_rule_{args.method}.jsonl"
    step_output = output_dir / f"step_level_instructions_rule_{args.method}.jsonl"
    
    # 生成指令
    generator.generate_file_level(workflows, file_output)
    generator.generate_step_level(workflows, step_output)
    
    logger.info("\n" + "="*60)
    logger.info("🎉 指令生成完成！")
    logger.info(f"📄 文件级: {file_output}")
    logger.info(f"📝 步骤级: {step_output}")
    logger.info(f"⚡ 方法: {args.method}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
