"""
增强版指令生成器 - 支持关键词权重和结构化表达

新特性：
1. 关键词权重标注（为训练时的attention机制提供支持）
2. 动作词强调和同义词变化
3. 结构化模板（动作+宾语+状语）的多样化表达
4. 支持输出带权重标记的格式
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple
import logging
from tqdm import tqdm
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KeywordWeights:
    """关键词权重定义"""
    
    # 权重等级
    CRITICAL = 3.0    # 核心动作词
    HIGH = 2.0        # 重要对象和方法
    MEDIUM = 1.5      # 修饰语和上下文
    NORMAL = 1.0      # 一般词汇
    
    # 动作词权重映射
    ACTION_WEIGHTS = {
        "Create": CRITICAL,
        "Update": CRITICAL,
        "Delete": CRITICAL,
        "Open": HIGH,
        "Navigate": HIGH,
        "Click": HIGH,
        "Verify": HIGH,
        "Select": HIGH,
        "Switch": MEDIUM,
        "Perform": MEDIUM,
    }
    
    # 对象类型权重
    OBJECT_WEIGHTS = {
        "object": HIGH,
        "dataset": MEDIUM,
        "database": MEDIUM,
        "tab": MEDIUM,
        "button": MEDIUM,
        "field": MEDIUM,
    }


class StructuredInstructionTemplate:
    """结构化指令模板（动作+宾语+状语）"""
    
    def __init__(self):
        # 动作词及其同义词变体
        self.action_synonyms = {
            "Create": ["Create", "Add", "Insert", "Generate"],
            "Update": ["Update", "Modify", "Change", "Edit"],
            "Delete": ["Delete", "Remove", "Erase"],
            "Open": ["Open", "Access", "Load"],
            "Navigate": ["Navigate to", "Go to", "Switch to", "Move to"],
            "Click": ["Click", "Press", "Activate"],
            "Select": ["Select", "Choose", "Pick"],
            "Verify": ["Verify", "Check", "Validate", "Confirm"],
        }
        
        # 宾语增强描述
        self.object_enhancers = {
            "object": ["object", "entity", "record", "item"],
            "dataset": ["dataset", "data collection", "data source"],
            "database": ["database", "data store", "repository"],
        }
        
        # 状语模板变体
        self.adverbial_templates = {
            "in_database": [
                "in {database} database",
                "within {database}",
                "from {database} dataset",
                "in the {database} repository"
            ],
            "with_attributes": [
                "with {count} attributes",
                "having {count} specified attributes",
                "containing {count} properties",
                "with {count} defined fields"
            ],
            "location": [
                "in {location}",
                "at {location}",
                "within {location}"
            ]
        }
    
    def get_action_variant(self, action: str, use_synonym: bool = False) -> str:
        """获取动作词（可选使用同义词）"""
        if use_synonym and action in self.action_synonyms:
            return random.choice(self.action_synonyms[action])
        return action
    
    def get_object_variant(self, obj_type: str) -> str:
        """获取宾语变体"""
        if obj_type in self.object_enhancers:
            return random.choice(self.object_enhancers[obj_type])
        return obj_type
    
    def get_adverbial_variant(self, adv_type: str, **kwargs) -> str:
        """获取状语变体"""
        if adv_type in self.adverbial_templates:
            template = random.choice(self.adverbial_templates[adv_type])
            return template.format(**kwargs)
        return ""


class WeightedInstructionGenerator:
    """带权重的指令生成器"""
    
    def __init__(self, use_variants: bool = True, mark_weights: bool = False):
        """
        Args:
            use_variants: 是否使用同义词变体
            mark_weights: 是否在输出中标记权重
        """
        self.templates = StructuredInstructionTemplate()
        self.use_variants = use_variants
        self.mark_weights = mark_weights
        
        # 核心动作映射（结构化）
        self.action_patterns = {
            "Create": self._create_pattern,
            "Update": self._update_pattern,
            "Delete": self._delete_pattern,
            "Open Object": self._open_pattern,
            "Open Object with ID": self._open_id_pattern,
            "Select Tab": self._select_tab_pattern,
            "Click Oneshot Button": self._click_button_pattern,
            "Verify Field": self._verify_pattern,
            "Switch Spatial Context": self._switch_context_pattern,
            "Select first HV object": self._select_hv_pattern,
            "Select second HV object": self._select_hv_pattern,
            "Datamodel Check": self._datamodel_check_pattern,
        }
    
    def _mark_keyword(self, word: str, weight: float) -> str:
        """标记关键词权重"""
        if self.mark_weights and weight > KeywordWeights.NORMAL:
            # 使用特殊标记包裹高权重词
            if weight >= KeywordWeights.CRITICAL:
                return f"**{word}**"  # 双星号表示关键
            elif weight >= KeywordWeights.HIGH:
                return f"*{word}*"    # 单星号表示重要
        return word
    
    def _clean_object_name(self, obj: str) -> str:
        """清理对象名"""
        return obj.replace(':', '').strip()
    
    def _create_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """创建操作模式：[动作] + [宾语] + [状语(属性/位置)]"""
        obj = self._clean_object_name(step.get('object', ''))
        database = step.get('database', '').replace(':', '')
        
        # 提取属性数量
        attr_count = self._extract_attributes_count(step)
        
        # 构建指令（结构化）
        action = self.templates.get_action_variant("Create", self.use_variants)
        action_marked = self._mark_keyword(action, KeywordWeights.CRITICAL)
        
        obj_marked = self._mark_keyword(obj, KeywordWeights.HIGH)
        
        # 状语部分
        adverbials = []
        if attr_count > 0:
            adv = self.templates.get_adverbial_variant("with_attributes", count=attr_count)
            adverbials.append(adv)
        
        if database:
            adv = self.templates.get_adverbial_variant("in_database", database=database)
            adverbials.append(self._mark_keyword(database, KeywordWeights.MEDIUM) + " database")
        
        # 组合：动作 + 宾语 + 状语
        parts = [action_marked, obj_marked, "object"]
        if adverbials:
            parts.extend(adverbials)
        
        instruction = " ".join(parts)
        
        # 返回指令和权重列表
        weights = [
            (action, KeywordWeights.CRITICAL),
            (obj, KeywordWeights.HIGH),
            ("object", KeywordWeights.HIGH),
        ]
        if database:
            weights.append((database, KeywordWeights.MEDIUM))
        
        return instruction, weights
    
    def _update_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """更新操作模式"""
        obj = self._clean_object_name(step.get('object', ''))
        action = self.templates.get_action_variant("Update", self.use_variants)
        
        action_marked = self._mark_keyword(action, KeywordWeights.CRITICAL)
        obj_marked = self._mark_keyword(obj, KeywordWeights.HIGH)
        
        instruction = f"{action_marked} {obj_marked} object with modified field values"
        weights = [
            (action, KeywordWeights.CRITICAL),
            (obj, KeywordWeights.HIGH),
            ("modified", KeywordWeights.MEDIUM),
        ]
        return instruction, weights
    
    def _delete_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """删除操作模式"""
        obj = self._clean_object_name(step.get('object', ''))
        action = self.templates.get_action_variant("Delete", self.use_variants)
        
        action_marked = self._mark_keyword(action, KeywordWeights.CRITICAL)
        obj_marked = self._mark_keyword(obj, KeywordWeights.HIGH)
        
        instruction = f"{action_marked} {obj_marked} object"
        weights = [
            (action, KeywordWeights.CRITICAL),
            (obj, KeywordWeights.HIGH),
        ]
        return instruction, weights
    
    def _open_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """打开对象模式"""
        obj = self._clean_object_name(step.get('object', ''))
        database = step.get('database', '').replace(':', '')
        action = self.templates.get_action_variant("Open", self.use_variants)
        
        action_marked = self._mark_keyword(action, KeywordWeights.HIGH)
        obj_marked = self._mark_keyword(obj, KeywordWeights.HIGH)
        
        if database:
            db_marked = self._mark_keyword(database, KeywordWeights.MEDIUM)
            instruction = f"{action_marked} {obj_marked} object in {db_marked} dataset"
            weights = [(action, KeywordWeights.HIGH), (obj, KeywordWeights.HIGH), (database, KeywordWeights.MEDIUM)]
        else:
            instruction = f"{action_marked} {obj_marked} object"
            weights = [(action, KeywordWeights.HIGH), (obj, KeywordWeights.HIGH)]
        
        return instruction, weights
    
    def _open_id_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """通过ID打开对象模式"""
        obj = self._clean_object_name(step.get('object', ''))
        action = self.templates.get_action_variant("Open", self.use_variants)
        
        action_marked = self._mark_keyword(action, KeywordWeights.HIGH)
        obj_marked = self._mark_keyword(obj, KeywordWeights.HIGH)
        id_marked = self._mark_keyword("ID", KeywordWeights.MEDIUM)
        
        instruction = f"{action_marked} {obj_marked} object by {id_marked}"
        weights = [
            (action, KeywordWeights.HIGH),
            (obj, KeywordWeights.HIGH),
            ("ID", KeywordWeights.MEDIUM),
        ]
        return instruction, weights
    
    def _select_tab_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """选择标签页模式"""
        obj = self._clean_object_name(step.get('object', ''))
        action = self.templates.get_action_variant("Navigate", self.use_variants)
        
        action_marked = self._mark_keyword(action, KeywordWeights.HIGH)
        obj_marked = self._mark_keyword(obj, KeywordWeights.MEDIUM)
        
        instruction = f"{action_marked} {obj_marked} tab"
        weights = [
            (action, KeywordWeights.HIGH),
            (obj, KeywordWeights.MEDIUM),
        ]
        return instruction, weights
    
    def _click_button_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """点击按钮模式"""
        obj = self._clean_object_name(step.get('object', ''))
        action = self.templates.get_action_variant("Click", self.use_variants)
        
        action_marked = self._mark_keyword(action, KeywordWeights.HIGH)
        obj_marked = self._mark_keyword(obj, KeywordWeights.MEDIUM)
        
        instruction = f"{action_marked} {obj_marked} button"
        weights = [
            (action, KeywordWeights.HIGH),
            (obj, KeywordWeights.MEDIUM),
        ]
        return instruction, weights
    
    def _verify_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """验证字段模式"""
        obj = self._clean_object_name(step.get('object', ''))
        action = self.templates.get_action_variant("Verify", self.use_variants)
        
        action_marked = self._mark_keyword(action, KeywordWeights.HIGH)
        obj_marked = self._mark_keyword(obj, KeywordWeights.MEDIUM)
        
        instruction = f"{action_marked} {obj_marked} field values"
        weights = [
            (action, KeywordWeights.HIGH),
            (obj, KeywordWeights.MEDIUM),
        ]
        return instruction, weights
    
    def _switch_context_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """切换空间上下文模式"""
        obj = self._clean_object_name(step.get('object', ''))
        action = "Switch spatial context"
        
        action_marked = self._mark_keyword("Switch", KeywordWeights.MEDIUM)
        obj_marked = self._mark_keyword(obj, KeywordWeights.MEDIUM)
        
        instruction = f"{action_marked} spatial context to {obj_marked}"
        weights = [
            ("Switch", KeywordWeights.MEDIUM),
            (obj, KeywordWeights.MEDIUM),
        ]
        return instruction, weights
    
    def _select_hv_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """选择层级视图对象模式"""
        obj = self._clean_object_name(step.get('object', ''))
        method = step.get('method', '')
        position = "first" if "first" in method else "second"
        
        action = self.templates.get_action_variant("Select", self.use_variants)
        action_marked = self._mark_keyword(action, KeywordWeights.HIGH)
        obj_marked = self._mark_keyword(obj, KeywordWeights.MEDIUM)
        
        instruction = f"{action_marked} {position} {obj_marked} in hierarchy viewer"
        weights = [
            (action, KeywordWeights.HIGH),
            (obj, KeywordWeights.MEDIUM),
        ]
        return instruction, weights
    
    def _datamodel_check_pattern(self, step: Dict) -> Tuple[str, List[Tuple[str, float]]]:
        """数据模型检查模式"""
        obj = self._clean_object_name(step.get('object', ''))
        
        action_marked = self._mark_keyword("Check", KeywordWeights.HIGH)
        obj_marked = self._mark_keyword(obj, KeywordWeights.MEDIUM)
        
        instruction = f"{action_marked} data consistency for {obj_marked}"
        weights = [
            ("Check", KeywordWeights.HIGH),
            (obj, KeywordWeights.MEDIUM),
        ]
        return instruction, weights
    
    def _extract_attributes_count(self, step: Dict) -> int:
        """提取属性数量"""
        test_data = step.get('test_data', {})
        for section in ['create', 'update']:
            if section in test_data and test_data[section]:
                data = test_data[section]
                for key, value in data.items():
                    if key.startswith('FLD_CSTM') and isinstance(value, dict):
                        return len([k for k in value.keys() if k != 'ID'])
        return 0
    
    def generate_step_instruction(self, step: Dict) -> Dict[str, Any]:
        """生成步骤级指令（带权重信息）"""
        method = step.get('method', '')
        
        # 使用对应的模式生成
        if method in self.action_patterns:
            instruction, weights = self.action_patterns[method](step)
        else:
            # 默认模式
            obj = self._clean_object_name(step.get('object', ''))
            instruction = f"{method} {obj}"
            weights = [(method, KeywordWeights.NORMAL), (obj, KeywordWeights.MEDIUM)]
        
        return {
            "instruction": instruction,
            "weights": weights,
            "structure": self._analyze_structure(instruction)
        }
    
    def _analyze_structure(self, instruction: str) -> Dict[str, str]:
        """分析指令结构（动作+宾语+状语）"""
        words = instruction.replace('*', '').split()
        
        # 简单的结构分析
        structure = {
            "action": words[0] if words else "",
            "object": "",
            "adverbials": []
        }
        
        # 寻找宾语（通常在动作词后）
        for i, word in enumerate(words[1:], 1):
            if word.lower() in ['object', 'tab', 'button', 'field']:
                if i > 0:
                    structure["object"] = " ".join(words[1:i+1])
                break
        
        # 剩余部分作为状语
        if structure["object"]:
            obj_end = len(structure["object"].split()) + 1
            if len(words) > obj_end:
                structure["adverbials"] = words[obj_end:]
        
        return structure
    
    def generate_file_instruction(self, workflow: Dict) -> Dict[str, Any]:
        """生成文件级指令（带权重和结构）"""
        steps = workflow.get('steps', [])
        app = workflow.get('test_app', 'GIS system')
        
        # 收集关键信息
        actions = set()
        objects = set()
        databases = set()
        
        for step in steps:
            method = step.get('method', '')
            obj = self._clean_object_name(step.get('object', ''))
            db = step.get('database', '').replace(':', '')
            
            if method in ['Create', 'Update', 'Delete']:
                actions.add(method.lower())
            
            if obj and obj not in ['Default', 'Object Control', 'Routes', 'Object Editor']:
                objects.add(obj)
            
            if db:
                databases.add(db)
        
        # 构建文件级指令
        action_str = self._mark_keyword(", ".join(sorted(actions)), KeywordWeights.CRITICAL) if actions else "manage"
        
        if len(objects) <= 3:
            obj_list = [self._mark_keyword(obj, KeywordWeights.HIGH) for obj in list(objects)[:3]]
            obj_str = ", ".join(obj_list)
        else:
            obj_str = f"multiple objects"
        
        db_str = ""
        if databases:
            db = list(databases)[0]
            db_str = f" in {self._mark_keyword(db, KeywordWeights.MEDIUM)}"
        
        instruction = f"Workflow: {action_str} {obj_str}{db_str} in {app}"
        
        # 权重信息
        weights = []
        for action in actions:
            weights.append((action, KeywordWeights.CRITICAL))
        for obj in list(objects)[:3]:
            weights.append((obj, KeywordWeights.HIGH))
        if databases:
            weights.append((list(databases)[0], KeywordWeights.MEDIUM))
        
        return {
            "instruction": instruction,
            "weights": weights,
            "actions": list(actions),
            "objects": list(objects)[:5],
            "databases": list(databases)
        }


def main():
    parser = argparse.ArgumentParser(description="增强版指令生成器（支持权重和结构化）")
    parser.add_argument('--input', type=str,
                       default='data/processed/parsed_workflows.jsonl',
                       help='输入文件路径')
    parser.add_argument('--output-dir', type=str,
                       default='data/processed',
                       help='输出目录')
    parser.add_argument('--use-variants', action='store_true',
                       help='使用同义词变体增加多样性')
    parser.add_argument('--mark-weights', action='store_true',
                       help='在输出中标记关键词权重（**关键** *重要*）')
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
    generator = WeightedInstructionGenerator(
        use_variants=args.use_variants,
        mark_weights=args.mark_weights
    )
    
    # 输出路径
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    suffix = "_weighted"
    if args.use_variants:
        suffix += "_variants"
    if args.mark_weights:
        suffix += "_marked"
    
    file_output = output_dir / f"file_level_instructions{suffix}.jsonl"
    step_output = output_dir / f"step_level_instructions{suffix}.jsonl"
    
    # 生成文件级指令
    logger.info("📝 Generating file-level instructions...")
    file_results = []
    for workflow in tqdm(workflows, desc="File-level"):
        result = generator.generate_file_instruction(workflow)
        
        output = {
            "file_id": workflow.get("file_id", ""),
            "is_high_quality": workflow.get("is_high_quality", False),
            "instruction": result["instruction"],
            "provider": "rule_weighted",
            "test_app": workflow.get("test_app", ""),
            "total_steps": len(workflow.get("steps", [])),
            "keywords": result["weights"],  # 关键词权重
            "actions": result["actions"],
            "objects": result["objects"],
            "databases": result["databases"]
        }
        file_results.append(output)
    
    with open(file_output, 'w', encoding='utf-8') as f:
        for result in file_results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    logger.info(f"✅ File-level instructions saved to {file_output}")
    
    # 生成步骤级指令
    logger.info("📝 Generating step-level instructions...")
    step_results = []
    for workflow in tqdm(workflows, desc="Step-level"):
        file_id = workflow.get("file_id", "")
        is_hq = workflow.get("is_high_quality", False)
        steps = workflow.get("steps", [])
        
        for i, step in enumerate(steps):
            result = generator.generate_step_instruction(step)
            
            output = {
                "file_id": file_id,
                "step_index": i,
                "step_type": step.get("module", ""),
                "is_high_quality": is_hq,
                "instruction": result["instruction"],
                "provider": "rule_weighted",
                "module": step.get("module", ""),
                "method": step.get("method", ""),
                "keywords": result["weights"],  # 关键词权重
                "structure": result["structure"]  # 结构分析
            }
            step_results.append(output)
    
    with open(step_output, 'w', encoding='utf-8') as f:
        for result in step_results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    logger.info(f"✅ Step-level instructions saved to {step_output}")
    
    # 统计信息
    logger.info("\n" + "="*60)
    logger.info("🎉 增强版指令生成完成！")
    logger.info(f"📄 文件级: {file_output}")
    logger.info(f"📝 步骤级: {step_output}")
    logger.info(f"⚙️  选项:")
    logger.info(f"   - 使用同义词变体: {args.use_variants}")
    logger.info(f"   - 标记权重: {args.mark_weights}")
    logger.info(f"📊 统计:")
    logger.info(f"   - 工作流数: {len(file_results)}")
    logger.info(f"   - 步骤数: {len(step_results)}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
