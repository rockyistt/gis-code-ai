#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合指令和数据生成器 - 输出4个分离的JSONL文件

数据流：
1. 加载 parsed_workflows.jsonl
2. 生成4个分离的文件：
   ✓ file_level_instructions_weighted.jsonl - 文件级指令（带权重）来自old version脚本
   ✓ file_level_data.jsonl - 文件级数据（简化） 来自01脚本
   ✓ step_level_instructions.jsonl - 步骤级指令（清晰格式） 来自01脚本
   ✓ step_level_data.jsonl - 步骤级数据（完整JSON+上下文） 来自01脚本

综合优势：
- 文件级指令：结构化表达 + 权重标注
- 文件级数据：CRUD统计 + 对象聚合
- 步骤级指令：自然语言 + 清晰的Step编号
- 步骤级数据：完整的原始JSON + 前置后续步骤上下文
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import logging
from tqdm import tqdm
import random
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 定义动作词集合（用于关键词权重提取）
ACTION_WORDS = {
    "Create", "Add", "New", "Generate", "Insert", "Make",
    "Update", "Modify", "Change", "Edit", "Save", "Set",
    "Delete", "Remove", "Drop", "Clear", "Unset",
    "Open", "View", "Display", "Show", "Access",
    "Close", "Exit", "End", "Finish", "Complete",
    "Select", "Pick", "Choose", "Mark", "Highlight",
    "Click", "Press", "Tap", "Activate", "Step",
    "Verify", "Check", "Validate", "Confirm", "Assert"
}

# 定义上下文词集合
CONTEXT_KEYWORDS = {
    "elektra", "database", "module", "editor", "field", "tab", "panel",
    "window", "dialog", "menu", "button", "form", "table", "list",
    "workflow", "process", "system", "app", "application", "gis"
}


class KeywordWeights:
    """关键词权重定义"""
    CRITICAL = 3.0    # 核心动作词
    HIGH = 2.0        # 重要对象和方法
    MEDIUM = 1.5      # 修饰语和上下文
    NORMAL = 1.0      # 一般词汇


class ObjectNameParser:
    """解析对象名，识别复合词组"""
    
    def __init__(self):
        """初始化对象名解析器"""
        # 从工作流中提取所有唯一的对象名
        self.known_objects = set()
    
    def add_object(self, obj_name: str):
        """添加已知的对象名"""
        if obj_name and len(obj_name) > 2:
            self.known_objects.add(obj_name)
    
    def find_object_name(self, text: str) -> Optional[str]:
        """在文本中查找对象名，返回最长匹配的对象名"""
        # 按长度降序排列，优先匹配长的对象名
        sorted_objects = sorted(self.known_objects, key=len, reverse=True)
        for obj in sorted_objects:
            if obj in text:
                return obj
        return None


class KeywordWeightExtractor:
    """从指令中提取关键词并分配权重"""
    
    def __init__(self, object_parser: Optional[ObjectNameParser] = None):
        """初始化关键词提取器"""
        self.action_words = ACTION_WORDS
        self.context_keywords = CONTEXT_KEYWORDS
        self.object_parser = object_parser or ObjectNameParser()
    
    def extract_keywords_with_weights(self, instruction: str) -> List[Tuple[str, float]]:
        """
        从指令文本中提取关键词及其权重
        
        Args:
            instruction: 指令文本（如 "Create MS Kabel"）
            
        Returns:
            [(keyword, weight), ...] 列表，按权重降序排列
        """
        keywords = []
        remaining_text = instruction
        
        # 1. 先尝试识别复合对象名（如"MS Kabel"、"MS Aardingstrafo FP"）
        object_name = self.object_parser.find_object_name(instruction)
        if object_name:
            keywords.append((object_name, KeywordWeights.HIGH))
            remaining_text = instruction.replace(object_name, '', 1).strip()
        
        # 2. 处理剩余的token
        tokens = remaining_text.split()
        for token in tokens:
            # 清除标点符号
            clean_token = re.sub(r'[^\w\s]', '', token)
            if not clean_token:
                continue
            
            # 跳过已经添加的对象名中的词
            if object_name and clean_token in object_name.split():
                continue
            
            # 检查是否是动作词（区分大小写）
            is_action = False
            for action in self.action_words:
                if clean_token.lower() == action.lower():
                    is_action = True
                    break
            
            if is_action:
                keywords.append((clean_token, KeywordWeights.CRITICAL))
            # 检查是否是上下文词
            elif clean_token.lower() in self.context_keywords:
                keywords.append((clean_token, KeywordWeights.MEDIUM))
            # 其他词（排除数字）
            elif len(clean_token) > 2 and not clean_token.isdigit():
                keywords.append((clean_token, KeywordWeights.HIGH))
        
        # 按权重降序排列
        keywords.sort(key=lambda x: -x[1])
        return keywords
    
    def get_keyword_weights_dict(self, instruction: str) -> Dict[str, Any]:
        """
        获取指令的完整关键词权重信息
        
        Args:
            instruction: 指令文本
            
        Returns:
            包含关键词、权重和统计的字典
        """
        keywords = self.extract_keywords_with_weights(instruction)
        
        if not keywords:
            return {
                "keywords": [],
                "avg_weight": 0.0,
                "max_weight": 0.0,
                "keyword_count": 0
            }
        
        weights = [w for _, w in keywords]
        return {
            "keywords": [[kw, w] for kw, w in keywords],
            "avg_weight": round(sum(weights) / len(weights), 3),
            "max_weight": round(max(weights), 3),
            "keyword_count": len(keywords)
        }


class StructuredInstructionTemplate:
    """结构化指令模板 - 动作+宾语+状语"""
    
    def __init__(self):
        # 动作词及其同义词
        self.action_synonyms = {
            "Create": ["Create", "Add", "Generate", "Insert"],
            "Update": ["Update", "Modify", "Configure", "Edit"],
            "Delete": ["Delete", "Remove", "Erase"],
            "Open": ["Open", "Access", "Load", "Explore"],
            "Navigate": ["Navigate to", "Go to", "Switch to"],
            "Verify": ["Verify", "Check", "Validate", "Confirm"],
            "Click": ["Click", "Press", "Activate"],
            "Select": ["Select", "Choose", "Pick"],
        }
    
    def get_action_variant(self, action: str, use_variant: bool = False) -> str:
        """获取动作词（可选使用同义词）"""
        if use_variant and action in self.action_synonyms:
            return random.choice(self.action_synonyms[action])
        return action


class WeightedInstructionGenerator:
    """
    综合指令生成器
    - 文件级指令：带权重的结构化表达（来自old version）
    - 文件级数据：简化的元数据和统计（来自01）
    - 步骤级指令：清晰的Step X/Y格式（来自01）+ 关键词权重
    - 步骤级数据：完整的原始JSON+上下文（来自01）
    """
    
    def __init__(self, use_variants: bool = False, object_parser: Optional[ObjectNameParser] = None):
        self.templates = StructuredInstructionTemplate()
        self.use_variants = use_variants
        self.object_parser = object_parser or ObjectNameParser()
        self.keyword_extractor = KeywordWeightExtractor(self.object_parser)  # 新增：关键词提取器
    
    def _clean_object_name(self, obj: str) -> str:
        """清理对象名 - 移除E/L/HV前缀"""
        obj = obj.replace(':', '').strip()
        if obj.startswith('E '):
            obj = obj[2:]
        elif obj.startswith('L '):
            obj = obj[2:]
        elif obj.startswith('HV '):
            obj = obj[3:]
        return obj
    
    def _is_valid_object(self, obj: str) -> bool:
        """判断是否为有效的业务对象（排除UI元素和伪对象）"""
        obj_lower = obj.lower()
        invalid = {
            'object', 'object editor', 'object control', 'default', 
            'select', 'button', 'tab', 'field', 'tabs', 'routes',
            'none', 'n/a', 'na', '', 'switch', 'click', 'update',
            'insert', 'get', 'hierarchy viewer', 'elektra;catalogus',
            'probleem object', 'probleem', 'clear', 'elektra', 'catalogus',
            'create', 'delete', 'remove', 'verify', 'check', 'validate',
            'open', 'navigate', 'access', 'edit', 'modify', 'change',
            'perform', 'execute', 'run', 'save', 'load', 'close'
        }
        if obj_lower in invalid:
            return False
        if any(c in obj for c in [';', '|', '$', '%']):
            return False
        return True
    
    def _categorize_operation(self, method: str) -> str:
        """将操作方法分类为标准操作类型"""
        method_lower = method.lower()
        
        if "create" in method_lower:
            return "Create"
        elif "update" in method_lower or "edit" in method_lower:
            return "Update"
        elif "delete" in method_lower or "remove" in method_lower:
            return "Delete"
        elif "verify" in method_lower or "check" in method_lower or "validate" in method_lower:
            return "Verify"
        elif "open" in method_lower or "access" in method_lower or "view" in method_lower:
            return "Open"
        else:
            return "Other"
    
    # ========== 文件级指令生成 ==========
    def generate_file_instruction_with_weights(self, workflow: Dict) -> Dict[str, Any]:
        """
        生成文件级指令（带权重）
        逻辑来自: 001_generate_instructions_file_old version.py
        """
        steps = workflow.get('steps', [])
        app = workflow.get('test_app', 'GIS system')
        
        # 如果没有steps，返回默认值
        if not steps:
            return {
                "instruction": f"Test workflow in {app}",
                "weights": [],
                "actions": [],
                "objects": [],
                "databases": []
            }
        
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
            
            # 使用改进的对象验证
            if obj and self._is_valid_object(obj):
                objects.add(obj)
            
            if db:
                databases.add(db)
        
        # 构建文件级指令
        action_str = ", ".join(sorted(actions)) if actions else "manage"
        
        # 总是列举对象（最多显示5个）
        objects_list = list(objects)[:5]
        if objects_list:
            if len(objects_list) == 1:
                obj_str = objects_list[0]
            elif len(objects_list) == 2:
                obj_str = " and ".join(objects_list)
            else:
                obj_str = ", ".join(objects_list[:-1]) + f" and {objects_list[-1]}"
        else:
            obj_str = "workflow objects"
        
        db_str = ""
        if databases:
            db = list(databases)[0]
            db_str = f" in {db}"
        
        instruction = f"{action_str.capitalize()} {obj_str}{db_str} in {app}"
        
        # 构建权重信息
        weights = []
        for action in actions:
            weights.append((action, KeywordWeights.CRITICAL))
        for obj in objects_list:
            weights.append((obj, KeywordWeights.HIGH))
        if databases:
            weights.append((list(databases)[0], KeywordWeights.MEDIUM))
        
        return {
            "instruction": instruction,
            "weights": weights,
            "actions": list(actions),
            "objects": objects_list,
            "databases": list(databases)
        }
    
    # ========== 文件级数据生成 ==========
    def generate_file_data(self, workflow: Dict, file_id: str) -> Dict[str, Any]:
        """
        生成文件级数据（直接使用原始workflow + file_id）
        """
        result = workflow.copy()
        result['file_id'] = file_id
        return result
    
    # ========== 步骤级指令生成 ==========
    def generate_step_instruction(self, step: Dict, step_index: int, total_steps: int) -> str:
        """
        生成步骤级指令（简洁格式，不含Step编号）
        示例: "Open MS Kabel" 而不是 "Step 1/7: Open MS Kabel"
        """
        method = step.get('method', '').strip()
        obj = step.get('object', '').strip()  # 保持原始对象名，不进行清理
        
        # 简化操作名
        verb = self._categorize_operation(method)
        if verb == "Other":
            verb = method
        
        # 记录对象名供权重提取器使用
        if obj and obj.lower() not in ['object', 'object editor', 'default']:
            self.object_parser.add_object(obj)
        
        # 构建步骤指令（不包含Step编号）
        if not obj or obj.lower() in ['object', 'object editor', 'default']:
            step_instruction = f"{verb}"
        else:
            step_instruction = f"{verb} {obj}"
        
        return step_instruction
    
    def generate_step_instruction_with_weights(self, step: Dict, step_index: int, total_steps: int) -> Dict[str, Any]:
        """
        生成步骤级指令及其关键词权重
        
        Returns:
            {
                "instruction": "Create MS Kabel",
                "keyword_weights": {
                    "keywords": [["Create", 3.0], ["MS Kabel", 2.0]],
                    "avg_weight": 2.5,
                    "max_weight": 3.0,
                    "keyword_count": 2
                }
            }
        """
        # 生成指令（不含Step编号）
        instruction = self.generate_step_instruction(step, step_index, total_steps)
        
        # 提取关键词权重（此时object_parser已包含该对象名）
        keyword_weights = self.keyword_extractor.get_keyword_weights_dict(instruction)
        
        return {
            "instruction": instruction,
            "keyword_weights": keyword_weights
        }
    
    # ========== 步骤级数据生成 ==========
    def generate_step_data(self, step: Dict, step_index: int, file_id: str) -> Dict[str, Any]:
        """
        生成步骤级数据（直接使用原始step + file_id + step_index）
        """
        step_data_item = step.copy()
        step_data_item["file_id"] = file_id
        step_data_item["step_index"] = step_index
        return step_data_item


def load_parsed_workflows(filepath: str) -> List[Dict]:
    """加载 parsed_workflows.jsonl"""
    logger.info(f"📂 加载 {filepath}...")
    workflows = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                workflow = json.loads(line)
                workflows.append(workflow)
            except json.JSONDecodeError as e:
                logger.warning(f"第 {line_num} 行 JSON 解析失败: {e}")
                continue
    
    logger.info(f"✅ 加载完成: {len(workflows)} 个工作流")
    return workflows


def generate_all_instructions(workflows: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """生成所有指令和数据（分离输出）"""
    logger.info("\n📊 生成指令与数据...")
    
    # 第一步：扫描所有工作流，提取所有对象名
    object_parser = ObjectNameParser()
    logger.info("📋 第1步: 扫描所有对象名...")
    for workflow in workflows:
        for step in workflow.get('steps', []):
            obj = step.get('object', '').strip()
            if obj:
                object_parser.add_object(obj)
    logger.info(f"✓ 已识别 {len(object_parser.known_objects)} 个唯一对象")
    
    # 第二步：生成指令和数据
    generator = WeightedInstructionGenerator(use_variants=False, object_parser=object_parser)
    file_instructions = []
    file_data = []
    step_instructions = []
    step_data = []
    
    for workflow in tqdm(workflows, desc="处理工作流"):
        file_id = workflow.get('file_id')
        steps = workflow.get('steps', [])
        total_steps = len(steps)
        
        if total_steps == 0:
            continue
        
        # ============ 文件级指令（带权重） ============
        file_instr_result = generator.generate_file_instruction_with_weights(workflow)
        
        # 调试：检查结果
        if not file_instr_result:
            logger.error(f"⚠️  文件 {file_id} 生成失败")
            continue
        
        file_instructions.append({
            "file_id": file_id,
            "instruction": file_instr_result.get("instruction", ""),
            "keywords": file_instr_result.get("keywords", []),
            "actions": file_instr_result.get("actions", []),
            "objects": file_instr_result.get("objects", []),
            "databases": file_instr_result.get("databases", [])
        })
        
        # ============ 文件级数据 ============
        file_data.append(generator.generate_file_data(workflow, file_id))
        
        # ============ 步骤级指令和数据 ============
        for step_index, step in enumerate(steps):
            # 步骤级指令（带权重）
            step_instr_with_weights = generator.generate_step_instruction_with_weights(step, step_index, total_steps)
            step_instructions.append({
                "file_id": file_id,
                "step_index": step_index,
                "instruction": step_instr_with_weights["instruction"],
                "keyword_weights": step_instr_with_weights["keyword_weights"]
            })
            
            # 步骤级数据
            step_data.append(generator.generate_step_data(step, step_index, file_id))
    
    logger.info(f"✅ 生成完成:")
    logger.info(f"   - 文件级指令: {len(file_instructions)}")
    logger.info(f"   - 文件级数据: {len(file_data)}")
    logger.info(f"   - 步骤级指令: {len(step_instructions)}")
    logger.info(f"   - 步骤级数据: {len(step_data)}")
    
    return file_instructions, file_data, step_instructions, step_data


def save_instructions(
    file_instructions: List[Dict],
    file_data: List[Dict],
    step_instructions: List[Dict],
    step_data: List[Dict],
    output_dir: str
) -> Dict[str, Path]:
    """保存所有输出文件"""
    logger.info("\n💾 保存分离的文件...")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件级指令
    file_instr_path = output_dir / "file_level_instructions.jsonl"
    with open(file_instr_path, 'w', encoding='utf-8') as f:
        for item in file_instructions:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"✅ {file_instr_path.name} ({len(file_instructions)} 条)")
    
    # 保存文件级数据
    file_data_path = output_dir / "file_level_data.jsonl"
    with open(file_data_path, 'w', encoding='utf-8') as f:
        for item in file_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"✅ {file_data_path.name} ({len(file_data)} 条)")
    
    # 保存步骤级指令
    step_instr_path = output_dir / "step_level_instructions.jsonl"
    with open(step_instr_path, 'w', encoding='utf-8') as f:
        for item in step_instructions:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"✅ {step_instr_path.name} ({len(step_instructions)} 条)")
    
    # 保存步骤级数据
    step_data_path = output_dir / "step_level_data.jsonl"
    with open(step_data_path, 'w', encoding='utf-8') as f:
        for item in step_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"✅ {step_data_path.name} ({len(step_data)} 条)")
    
    return {
        "file_instructions": file_instr_path,
        "file_data": file_data_path,
        "step_instructions": step_instr_path,
        "step_data": step_data_path
    }


def show_samples(
    file_instructions: List[Dict],
    file_data: List[Dict],
    step_instructions: List[Dict],
    step_data: List[Dict]
):
    """展示生成的样本数据"""
    logger.info("\n" + "=" * 80)
    logger.info("📌 数据样本展示")
    logger.info("=" * 80)
    
    if file_instructions:
        logger.info("\n[File #0] 文件级指令与数据：\n")
        sample_file = file_instructions[0]
        logger.info(f"  📄 文件级指令（带权重）:")
        logger.info(f"     instruction: {sample_file['instruction']}")
        logger.info(f"     keywords: {sample_file['keywords'][:3]}... (共{len(sample_file['keywords'])}个)")
        logger.info(f"     actions: {sample_file['actions']}")
        logger.info(f"     objects: {sample_file['objects'][:3]}")
        
        if file_data:
            sample_data = file_data[0]
            logger.info(f"\n  📊 文件级数据:")
            logger.info(f"     test_app: {sample_data.get('test_app', 'N/A')}")
            logger.info(f"     total_steps: {len(sample_data.get('steps', []))}")
            logger.info(f"     file_id: {sample_data.get('file_id', 'N/A')}")
    
    if step_instructions and step_data:
        logger.info(f"\n[Steps] 步骤级指令与数据（前2条）：\n")
        for i in range(min(2, len(step_instructions))):
            instr = step_instructions[i]
            data = step_data[i]
            logger.info(f"  Step #{i}:")
            logger.info(f"    📝 指令: {instr['instruction']}")
            
            # 显示关键词权重
            weights = instr.get('keyword_weights', {})
            if weights.get('keywords'):
                logger.info(f"    🏷️  关键词权重:")
                for keyword, weight in weights['keywords'][:3]:  # 显示前3个关键词
                    logger.info(f"      - {keyword}: {weight}")
                if len(weights['keywords']) > 3:
                    logger.info(f"      ... 及{len(weights['keywords']) - 3}个其他关键词")
                logger.info(f"      平均权重: {weights.get('avg_weight', 0):.2f}, 最高权重: {weights.get('max_weight', 0):.1f}")
            
            logger.info(f"    📊 数据: file_id={data.get('file_id', 'N/A')}, step_index={data.get('step_index', 'N/A')}, object={data.get('object', 'N/A')}")



def main():
    logger.info("=" * 80)
    logger.info("📋 综合指令与数据生成 - 输出4个分离的JSONL文件（包含关键词权重）")
    logger.info("=" * 80)
    logger.info("\n🎯 功能说明:")
    logger.info("  文件级指令: 结构化表达 + 权重标注")
    logger.info("  文件级数据: 原始workflow数据")
    logger.info("  步骤级指令: Step X/Y格式 + 关键词权重")
    logger.info("    ├─ 动作词权重: 3.0（Create/Update等）")
    logger.info("    ├─ 对象名权重: 2.0（MS Kabel等）")
    logger.info("    └─ 上下文词权重: 1.5（数据库、模块名等）")
    logger.info("  步骤级数据: 原始step数据")
    logger.info("=" * 80)
    
    # 参数
    input_file = "data/processed/parsed_workflows.jsonl"
    output_dir = "data/processed"
    
    # 检查输入文件
    if not Path(input_file).exists():
        logger.error(f"❌ 输入文件不存在: {input_file}")
        return
    
    # 加载工作流
    workflows = load_parsed_workflows(input_file)
    
    # 生成指令和数据
    file_instructions, file_data, step_instructions, step_data = generate_all_instructions(workflows)
    
    # 保存为JSONL文件
    output_files = save_instructions(file_instructions, file_data, step_instructions, step_data, output_dir)
    
    # 显示样本
    show_samples(file_instructions, file_data, step_instructions, step_data)
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ 指令与数据生成完成！")
    logger.info("✅ 关键词权重已添加到 step_level_instructions.jsonl！")
    logger.info("=" * 80)
    logger.info(f"📁 输出目录: {output_dir}")
    logger.info(f"📊 统计:")
    logger.info(f"   - 文件数: {len(file_instructions)}")
    logger.info(f"   - 步骤数: {len(step_instructions)}")
    logger.info(f"📋 输出文件:")
    for name, path in output_files.items():
        logger.info(f"   ✓ {path.name}")
    logger.info("\n💡 关键词权重信息:")
    logger.info(f"   - 动作词（Create/Update等）: 权重 {KeywordWeights.CRITICAL}")
    logger.info(f"   - 对象名（MS Kabel等）: 权重 {KeywordWeights.HIGH}")
    logger.info(f"   - 上下文词（数据库、模块等）: 权重 {KeywordWeights.MEDIUM}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
