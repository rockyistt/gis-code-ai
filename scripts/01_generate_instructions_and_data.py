#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ç»¼åˆæŒ‡ä»¤å’Œæ•°æ®ç”Ÿæˆå™¨ - è¾“å‡º4ä¸ªåˆ†ç¦»çš„JSONLæ–‡ä»¶

æ•°æ®æµï¼š
1. åŠ è½½ parsed_workflows.jsonl
2. ç”Ÿæˆ4ä¸ªåˆ†ç¦»çš„æ–‡ä»¶ï¼š
   âœ“ file_level_instructions_weighted.jsonl - æ–‡ä»¶çº§æŒ‡ä»¤ï¼ˆå¸¦æƒé‡ï¼‰æ¥è‡ªold versionè„šæœ¬
   âœ“ file_level_data.jsonl - æ–‡ä»¶çº§æ•°æ®ï¼ˆç®€åŒ–ï¼‰ æ¥è‡ª01è„šæœ¬
   âœ“ step_level_instructions.jsonl - æ­¥éª¤çº§æŒ‡ä»¤ï¼ˆæ¸…æ™°æ ¼å¼ï¼‰ æ¥è‡ª01è„šæœ¬
   âœ“ step_level_data.jsonl - æ­¥éª¤çº§æ•°æ®ï¼ˆå®Œæ•´JSON+ä¸Šä¸‹æ–‡ï¼‰ æ¥è‡ª01è„šæœ¬

ç»¼åˆä¼˜åŠ¿ï¼š
- æ–‡ä»¶çº§æŒ‡ä»¤ï¼šç»“æž„åŒ–è¡¨è¾¾ + æƒé‡æ ‡æ³¨
- æ–‡ä»¶çº§æ•°æ®ï¼šCRUDç»Ÿè®¡ + å¯¹è±¡èšåˆ
- æ­¥éª¤çº§æŒ‡ä»¤ï¼šè‡ªç„¶è¯­è¨€ + æ¸…æ™°çš„Stepç¼–å·
- æ­¥éª¤çº§æ•°æ®ï¼šå®Œæ•´çš„åŽŸå§‹JSON + å‰ç½®åŽç»­æ­¥éª¤ä¸Šä¸‹æ–‡
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

# å®šä¹‰åŠ¨ä½œè¯é›†åˆï¼ˆç”¨äºŽå…³é”®è¯æƒé‡æå–ï¼‰
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

# å®šä¹‰ä¸Šä¸‹æ–‡è¯é›†åˆ
CONTEXT_KEYWORDS = {
    "elektra", "database", "module", "editor", "field", "tab", "panel",
    "window", "dialog", "menu", "button", "form", "table", "list",
    "workflow", "process", "system", "app", "application", "gis"
}

# æ­¥éª¤çº§æŒ‡ä»¤æ¨¡æ¿ï¼ˆæŒ‰ (module, method) åˆ†ç±»ï¼‰
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
    """å…³é”®è¯æƒé‡å®šä¹‰"""
    CRITICAL = 3.0    # æ ¸å¿ƒåŠ¨ä½œè¯
    HIGH = 2.0        # é‡è¦å¯¹è±¡å’Œæ–¹æ³•
    MEDIUM = 1.5      # ä¿®é¥°è¯­å’Œä¸Šä¸‹æ–‡
    NORMAL = 1.0      # ä¸€èˆ¬è¯æ±‡
    CONTEXT_DB = 1.8  # æ•°æ®åº“ä¸Šä¸‹æ–‡
    CONTEXT_VARIANT = 1.6  # æ–¹æ³•å˜ä½“ä¸Šä¸‹æ–‡
    CONTEXT_ID = 1.4  # å¯¹è±¡IDä¸Šä¸‹æ–‡
    CONTEXT_DATA = 1.2  # æµ‹è¯•æ•°æ®ä¸Šä¸‹æ–‡


class TemplateInstructionExtractor:
    """åŸºäºŽ (module, method) æ¨¡æ¿çš„æ­¥éª¤çº§æŒ‡ä»¤æå–å™¨"""

    # å¯é€‰å­—æ®µï¼šè‹¥è¿™äº›å­—æ®µä¸ºç©ºåˆ™å¯ç”¨ fallback_template
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

    # ---------- test_data å­—æ®µæå– ----------

    def extract_station_nummer(self, test_data) -> str:
        """ä»ŽåµŒå¥— test_data ä¸­æå– Station Nummerï¼›ä¸å­˜åœ¨æ—¶è¿”å›žç©ºå­—ç¬¦ä¸²ã€‚"""
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
        """ä»Ž test_data editor èŠ‚ä¸­æå– Spatial Context å€¼ã€‚"""
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
        """ä»Ž test_data editor èŠ‚ä¸­æŽ¨æ–­è¢«éªŒè¯çš„å­—æ®µåã€‚"""
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
        """ä»Ž test_data çš„ create/update èŠ‚æå–å­—æ®µåå’Œå¯¹åº”å€¼ï¼ˆå„æœ€å¤š3ä¸ªï¼‰ã€‚"""
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

    # ---------- ä¸Šä¸‹æ–‡æž„å»ºä¸ŽæŒ‡ä»¤æ¸²æŸ“ ----------

    def build_context(self, step: Dict) -> Dict[str, Any]:
        """æŠŠä¸€è¡Œ step æ•°æ®æ˜ å°„ä¸ºæ¨¡æ¿æ‰€éœ€çš„ä¸Šä¸‹æ–‡å­—å…¸ã€‚"""
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
            "spatial_context":self.extract_spatial_context(test_data),
            "field_name":     self.extract_verify_field(test_data) or self._clean_text(step.get("command", "")),
            "fields":         fields_str,
            "values":         values_str,
            "id_hv":          self._clean_text(step.get("object_id", "")),
        }

    def render_instruction(self, step: Dict) -> str:
        """æ ¹æ® (module, method) é€‰æ‹©æ¨¡æ¿å¹¶æ¸²æŸ“æŒ‡ä»¤ï¼›å­—æ®µç¼ºå¤±æ—¶è‡ªåŠ¨é™çº§åˆ° fallback_templateã€‚"""
        module = self._clean_text(step.get("module", ""))
        method = self._clean_text(step.get("method", ""))
        pair   = (module, method)

        template_info = self.templates.get(pair)
        if not template_info:
            # æœªæ³¨å†Œçš„ç»„åˆï¼šç”¨ method + object + database æž„å»ºé»˜è®¤æŒ‡ä»¤
            obj = self._clean_text(step.get("object", ""))
            db  = self._clean_database(step.get("database", ""))
            parts = [method] if method else ["Process"]
            if obj:
                parts.append(obj)
            if db:
                parts.append(f"in {db}")
            return " ".join(parts)

        context  = self.build_context(step)
        template = template_info.get("template", "")
        fallback = template_info.get("fallback_template")

        # è‹¥ä¸»æ¨¡æ¿åŒ…å«æŸä¸ªå¯é€‰å­—æ®µä½†è¯¥å­—æ®µä¸ºç©ºï¼Œåˆ‡æ¢åˆ° fallback
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
        """æå–ä¸Ž KeywordWeightExtractor å…¼å®¹çš„ä¸Šä¸‹æ–‡å­—å…¸ã€‚"""
        db     = self._clean_database(step.get("database", ""))
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

        context["has_id"]        = bool(obj_id)
        context["context_score"] = round(sum(weights_list) / len(weights_list), 2) if weights_list else 0.0
        return context


class ObjectNameParser:
    """è§£æžå¯¹è±¡åï¼Œè¯†åˆ«å¤åˆè¯ç»„"""
    
    def __init__(self):
        """åˆå§‹åŒ–å¯¹è±¡åè§£æžå™¨"""
        # ä»Žå·¥ä½œæµä¸­æå–æ‰€æœ‰å”¯ä¸€çš„å¯¹è±¡å
        self.known_objects = set()
    
    def add_object(self, obj_name: str):
        """æ·»åŠ å·²çŸ¥çš„å¯¹è±¡å"""
        if not isinstance(obj_name, str):
            obj_name = str(obj_name) if obj_name else ""
        
        obj_name = obj_name.strip()
        if obj_name and len(obj_name) > 2:
            self.known_objects.add(obj_name)
    
    def find_object_name(self, text: str) -> Optional[str]:
        """åœ¨æ–‡æœ¬ä¸­æŸ¥æ‰¾å¯¹è±¡åï¼Œè¿”å›žæœ€é•¿åŒ¹é…çš„å¯¹è±¡å"""
        if not isinstance(text, str):
            text = str(text) if text else ""
        
        # æŒ‰é•¿åº¦é™åºæŽ’åˆ—ï¼Œä¼˜å…ˆåŒ¹é…é•¿çš„å¯¹è±¡å
        sorted_objects = sorted(self.known_objects, key=len, reverse=True)
        for obj in sorted_objects:
            if obj in text:
                return obj
        return None


class KeywordWeightExtractor:
    """ä»ŽæŒ‡ä»¤ä¸­æå–å…³é”®è¯å¹¶åˆ†é…æƒé‡"""
    
    def __init__(self, object_parser: Optional[ObjectNameParser] = None):
        """åˆå§‹åŒ–å…³é”®è¯æå–å™¨"""
        self.action_words = ACTION_WORDS
        self.context_keywords = CONTEXT_KEYWORDS
        self.object_parser = object_parser or ObjectNameParser()
    
    def extract_keywords_with_weights(self, instruction: str, context: Optional[Dict[str, Any]] = None) -> List[Tuple[str, float]]:
        """
        ä»ŽæŒ‡ä»¤æ–‡æœ¬ä¸­æå–å…³é”®è¯åŠå…¶æƒé‡ï¼Œæ”¯æŒä¸Šä¸‹æ–‡å­—æ®µ
        
        Args:
            instruction: æŒ‡ä»¤æ–‡æœ¬ï¼ˆå¦‚ "Create MS Kabel"ï¼‰
            context: å¯é€‰çš„ä¸Šä¸‹æ–‡å­—å…¸ï¼ˆæ¥è‡ª ContextualFieldExtractorï¼‰
            
        Returns:
            [(keyword, weight), ...] åˆ—è¡¨ï¼ŒæŒ‰æƒé‡é™åºæŽ’åˆ—
        """
        # ç¡®ä¿ instruction æ˜¯å­—ç¬¦ä¸²
        if not isinstance(instruction, str):
            instruction = str(instruction) if instruction else ""
        
        keywords = []
        remaining_text = instruction
        
        # 1. å…ˆå°è¯•è¯†åˆ«å¤åˆå¯¹è±¡åï¼ˆå¦‚"MS Kabel"ã€"MS Aardingstrafo FP"ï¼‰
        object_name = self.object_parser.find_object_name(instruction)
        if object_name:
            keywords.append((object_name, KeywordWeights.HIGH))
            remaining_text = instruction.replace(object_name, '', 1).strip()
        
        # 2. å¤„ç†å‰©ä½™çš„token
        tokens = remaining_text.split()
        for token in tokens:
            # æ¸…é™¤æ ‡ç‚¹ç¬¦å·
            clean_token = re.sub(r'[^\w\s]', '', token)
            if not clean_token:
                continue
            
            # è·³è¿‡å·²ç»æ·»åŠ çš„å¯¹è±¡åä¸­çš„è¯
            if object_name and clean_token in object_name.split():
                continue
            
            # æ£€æŸ¥æ˜¯å¦æ˜¯åŠ¨ä½œè¯ï¼ˆåŒºåˆ†å¤§å°å†™ï¼‰
            is_action = False
            for action in self.action_words:
                if clean_token.lower() == action.lower():
                    is_action = True
                    break
            
            if is_action:
                keywords.append((clean_token, KeywordWeights.CRITICAL))
            # æ£€æŸ¥æ˜¯å¦æ˜¯ä¸Šä¸‹æ–‡è¯
            elif clean_token.lower() in self.context_keywords:
                keywords.append((clean_token, KeywordWeights.MEDIUM))
            # å…¶ä»–è¯ï¼ˆæŽ’é™¤æ•°å­—ï¼‰
            elif len(clean_token) > 2 and not clean_token.isdigit():
                keywords.append((clean_token, KeywordWeights.HIGH))
        
        # 3. æ·»åŠ æ¥è‡ªcontextçš„å…³é”®è¯ï¼ˆå¦‚æžœæä¾›äº†contextï¼Œä»…æ·»åŠ ç®€æ´çš„å­—æ®µï¼‰
        if context:
            if context.get('database'):
                keywords.append((f"[DB:{context['database']}]", KeywordWeights.CONTEXT_DB))
            
            if context.get('method_variant'):
                keywords.append((context['method_variant'], KeywordWeights.CONTEXT_VARIANT))
            
            if context.get('object_id'):
                keywords.append(('[ID]', KeywordWeights.CONTEXT_ID))
            
            # ä¸æ·»åŠ  test_data æƒé‡ - å¤ªå¤æ‚äº†

        
        # æŒ‰æƒé‡é™åºæŽ’åˆ—
        keywords.sort(key=lambda x: -x[1])
        return keywords
    
    def get_keyword_weights_dict(self, instruction: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        èŽ·å–æŒ‡ä»¤çš„å®Œæ•´å…³é”®è¯æƒé‡ä¿¡æ¯ï¼Œæ”¯æŒä¸Šä¸‹æ–‡å­—æ®µ
        
        Args:
            instruction: æŒ‡ä»¤æ–‡æœ¬
            context: å¯é€‰çš„ä¸Šä¸‹æ–‡å­—å…¸
            
        Returns:
            åŒ…å«å…³é”®è¯ã€æƒé‡å’Œç»Ÿè®¡çš„å­—å…¸
        """
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
    """ç»“æž„åŒ–æŒ‡ä»¤æ¨¡æ¿ - åŠ¨ä½œ+å®¾è¯­+çŠ¶è¯­"""
    
    def __init__(self):
        # åŠ¨ä½œè¯åŠå…¶åŒä¹‰è¯
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
        """èŽ·å–åŠ¨ä½œè¯ï¼ˆå¯é€‰ä½¿ç”¨åŒä¹‰è¯ï¼‰"""
        if use_variant and action in self.action_synonyms:
            return random.choice(self.action_synonyms[action])
        return action


class WeightedInstructionGenerator:
    """
    ç»¼åˆæŒ‡ä»¤ç”Ÿæˆå™¨
    - æ–‡ä»¶çº§æŒ‡ä»¤ï¼šå¸¦æƒé‡çš„ç»“æž„åŒ–è¡¨è¾¾ï¼ˆæ¥è‡ªold versionï¼‰
    - æ–‡ä»¶çº§æ•°æ®ï¼šç®€åŒ–çš„å…ƒæ•°æ®å’Œç»Ÿè®¡ï¼ˆæ¥è‡ª01ï¼‰
    - æ­¥éª¤çº§æŒ‡ä»¤ï¼šæ¸…æ™°çš„Step X/Yæ ¼å¼ï¼ˆæ¥è‡ª01ï¼‰+ å…³é”®è¯æƒé‡ + ä¸Šä¸‹æ–‡å­—æ®µ
    - æ­¥éª¤çº§æ•°æ®ï¼šå®Œæ•´çš„åŽŸå§‹JSON+ä¸Šä¸‹æ–‡ï¼ˆæ¥è‡ª01ï¼‰
    """
    
    def __init__(self, use_variants: bool = False, object_parser: Optional[ObjectNameParser] = None):
        self.templates = StructuredInstructionTemplate()
        self.use_variants = use_variants
        self.object_parser = object_parser or ObjectNameParser()
        self.keyword_extractor = KeywordWeightExtractor(self.object_parser)
        self.template_extractor = TemplateInstructionExtractor()  # åŸºäºŽæ¨¡æ¿çš„æŒ‡ä»¤æå–å™¨
    
    def _clean_object_name(self, obj: str) -> str:
        """æ¸…ç†å¯¹è±¡å - ç§»é™¤E/L/HVå‰ç¼€"""
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
        """åˆ¤æ–­æ˜¯å¦ä¸ºæœ‰æ•ˆçš„ä¸šåŠ¡å¯¹è±¡ï¼ˆæŽ’é™¤UIå…ƒç´ å’Œä¼ªå¯¹è±¡ï¼‰"""
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
    
    def _categorize_operation(self, method: str) -> str:
        """å°†æ“ä½œæ–¹æ³•åˆ†ç±»ä¸ºæ ‡å‡†æ“ä½œç±»åž‹"""
        # ç¡®ä¿ method æ˜¯å­—ç¬¦ä¸²
        if not isinstance(method, str):
            method = str(method) if method else ""
        
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
    
    # ========== æ–‡ä»¶çº§æŒ‡ä»¤ç”Ÿæˆ ==========
    def generate_file_instruction_with_weights(self, workflow: Dict) -> Dict[str, Any]:
        """
        ç”Ÿæˆæ–‡ä»¶çº§æŒ‡ä»¤ï¼ˆå¸¦æƒé‡ï¼‰
        é€»è¾‘æ¥è‡ª: 001_generate_instructions_file_old version.py
        """
        steps = workflow.get('steps', [])
        app = workflow.get('test_app', 'GIS system')
        
        # å¦‚æžœæ²¡æœ‰stepsï¼Œè¿”å›žé»˜è®¤å€¼
        if not steps:
            return {
                "instruction": f"Test workflow in {app}",
                "weights": [],
                "actions": [],
                "objects": [],
                "databases": []
            }
        
        # æ”¶é›†å…³é”®ä¿¡æ¯
        actions = set()
        objects = set()
        databases = set()
        
        for step in steps:
            method = step.get('method', '')
            if not isinstance(method, str):
                method = str(method) if method else ""
            else:
                method = method.strip()
            
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
            
            # ä½¿ç”¨æ”¹è¿›çš„å¯¹è±¡éªŒè¯
            if obj and self._is_valid_object(obj):
                objects.add(obj)
            
            if db:
                databases.add(db)
        
        # æž„å»ºæ–‡ä»¶çº§æŒ‡ä»¤
        action_str = ", ".join(sorted(actions)) if actions else "manage"
        
        # æ€»æ˜¯åˆ—ä¸¾å¯¹è±¡ï¼ˆæœ€å¤šæ˜¾ç¤º5ä¸ªï¼‰
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
        
        # æž„å»ºæƒé‡ä¿¡æ¯
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
    
    # ========== æ–‡ä»¶çº§æ•°æ®ç”Ÿæˆ ==========
    def generate_file_data(self, workflow: Dict, file_id: str) -> Dict[str, Any]:
        """
        ç”Ÿæˆæ–‡ä»¶çº§æ•°æ®ï¼ˆç›´æŽ¥ä½¿ç”¨åŽŸå§‹workflow + file_idï¼‰
        """
        result = workflow.copy()
        result['file_id'] = file_id
        return result
    
    # ========== æ­¥éª¤çº§æŒ‡ä»¤ç”Ÿæˆ ==========
    def generate_step_instruction(self, step: Dict, step_index: int, total_steps: int) -> Dict[str, Any]:
        """
        ä½¿ç”¨æ¨¡æ¿ç³»ç»Ÿç”Ÿæˆæ­¥éª¤çº§æŒ‡ä»¤ã€‚

        è¿”å›žæ ¼å¼:
        {
            "instruction": "Create MS Kabel in elektra",
            "context": {"database": "elektra", "object_id": "Passed", "has_id": true, "context_score": 1.8}
        }
        """
        # è®°å½•å¯¹è±¡åä¾›å…³é”®è¯æƒé‡æå–å™¨ä½¿ç”¨
        obj = step.get('object', '')
        if not isinstance(obj, str):
            obj = str(obj) if obj else ''
        obj = obj.strip()
        if obj and obj.lower() not in ['object', 'object editor', 'default']:
            self.object_parser.add_object(obj)

        instruction = self.template_extractor.render_instruction(step)
        context     = self.template_extractor.extract_context_for_weights(step)

        return {
            "instruction": instruction,
            "context": context,
        }

    
    def generate_step_instruction_with_weights(self, step: Dict, step_index: int, total_steps: int) -> Dict[str, Any]:
        """
        ç”Ÿæˆæ­¥éª¤çº§æŒ‡ä»¤åŠå…¶å…³é”®è¯æƒé‡ã€‚

        Returns:
            {
                "instruction": "Create MS Kabel in elektra",
                "keyword_weights": {
                    "keywords": [["Create", 3.0], ["MS Kabel", 2.0], ["[DB:elektra]", 1.8]],
                    "avg_weight": 2.27,
                    "max_weight": 3.0,
                    "keyword_count": 3
                },
                "context": {"database": "elektra", "has_id": false, "context_score": 1.8}
            }
        """
        instr_result = self.generate_step_instruction(step, step_index, total_steps)

        keyword_weights = self.keyword_extractor.get_keyword_weights_dict(
            instr_result["instruction"],
            instr_result["context"]
        )

        return {
            "instruction":    instr_result["instruction"],
            "keyword_weights": keyword_weights,
            "context":        instr_result["context"],
        }
    
    # ========== æ­¥éª¤çº§æ•°æ®ç”Ÿæˆ ==========
    def generate_step_data(self, step: Dict, step_index: int, file_id: str) -> Dict[str, Any]:
        """
        ç”Ÿæˆæ­¥éª¤çº§æ•°æ®ï¼ˆç›´æŽ¥ä½¿ç”¨åŽŸå§‹step + file_id + step_indexï¼‰
        """
        step_data_item = step.copy()
        step_data_item["file_id"] = file_id
        step_data_item["step_index"] = step_index
        return step_data_item


def load_parsed_workflows(filepath: str) -> List[Dict]:
    """åŠ è½½ parsed_workflows.jsonl"""
    logger.info(f"ðŸ“‚ åŠ è½½ {filepath}...")
    workflows = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                workflow = json.loads(line)
                workflows.append(workflow)
            except json.JSONDecodeError as e:
                logger.warning(f"ç¬¬ {line_num} è¡Œ JSON è§£æžå¤±è´¥: {e}")
                continue
    
    logger.info(f"âœ… åŠ è½½å®Œæˆ: {len(workflows)} ä¸ªå·¥ä½œæµ")
    return workflows


def generate_all_instructions(workflows: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """ç”Ÿæˆæ‰€æœ‰æŒ‡ä»¤å’Œæ•°æ®ï¼ˆåˆ†ç¦»è¾“å‡ºï¼‰"""
    logger.info("\nðŸ“Š ç”ŸæˆæŒ‡ä»¤ä¸Žæ•°æ®...")
    
    # ç¬¬ä¸€æ­¥ï¼šæ‰«ææ‰€æœ‰å·¥ä½œæµï¼Œæå–æ‰€æœ‰å¯¹è±¡å
    object_parser = ObjectNameParser()
    logger.info("ðŸ“‹ ç¬¬1æ­¥: æ‰«ææ‰€æœ‰å¯¹è±¡å...")
    for workflow in workflows:
        for step in workflow.get('steps', []):
            obj = step.get('object', '').strip()
            if obj:
                object_parser.add_object(obj)
    logger.info(f"âœ“ å·²è¯†åˆ« {len(object_parser.known_objects)} ä¸ªå”¯ä¸€å¯¹è±¡")
    
    # ç¬¬äºŒæ­¥ï¼šç”ŸæˆæŒ‡ä»¤å’Œæ•°æ®
    generator = WeightedInstructionGenerator(use_variants=False, object_parser=object_parser)
    file_instructions = []
    file_data = []
    step_instructions = []
    step_data = []
    
    for workflow in tqdm(workflows, desc="å¤„ç†å·¥ä½œæµ"):
        file_id = workflow.get('file_id')
        steps = workflow.get('steps', [])
        total_steps = len(steps)
        
        if total_steps == 0:
            continue
        
        # ============ æ–‡ä»¶çº§æŒ‡ä»¤ï¼ˆå¸¦æƒé‡ï¼‰ ============
        file_instr_result = generator.generate_file_instruction_with_weights(workflow)
        
        # è°ƒè¯•ï¼šæ£€æŸ¥ç»“æžœ
        if not file_instr_result:
            logger.error(f"âš ï¸  æ–‡ä»¶ {file_id} ç”Ÿæˆå¤±è´¥")
            continue
        
        file_instructions.append({
            "file_id": file_id,
            "instruction": file_instr_result.get("instruction", ""),
            "keywords": file_instr_result.get("keywords", []),
            "actions": file_instr_result.get("actions", []),
            "objects": file_instr_result.get("objects", []),
            "databases": file_instr_result.get("databases", [])
        })
        
        # ============ æ–‡ä»¶çº§æ•°æ® ============
        file_data.append(generator.generate_file_data(workflow, file_id))
        
        # ============ æ­¥éª¤çº§æŒ‡ä»¤å’Œæ•°æ® ============
        for step_index, step in enumerate(steps):
            # æ­¥éª¤çº§æŒ‡ä»¤ï¼ˆå¸¦æƒé‡ + ä¸Šä¸‹æ–‡ï¼‰
            step_instr_with_weights = generator.generate_step_instruction_with_weights(step, step_index, total_steps)
            step_instructions.append({
                "file_id": file_id,
                "step_index": step_index,
                "instruction": step_instr_with_weights["instruction"],
                "keyword_weights": step_instr_with_weights["keyword_weights"],
                "context": step_instr_with_weights.get("context", {})
            })
            
            # æ­¥éª¤çº§æ•°æ®
            step_data.append(generator.generate_step_data(step, step_index, file_id))
    
    logger.info(f"âœ… ç”Ÿæˆå®Œæˆ:")
    logger.info(f"   - æ–‡ä»¶çº§æŒ‡ä»¤: {len(file_instructions)}")
    logger.info(f"   - æ–‡ä»¶çº§æ•°æ®: {len(file_data)}")
    logger.info(f"   - æ­¥éª¤çº§æŒ‡ä»¤: {len(step_instructions)}")
    logger.info(f"   - æ­¥éª¤çº§æ•°æ®: {len(step_data)}")
    
    return file_instructions, file_data, step_instructions, step_data


def save_instructions(
    file_instructions: List[Dict],
    file_data: List[Dict],
    step_instructions: List[Dict],
    step_data: List[Dict],
    output_dir: str
) -> Dict[str, Path]:
    """ä¿å­˜æ‰€æœ‰è¾“å‡ºæ–‡ä»¶"""
    logger.info("\nðŸ’¾ ä¿å­˜åˆ†ç¦»çš„æ–‡ä»¶...")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # ä¿å­˜æ–‡ä»¶çº§æŒ‡ä»¤
    file_instr_path = output_dir / "file_level_instructions.jsonl"
    with open(file_instr_path, 'w', encoding='utf-8') as f:
        for item in file_instructions:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"âœ… {file_instr_path.name} ({len(file_instructions)} æ¡)")
    
    # ä¿å­˜æ–‡ä»¶çº§æ•°æ®
    file_data_path = output_dir / "file_level_data.jsonl"
    with open(file_data_path, 'w', encoding='utf-8') as f:
        for item in file_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"âœ… {file_data_path.name} ({len(file_data)} æ¡)")
    
    # ä¿å­˜æ­¥éª¤çº§æŒ‡ä»¤
    step_instr_path = output_dir / "step_level_instructions.jsonl"
    with open(step_instr_path, 'w', encoding='utf-8') as f:
        for item in step_instructions:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"âœ… {step_instr_path.name} ({len(step_instructions)} æ¡)")
    
    # ä¿å­˜æ­¥éª¤çº§æ•°æ®
    step_data_path = output_dir / "step_level_data.jsonl"
    with open(step_data_path, 'w', encoding='utf-8') as f:
        for item in step_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    logger.info(f"âœ… {step_data_path.name} ({len(step_data)} æ¡)")
    
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
    """å±•ç¤ºç”Ÿæˆçš„æ ·æœ¬æ•°æ®"""
    logger.info("\n" + "=" * 80)
    logger.info("ðŸ“Œ æ•°æ®æ ·æœ¬å±•ç¤º")
    logger.info("=" * 80)
    
    if file_instructions:
        logger.info("\n[File #0] æ–‡ä»¶çº§æŒ‡ä»¤ä¸Žæ•°æ®ï¼š\n")
        sample_file = file_instructions[0]
        logger.info(f"  ðŸ“„ æ–‡ä»¶çº§æŒ‡ä»¤ï¼ˆå¸¦æƒé‡ï¼‰:")
        logger.info(f"     instruction: {sample_file['instruction']}")
        logger.info(f"     keywords: {sample_file['keywords'][:3]}... (å…±{len(sample_file['keywords'])}ä¸ª)")
        logger.info(f"     actions: {sample_file['actions']}")
        logger.info(f"     objects: {sample_file['objects'][:3]}")
        
        if file_data:
            sample_data = file_data[0]
            logger.info(f"\n  ðŸ“Š æ–‡ä»¶çº§æ•°æ®:")
            logger.info(f"     test_app: {sample_data.get('test_app', 'N/A')}")
            logger.info(f"     total_steps: {len(sample_data.get('steps', []))}")
            logger.info(f"     file_id: {sample_data.get('file_id', 'N/A')}")
    
    if step_instructions and step_data:
        logger.info(f"\n[Steps] æ­¥éª¤çº§æŒ‡ä»¤ä¸Žæ•°æ®ï¼ˆå‰2æ¡ï¼‰ï¼š\n")
        for i in range(min(2, len(step_instructions))):
            instr = step_instructions[i]
            data = step_data[i]
            logger.info(f"  Step #{i}:")
            logger.info(f"    ðŸ“ æŒ‡ä»¤: {instr['instruction']}")

            # æ˜¾ç¤ºä¸Šä¸‹æ–‡å­—æ®µ
            context = instr.get('context', {})
            if context and any(context.values()):
                logger.info(f"    ðŸ“ ä¸Šä¸‹æ–‡å­—æ®µ:")
                if context.get('database'):
                    logger.info(f"      - æ•°æ®åº“: {context['database']}")
                if context.get('method_variant'):
                    logger.info(f"      - æ–¹æ³•å˜ä½“: {context['method_variant']}")
                if context.get('object_id'):
                    logger.info(f"      - å¯¹è±¡ID: {context['object_id']}")
                if context.get('context_score'):
                    logger.info(f"      - ä¸Šä¸‹æ–‡æƒé‡: {context['context_score']}")
            
            # æ˜¾ç¤ºå…³é”®è¯æƒé‡
            weights = instr.get('keyword_weights', {})
            if weights.get('keywords'):
                logger.info(f"    ðŸ·ï¸  å…³é”®è¯æƒé‡:")
                for keyword, weight in weights['keywords'][:4]:  # æ˜¾ç¤ºå‰4ä¸ªå…³é”®è¯
                    logger.info(f"      - {keyword}: {weight}")
                if len(weights['keywords']) > 4:
                    logger.info(f"      ... åŠ{len(weights['keywords']) - 4}ä¸ªå…¶ä»–å…³é”®è¯")
                logger.info(f"      å¹³å‡æƒé‡: {weights.get('avg_weight', 0):.2f}, æœ€é«˜æƒé‡: {weights.get('max_weight', 0):.1f}")
            
            logger.info(f"    ðŸ“Š æ­¥éª¤æ•°æ®: file_id={data.get('file_id', 'N/A')}, method={data.get('method', 'N/A')}, object={data.get('object', 'N/A')}")



def main():
    logger.info("=" * 80)
    logger.info("ðŸ“‹ ç»¼åˆæŒ‡ä»¤ä¸Žæ•°æ®ç”Ÿæˆ - è¾“å‡º4ä¸ªåˆ†ç¦»çš„JSONLæ–‡ä»¶ï¼ˆåŒ…å«å…³é”®è¯æƒé‡+ä¸Šä¸‹æ–‡å­—æ®µï¼‰")
    logger.info("=" * 80)
    logger.info("\nðŸŽ¯ åŠŸèƒ½è¯´æ˜Ž:")
    logger.info("  æ–‡ä»¶çº§æŒ‡ä»¤: ç»“æž„åŒ–è¡¨è¾¾ + æƒé‡æ ‡æ³¨")
    logger.info("  æ–‡ä»¶çº§æ•°æ®: åŽŸå§‹workflowæ•°æ®")
    logger.info("  æ­¥éª¤çº§æŒ‡ä»¤: åŸºäºŽ(module,method)æ¨¡æ¿æ¸²æŸ“ + å…³é”®è¯æƒé‡ + ä¸Šä¸‹æ–‡å­—æ®µ")
    logger.info("    â”œâ”€ åŠ¨ä½œè¯æƒé‡: 3.0ï¼ˆCreate/Updateç­‰ï¼‰")
    logger.info("    â”œâ”€ å¯¹è±¡åæƒé‡: 2.0ï¼ˆMS Kabelç­‰ï¼‰")
    logger.info("    â”œâ”€ æ•°æ®åº“æƒé‡: 1.8ï¼ˆElektraç­‰ï¼‰")
    logger.info("    â”œâ”€ æ–¹æ³•å˜ä½“æƒé‡: 1.6ï¼ˆWith IDç­‰ï¼‰")
    logger.info("    â””â”€ å¯¹è±¡IDæƒé‡: 1.4")
    logger.info("  æ­¥éª¤çº§æ•°æ®: åŽŸå§‹stepæ•°æ®")
    logger.info("=" * 80)
    
    # å‚æ•°
    input_file = "data/processed/parsed_workflows.jsonl"
    output_dir = "data/processed"
    
    # æ£€æŸ¥è¾“å…¥æ–‡ä»¶
    if not Path(input_file).exists():
        logger.error(f"âŒ è¾“å…¥æ–‡ä»¶ä¸å­˜åœ¨: {input_file}")
        return
    
    # åŠ è½½å·¥ä½œæµ
    workflows = load_parsed_workflows(input_file)
    
    # ç”ŸæˆæŒ‡ä»¤å’Œæ•°æ®
    file_instructions, file_data, step_instructions, step_data = generate_all_instructions(workflows)
    
    # ä¿å­˜ä¸ºJSONLæ–‡ä»¶
    output_files = save_instructions(file_instructions, file_data, step_instructions, step_data, output_dir)
    
    # æ˜¾ç¤ºæ ·æœ¬
    show_samples(file_instructions, file_data, step_instructions, step_data)
    
    logger.info("\n" + "=" * 80)
    logger.info("âœ… æŒ‡ä»¤ä¸Žæ•°æ®ç”Ÿæˆå®Œæˆï¼")
    logger.info("âœ… ä½¿ç”¨ (module, method) æ¨¡æ¿ç”Ÿæˆæ­¥éª¤çº§æŒ‡ä»¤ï¼")
    logger.info("âœ… å…³é”®è¯æƒé‡å·²æ·»åŠ åˆ° step_level_instructions.jsonlï¼")
    logger.info("=" * 80)
    logger.info(f"ðŸ“ è¾“å‡ºç›®å½•: {output_dir}")
    logger.info(f"ðŸ“Š ç»Ÿè®¡:")
    logger.info(f"   - æ–‡ä»¶æ•°: {len(file_instructions)}")
    logger.info(f"   - æ­¥éª¤æ•°: {len(step_instructions)}")
    logger.info(f"ðŸ“‹ è¾“å‡ºæ–‡ä»¶:")
    for name, path in output_files.items():
        logger.info(f"   âœ“ {path.name}")
    logger.info("\nðŸ’¡ æƒé‡ä½“ç³»:")
    logger.info(f"   - åŠ¨ä½œè¯ï¼ˆCreate/Updateç­‰ï¼‰: {KeywordWeights.CRITICAL}")
    logger.info(f"   - å¯¹è±¡åï¼ˆMS Kabelç­‰ï¼‰: {KeywordWeights.HIGH}")
    logger.info(f"   - æ•°æ®åº“ä¸Šä¸‹æ–‡: {KeywordWeights.CONTEXT_DB}")
    logger.info(f"   - æ–¹æ³•å˜ä½“: {KeywordWeights.CONTEXT_VARIANT}")
    logger.info(f"   - å¯¹è±¡ID: {KeywordWeights.CONTEXT_ID}")
    logger.info(f"   - æµ‹è¯•æ•°æ®: {KeywordWeights.CONTEXT_DATA}")
    logger.info("\nâœ¨ æ–°å¢žåŠŸèƒ½:")
    logger.info("   - è‡ªåŠ¨æå–æ•°æ®åº“ã€æ–¹æ³•å˜ä½“ã€å¯¹è±¡IDç­‰ä¸Šä¸‹æ–‡å­—æ®µ")
    logger.info("   - ç”Ÿæˆå¤šå±‚æ¬¡æŒ‡ä»¤ï¼ˆåŸºç¡€ + ä¸Šä¸‹æ–‡åŒ–ï¼‰")
    logger.info("   - ç»“æž„åŒ–ä¸Šä¸‹æ–‡ä¿¡æ¯ç”¨äºŽRAGç³»ç»Ÿ")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

