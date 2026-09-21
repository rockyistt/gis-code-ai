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
- 步骤级数据：完整的原始JSON + 前置后继步骤上下文
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

# 步骤级指令模板（按 (module, method) 分类）
STEP_INSTRUCTION_TEMPLATES = {
    ("Tabs", "Select Tab"): {
        "template": "Select {object} in {database}",
    },
    ("Buttons", "Click Oneshot Button"): {
        "template": "Click {object} button in {database}",
    },
    ("Editor(s)", "Open Object"): {
        "template": "Open {object} of station {station_nummer}",
        "fallback_template": "Open {object} in {database}",
    },
    ("Editor(s)", "Open Object with ID"): {
        "template": "Open {object} with id {object_id} of station {station_nummer} in {database}",
        "fallback_template": "Open {object} with id {object_id} in {database}",
    },
    ("Editor(s)", "Verify Field"): {
        "template": "Verify {field_name} of {object} in {database}",
        "fallback_template": "Verify {object} in {database}",
    },
    ("Editor(s)", "Switch Spatial Context"): {
        "template": "Switch to {spatial_context} for {object} in {database}",
        "fallback_template": "Switch spatial context for {object} in {database}",
    },
    ("Hierarchy Viewer", "Select first HV object"): {
        "template": "Select first hierarchy {object} indexed {id_hv} in {database}",
        "fallback_template": "Select first hierarchy {object} in {database}",
    },
    ("Hierarchy Viewer", "Select second HV object"): {
        "template": "Select second hierarchy {object} indexed {id_hv} in {database}",
        "fallback_template": "Select second hierarchy {object} in {database}",
    },
    ("Datamodel Consistency Check", "Datamodel Check"): {
        "template": "Run datamodel consistency check in {database}",
    },
    ("Datamodel CRUD", "Create"): {
        "template": "Create {object} where {fields} have {values} in {database}",
        "fallback_template": "Create {object} in {database}",
    },
    ("Datamodel CRUD", "Update"): {
        "template": "Update {object} where {fields} have {values} in {database}",
        "fallback_template": "Update {object} in {database}",
    },
    ("Datamodel CRUD", "Delete"): {
        "template": "Delete {object} in {database}",
    },
}


class KeywordWeights:
    """关键词权重定义"""
    CRITICAL = 3.0    # 核心动作词
    HIGH = 2.0        # 重要对象和方法
    MEDIUM = 1.5      # 修饰语和上下文
    NORMAL = 1.0      # 一般词汇
    CONTEXT_DB = 1.8  # 数据库上下文
    CONTEXT_VARIANT = 1.6  # 方法变体上下文
    CONTEXT_ID = 1.4  # 对象ID上下文
    CONTEXT_DATA = 1.2  # 测试数据上下文


class TemplateInstructionExtractor:
    """基于 (module, method) 模板的步骤级指令提取器"""

    # 可选字段：若这些字段为空则可用 fallback_template
    OPTIONAL_FIELDS = {"station_nummer", "spatial_context", "field_name", "fields", "values", "id_hv"}

    def __init__(self):
        self.templates = STEP_INSTRUCTION_TEMPLATES

    def _clean_text(self, value) -> str:
        if value is None:
            return ""
        try:
            text = str(value).strip()
        except Exception:
            return ""
        if text.lower() in {"none", "nan", "null", "n/a", ""}:
            return ""
        return text

    def _clean_database(self, value) -> str:
        return self._clean_text(value).replace(":", "").strip()

    def extract_station_nummer(self, test_data) -> str:
        """从嵌套 test_data 中提取 Station Nummer；不存在时返回空字符串。"""
        if not isinstance(test_data, dict):
            return ""
        for section_value in test_data.values():
            if not isinstance(section_value, dict):
                continue
            for field_value in section_value.values():
                if not isinstance(field_value, dict):
                    continue
                val = self._clean_text(field_value.get("Station Nummer"))
                if val:
                    return val
        return ""

    def extract_spatial_context(self, test_data) -> str:
        """从 test_data editor 节中提取 Spatial Context 值。"""
        if not isinstance(test_data, dict):
            return ""
        for section_value in test_data.values():
            if not isinstance(section_value, dict):
                continue
            for field_value in section_value.values():
                if not isinstance(field_value, dict):
                    continue
                val = self._clean_text(field_value.get("Spatial Context"))
                if val and val.lower() != "passed":
                    return val
        return ""

    def extract_verify_field(self, test_data) -> str:
        """从 test_data editor 节中推断被验证的字段名。"""
        if not isinstance(test_data, dict):
            return ""
        editor = test_data.get("editor", {})
        if not isinstance(editor, dict):
            return ""
        for field_value in editor.values():
            if not isinstance(field_value, dict):
                continue
            for key in field_value:
                if key.lower() not in {"id", "station nummer", "spatial context"}:
                    return key
        return ""

    def extract_crud_fields_values(self, test_data, operation: str) -> Tuple[str, str]:
        """从 test_data 的 create/update 节提取字段名和对应值（各最多3个）。"""
        if not isinstance(test_data, dict):
            return "", ""
        section = test_data.get(operation.lower(), {})
        if not isinstance(section, dict) or not section:
            return "", ""
        fields: List[str] = []
        values: List[str] = []
        for field_val in section.values():
            if isinstance(field_val, dict):
                for subkey, subval in field_val.items():
                    text_val = self._clean_text(subval)
                    if text_val and text_val.lower() != "passed":
                        fields.append(subkey)
                        values.append(text_val)
        if not fields:
            return "", ""
        return ", ".join(fields[:3]), ", ".join(values[:3])

    def build_context(self, step: Dict) -> Dict[str, Any]:
        """把一行 step 数据映射为模板所需的上下文字典。"""
        method = self._clean_text(step.get("method", ""))
        test_data = step.get("test_data", {})

        fields_str, values_str = "", ""
        if method == "Create":
            fields_str, values_str = self.extract_crud_fields_values(test_data, "create")
        elif method == "Update":
            fields_str, values_str = self.extract_crud_fields_values(test_data, "update")

        return {
            "database":       self._clean_database(step.get("database", "")),
            "object":         self._clean_text(step.get("object", "")),
            "object_id":      self._clean_text(step.get("object_id", "")),
            "module":         self._clean_text(step.get("module", "")),
            "method":         method,
            "command":        self._clean_text(step.get("command", "")),
            "station_nummer": self.extract_station_nummer(test_data),
            "spatial_context": self.extract_spatial_context(test_data),
            "field_name":     self.extract_verify_field(test_data) or self._clean_text(step.get("command", "")),
            "fields":         fields_str,
            "values":         values_str,
            "id_hv":          self._clean_text(step.get("object_id", "")),
        }

    def render_instruction(self, step: Dict) -> str:
        """根据 (module, method) 选择模板并渲染指令；字段缺失时自动降级到 fallback_template。"""
        module = self._clean_text(step.get("module", ""))
        method = self._clean_text(step.get("method", ""))
        pair = (module, method)

        template_info = self.templates.get(pair)
        if not template_info:
            # 未注册的组合：用 method + object + database 构建默认指令
            obj = self._clean_text(step.get("object", ""))
            db = self._clean_database(step.get("database", ""))
            parts = [method] if method else ["Process"]
            if obj:
                parts.append(obj)
            if db:
                parts.append(f"in {db}")
            return " ".join(parts)

        context = self.build_context(step)
        template = template_info.get("template", "")
        fallback = template_info.get("fallback_template")

        # 若主模板包含某个可选字段但该字段为空，切换到 fallback
        if fallback:
            for field in self.OPTIONAL_FIELDS:
                if "{" + field + "}" in template and not context.get(field):
                    template = fallback
                    break

        try:
            return template.format(**context)
        except KeyError:
            if fallback and template != fallback:
                try:
                    return fallback.format(**context)
                except KeyError:
                    pass
            return f"{method} {context.get('object', '')} in {context.get('database', '')}".strip()

    def extract_context_for_weights(self, step: Dict) -> Dict[str, Any]:
        """提取与 KeywordWeightExtractor 兼容的上下文字典。"""
        db = self._clean_database(step.get("database", ""))
        obj_id = self._clean_text(step.get("object_id", ""))
        method = self._clean_text(step.get("method", ""))

        context: Dict[str, Any] = {}
        weights_list: List[float] = []

        if db:
            context["database"] = db
            weights_list.append(KeywordWeights.CONTEXT_DB)
        if "with id" in method.lower():
            context["method_variant"] = "With ID"
            weights_list.append(KeywordWeights.CONTEXT_VARIANT)
        if obj_id:
            context["object_id"] = obj_id
            weights_list.append(KeywordWeights.CONTEXT_ID)

        context["has_id"] = bool(obj_id)
        context["context_score"] = round(sum(weights_list) / len(weights_list), 2) if weights_list else 0.0
        return context


class ObjectNameParser:
    """解析对象名，识别复合词组"""

    def __init__(self):
        """初始化对象名解析器"""
        self.known_objects = set()

    def add_object(self, obj_name: str):
        """添加已知的对象名"""
        if not isinstance(obj_name, str):
            obj_name = str(obj_name) if obj_name else ""

        obj_name = obj_name.strip()
        if obj_name and len(obj_name) > 2:
            self.known_objects.add(obj_name)

    def find_object_name(self, text: str) -> Optional[str]:
        """在文本中查找对象名，返回最长匹配的对象名"""
        if not isinstance(text, str):
            text = str(text) if text else ""

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

    def extract_keywords_with_weights(
        self, instruction: str, context: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float]]:
        """从指令文本中提取关键词及其权重，支持上下文字段"""
        if not isinstance(instruction, str):
            instruction = str(instruction) if instruction else ""

        keywords = []
        remaining_text = instruction

        object_name = self.object_parser.find_object_name(instruction)
        if object_name:
            keywords.append((object_name, KeywordWeights.HIGH))
            remaining_text = instruction.replace(object_name, '', 1).strip()

        tokens = remaining_text.split()
        for token in tokens:
            clean_token = re.sub(r'[^\w\s]', '', token)
            if not clean_token:
                continue

            if object_name and clean_token in object_name.split():
                continue

            is_action = False
            for action in self.action_words:
                if clean_token.lower() == action.lower():
                    is_action = True
                    break

            if is_action:
                keywords.append((clean_token, KeywordWeights.CRITICAL))
            elif clean_token.lower() in self.context_keywords:
                keywords.append((clean_token, KeywordWeights.MEDIUM))
            elif len(clean_token) > 2 and not clean_token.isdigit():
                keywords.append((clean_token, KeywordWeights.HIGH))

        if context:
            if context.get('database'):
                keywords.append((f"[DB:{context['database']}]", KeywordWeights.CONTEXT_DB))

            if context.get('method_variant'):
                keywords.append((context['method_variant'], KeywordWeights.CONTEXT_VARIANT))

            if context.get('object_id'):
                keywords.append(('[ID]', KeywordWeights.CONTEXT_ID))

        keywords.sort(key=lambda x: -x[1])
        return keywords

    def get_keyword_weights_dict(
        self, instruction: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """获取指令的完整关键词权重信息，支持上下文字段"""
        keywords = self.extract_keywords_with_weights(instruction, context)

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
    """综合指令生成器"""

    def __init__(self, use_variants: bool = False, object_parser: Optional[ObjectNameParser] = None):
        self.templates = StructuredInstructionTemplate()
        self.use_variants = use_variants
        self.object_parser = object_parser or ObjectNameParser()
        self.keyword_extractor = KeywordWeightExtractor(self.object_parser)
        self.template_extractor = TemplateInstructionExtractor()

    def _clean_object_name(self, obj: str) -> str:
        """清理对象名 - 移除E/L/HV前缀"""
        if not isinstance(obj, str):
            obj = str(obj) if obj else ""

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
        if not isinstance(obj, str):
            obj = str(obj) if obj else ""

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

    def generate_file_instruction_with_weights(self, workflow: Dict) -> Dict[str, Any]:
        """生成文件级指令（带权重）"""
        steps = workflow.get('steps', [])
        app = workflow.get('test_app', 'GIS system')

        if not steps:
            return {
                "instruction": f"Test workflow in {app}",
                "weights": [],
                "actions": [],
                "objects": [],
                "databases": []
            }

        actions = set()
        objects = set()
        databases = set()

        for step in steps:
            method = step.get('method', '')
            if not isinstance(method, str):
                method = str(method) if method else ""

            obj_raw = step.get('object', '')
            if not isinstance(obj_raw, str):
                obj_raw = str(obj_raw) if obj_raw else ""
            obj = self._clean_object_name(obj_raw)

            db = step.get('database', '')
            if not isinstance(db, str):
                db = str(db) if db else ""
            db = db.replace(':', '').strip()

            if method in ['Create', 'Update', 'Delete']:
                actions.add(method.lower())

            if obj and self._is_valid_object(obj):
                objects.add(obj)

            if db:
                databases.add(db)

        action_str = ", ".join(sorted(actions)) if actions else "manage"

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

        keyword_weights_info = self.keyword_extractor.get_keyword_weights_dict(instruction)

        return {
            "instruction": instruction,
            "weights": keyword_weights_info.get("keywords", []),
            "avg_weight": keyword_weights_info.get("avg_weight", 0.0),
            "max_weight": keyword_weights_info.get("max_weight", 0.0),
            "actions": sorted(actions),
            "objects": objects_list,
            "databases": sorted(databases),
        }

    def generate_step_instruction(self, step: Dict, step_index: int, total_steps: int) -> str:
        """生成步骤级指令（纯文本）"""
        base_instruction = self.template_extractor.render_instruction(step)
        return f"Step {step_index + 1}/{total_steps}: {base_instruction}"

    def generate_step_instruction_with_weights(
        self, step: Dict, step_index: int, total_steps: int
    ) -> Dict[str, Any]:
        """生成步骤级指令（带权重+上下文字段）"""
        base_instruction = self.template_extractor.render_instruction(step)
        context = self.template_extractor.extract_context_for_weights(step)
        keyword_info = self.keyword_extractor.get_keyword_weights_dict(base_instruction, context)

        return {
            "step_index": step_index,
            "step_number": f"Step {step_index + 1}/{total_steps}",
            "instruction": base_instruction,
            "keywords": keyword_info.get("keywords", []),
            "avg_weight": keyword_info.get("avg_weight", 0.0),
            "max_weight": keyword_info.get("max_weight", 0.0),
            "context": context,
        }

    def generate_file_data(self, workflow: Dict) -> Dict[str, Any]:
        """生成文件级数据（简化）"""
        steps = workflow.get('steps', [])
        file_id = workflow.get('file_id', '')
        test_app = workflow.get('test_app', '')
        test_cases = workflow.get('test_cases', [])

        crud_stats = {"create": 0, "read": 0, "update": 0, "delete": 0}
        objects_set = set()
        databases_set = set()

        for step in steps:
            method = step.get('method', '').lower()
            obj = step.get('object', '')
            db = step.get('database', '')

            if 'create' in method:
                crud_stats['create'] += 1
            elif 'read' in method or 'open' in method or 'view' in method or 'select' in method:
                crud_stats['read'] += 1
            elif 'update' in method or 'edit' in method or 'modify' in method:
                crud_stats['update'] += 1
            elif 'delete' in method or 'remove' in method:
                crud_stats['delete'] += 1

            if obj:
                objects_set.add(self._clean_object_name(obj))
            if db:
                databases_set.add(db.replace(':', '').strip())

        return {
            "file_id": file_id,
            "test_app": test_app,
            "test_cases": test_cases,
            "total_steps": len(steps),
            "crud_stats": crud_stats,
            "unique_objects": list(objects_set),
            "unique_databases": list(databases_set),
            "steps": steps,
        }

    def generate_step_data(
        self, workflow: Dict, step_index: int
    ) -> Dict[str, Any]:
        """生成步骤级数据（完整JSON+上下文）"""
        steps = workflow.get('steps', [])
        if step_index >= len(steps):
            return {}

        step = steps[step_index]
        total_steps = len(steps)

        prev_step = steps[step_index - 1] if step_index > 0 else None
        next_step = steps[step_index + 1] if step_index < total_steps - 1 else None

        return {
            "file_id": workflow.get('file_id', ''),
            "test_app": workflow.get('test_app', ''),
            "step_index": step_index,
            "step_number": f"Step {step_index + 1}/{total_steps}",
            "current_step": step,
            "previous_step": prev_step,
            "next_step": next_step,
            "total_steps": total_steps,
            "test_data": step.get('test_data', {}),
        }


def load_parsed_workflows(input_path: str) -> List[Dict]:
    """加载 parsed_workflows.jsonl 文件"""
    workflows = []
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    workflow = json.loads(line)
                    workflows.append(workflow)
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: JSON parse error - {e}")
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_path}")
        return []
    except Exception as e:
        logger.error(f"Error loading file: {e}")
        return []

    logger.info(f"Loaded {len(workflows)} workflows from {input_path}")
    return workflows


def generate_all_instructions(
    workflows: List[Dict], generator: WeightedInstructionGenerator
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """生成文件级和步骤级的指令与数据"""
    file_instructions = []
    file_data_list = []
    step_instructions = []
    step_data_list = []

    for workflow in tqdm(workflows, desc="Generating instructions"):
        # 文件级
        file_instr = generator.generate_file_instruction_with_weights(workflow)
        file_instructions.append(file_instr)

        file_data = generator.generate_file_data(workflow)
        file_data_list.append(file_data)

        # 步骤级
        steps = workflow.get('steps', [])
        total_steps = len(steps)

        for step_idx in range(total_steps):
            step_instr = generator.generate_step_instruction_with_weights(
                steps[step_idx], step_idx, total_steps
            )
            step_instructions.append(step_instr)

            step_data = generator.generate_step_data(workflow, step_idx)
            step_data_list.append(step_data)

    logger.info(f"Generated {len(file_instructions)} file-level entries")
    logger.info(f"Generated {len(step_instructions)} step-level entries")

    return file_instructions, file_data_list, step_instructions, step_data_list


def save_instructions(
    output_dir: str,
    file_instructions: List[Dict],
    file_data_list: List[Dict],
    step_instructions: List[Dict],
    step_data_list: List[Dict],
):
    """保存4个分离的JSONL输出文件"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files = [
        ("file_level_instructions_weighted.jsonl", file_instructions),
        ("file_level_data.jsonl", file_data_list),
        ("step_level_instructions.jsonl", step_instructions),
        ("step_level_data.jsonl", step_data_list),
    ]

    for filename, data in files:
        filepath = output_path / filename
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
            logger.info(f"✓ Saved {len(data)} items to {filepath}")
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")


def show_samples(
    file_instructions: List[Dict],
    file_data_list: List[Dict],
    step_instructions: List[Dict],
    step_data_list: List[Dict],
    num_samples: int = 2,
):
    """展示生成的数据样本（用于调试）"""
    logger.info("\n" + "=" * 80)
    logger.info("SAMPLE: File-Level Instructions with Weights")
    logger.info("=" * 80)
    for item in file_instructions[:num_samples]:
        logger.info(json.dumps(item, ensure_ascii=False, indent=2))

    logger.info("\n" + "=" * 80)
    logger.info("SAMPLE: File-Level Data")
    logger.info("=" * 80)
    for item in file_data_list[:num_samples]:
        logger.info(json.dumps(item, ensure_ascii=False, indent=2))

    logger.info("\n" + "=" * 80)
    logger.info("SAMPLE: Step-Level Instructions with Weights")
    logger.info("=" * 80)
    for item in step_instructions[:num_samples]:
        logger.info(json.dumps(item, ensure_ascii=False, indent=2))

    logger.info("\n" + "=" * 80)
    logger.info("SAMPLE: Step-Level Data")
    logger.info("=" * 80)
    for item in step_data_list[:num_samples]:
        logger.info(json.dumps(item, ensure_ascii=False, indent=2))


def main():
    """主入口函数"""
    input_file = "data/processed/parsed_workflows.jsonl"
    output_dir = "data/processed"

    workflows = load_parsed_workflows(input_file)
    if not workflows:
        logger.error("No workflows loaded. Exiting.")
        return

    object_parser = ObjectNameParser()
    for workflow in workflows:
        steps = workflow.get('steps', [])
        for step in steps:
            obj = step.get('object', '')
            if obj:
                object_parser.add_object(obj)

    logger.info(f"Scanned {len(object_parser.known_objects)} unique objects")

    generator = WeightedInstructionGenerator(object_parser=object_parser)
    file_instructions, file_data_list, step_instructions, step_data_list = generate_all_instructions(
        workflows, generator
    )

    save_instructions(output_dir, file_instructions, file_data_list, step_instructions, step_data_list)

    show_samples(file_instructions, file_data_list, step_instructions, step_data_list)

    logger.info("\n✅ All done!")


if __name__ == '__main__':
    main()
