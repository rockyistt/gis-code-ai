#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的步骤级指令生成器 - 支持基于上下文的指令差异化
核心改进: 利用步骤数据中的差异信息生成更具体的指令，减少不必要的重复同时保留必要的多样性
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class ContextualInstructionBuilder:
    """
    上下文感知的指令构建器
    
    原理:
    1. 基础指令: "Create MS Kabel"
    2. 上下文修饰符: "in Elektra", "with ID", "from Template"
    3. 最终指令: "Create MS Kabel in Elektra" ✨
    """
    
    # 可以影响指令的关键字段（优先级顺序）
    CONTEXT_FIELDS = [
        'database',           # :elektra, :catalogus, :gas 等
        'method',            # "Open Object" vs "Open Object with ID"
        'object_id',         # 不同的ID可能代表不同的实例
        'template',          # 是否使用模板
        'parent_object',     # 是否在特定的父对象下
    ]
    
    # 字段到修饰符的映射
    MODIFIER_TEMPLATES = {
        'database': 'in {value}',           # "Create MS Kabel in Elektra"
        'method': '{value}',                # "Open E MS Kabel with ID"  
        'template': 'from {value}',         # "Create MS Kabel from Template"
        'parent_object': 'under {value}',   # "Create MS Kabel under Parent"
    }
    
    def __init__(self):
        self.method_variations = {}  # 用于追踪method的变体
        
    def extract_context(self, step: Dict) -> Dict[str, Any]:
        """
        从步骤数据提取上下文信息
        
        Returns:
            {
                'database': ':elektra',
                'method_variant': 'with ID',
                'has_id': True,
                ...
            }
        """
        context = {}
        
        # 1. 提取database信息
        database = step.get('database', '').strip()
        if database and database != ':':
            # 规范化: :elektra → elektra
            context['database'] = database.lstrip(':').capitalize()
        
        # 2. 提取method的变体信息
        method = step.get('method', '').strip()
        method_variant = self._extract_method_variant(method)
        if method_variant and method_variant != 'standard':
            context['method_variant'] = method_variant
        
        # 3. 检查是否有对象ID
        object_id = step.get('object_id', '')
        if object_id and object_id not in ['Passed', '', 'N/A']:
            context['has_object_id'] = True
        
        # 4. 检查test_data中的创建/更新操作类型
        test_data = step.get('test_data', {})
        if isinstance(test_data, dict):
            if test_data.get('create'):
                context['operation_type'] = 'Create'
            elif test_data.get('update'):
                context['operation_type'] = 'Update'
        
        # 5. 检查是否涉及模板
        if 'template' in method.lower() or 'template' in str(test_data).lower():
            context['uses_template'] = True
        
        return context
    
    def _extract_method_variant(self, method: str) -> Optional[str]:
        """提取方法的变体（如"with ID"、"from Template"等）"""
        method_lower = method.lower()
        
        if 'with id' in method_lower:
            return 'with ID'
        elif 'from template' in method_lower or 'template' in method_lower:
            return 'from template'
        elif 'with parameter' in method_lower:
            return 'with parameter'
        elif 'and' in method_lower:
            return 'with transaction'
        
        return 'standard'
    
    def build_contextualized_instruction(self, base_instruction: str, context: Dict[str, Any]) -> str:
        """
        构建包含上下文的指令
        
        Examples:
            "Create MS Kabel" + {database: 'Elektra'} → "Create MS Kabel in Elektra"
            "Open E MS Kabel" + {method_variant: 'with ID'} → "Open E MS Kabel with ID"
        """
        parts = [base_instruction]
        
        # 按优先级添加修饰符
        if 'database' in context:
            parts.append(f"in {context['database']}")
        
        if 'method_variant' in context and context['method_variant'] != 'standard':
            # 某些method变体应该写在对象前面
            if 'with' in context['method_variant']:
                parts.insert(1, context['method_variant'])
            else:
                parts.append(f"({context['method_variant']})")
        
        if context.get('uses_template'):
            parts.append("from template")
        
        # 合并成最终指令
        return " ".join(parts)
    
    def get_instruction_variants(self, base_instruction: str, context: Dict[str, Any]) -> List[str]:
        """
        生成指令的多个变体（从最简到最详细）
        
        Examples:
            "Create MS Kabel"
            "Create MS Kabel in Elektra"
            "Create MS Kabel in Elektra with ID"
        """
        variants = [base_instruction]
        
        # 添加带database的变体
        if 'database' in context:
            variants.append(f"{base_instruction} in {context['database']}")
        
        # 添加带method变体的表达
        if 'method_variant' in context and context['method_variant'] != 'standard':
            if 'with' in context['method_variant'].lower():
                variants.append(f"{base_instruction} {context['method_variant']}")
            else:
                variants.append(f"{base_instruction} ({context['method_variant']})")
        
        return variants


class EnhancedStepInstructionGenerator:
    """
    增强的步骤级指令生成器
    支持基于上下文生成更具区分度的指令
    """
    
    def __init__(self):
        self.context_builder = ContextualInstructionBuilder()
        self.instruction_contexts = defaultdict(list)  # 追踪每个基础指令的所有上下文
    
    def _categorize_operation(self, method: str) -> str:
        """分类操作动词"""
        method_lower = method.lower()
        
        if "create" in method_lower:
            return "Create"
        elif "update" in method_lower or "edit" in method_lower:
            return "Update"
        elif "delete" in method_lower:
            return "Delete"
        elif "verify" in method_lower or "check" in method_lower:
            return "Verify"
        elif "open" in method_lower or "access" in method_lower:
            return "Open"
        elif "select" in method_lower or "choose" in method_lower:
            return "Select"
        elif "click" in method_lower or "press" in method_lower:
            return "Click"
        else:
            return method.capitalize()
    
    def _clean_object_name(self, obj: str) -> str:
        """清理对象名"""
        obj = obj.replace(':', '').strip()
        for prefix in ['E ', 'L ', 'HV ']:
            if obj.startswith(prefix):
                obj = obj[len(prefix):].strip()
                break
        return obj
    
    def _is_valid_object(self, obj: str) -> bool:
        """判断是否为有效对象"""
        if not obj:
            return False
        
        obj_lower = obj.lower()
        invalid = {
            'object', 'object editor', 'object control', 'default',
            'select', 'button', 'tab', 'field', 'none', 'n/a', 'na',
        }
        
        if obj_lower in invalid:
            return False
        return len(obj) > 1
    
    def generate_base_instruction(self, step: Dict) -> Tuple[str, bool]:
        """
        生成基础指令（不带上下文修饰）
        
        Returns:
            (instruction, has_object)
        """
        method = step.get('method', '').strip()
        obj = step.get('object', '').strip()
        
        verb = self._categorize_operation(method)
        
        if obj and self._is_valid_object(obj):
            obj_clean = self._clean_object_name(obj)
            return f"{verb} {obj_clean}", True
        else:
            return verb, False
    
    def generate_contextualized_instructions(self, step: Dict) -> Dict[str, Any]:
        """
        生成带上下文的指令集合
        
        Returns:
            {
                'base_instruction': 'Create MS Kabel',
                'contextualized_instruction': 'Create MS Kabel in Elektra',
                'variants': ['Create MS Kabel', 'Create MS Kabel in Elektra'],
                'context': {database: 'Elektra', ...},
                'canonical_form': 'create ms kabel in elektra'
            }
        """
        # 1. 生成基础指令
        base_instr, has_object = self.generate_base_instruction(step)
        
        # 2. 提取上下文信息
        context = self.context_builder.extract_context(step)
        
        # 3. 生成上下文化指令（带修饰符）
        contextualized = self.context_builder.build_contextualized_instruction(base_instr, context)
        
        # 4. 生成多个变体（用于RAG多层检索）
        variants = self.context_builder.get_instruction_variants(base_instr, context)
        
        # 5. 规范形式（用于去重和匹配）
        canonical = contextualized.lower().replace("  ", " ")
        
        return {
            'base_instruction': base_instr,
            'contextualized_instruction': contextualized,
            'variants': variants,
            'context': context,
            'canonical_form': canonical,
            'richness_score': self._calculate_richness(context)
        }
    
    def _calculate_richness(self, context: Dict[str, Any]) -> float:
        """
        计算指令的丰富度评分（上下文信息越多越高）
        用于后续的RAG中判断使用哪个变体
        """
        richness = 1.0  # 基础分
        richness += len([v for v in context.values() if v]) * 0.3
        return min(richness, 3.0)  # 上限3.0


# ============================================================
# 对比展示：原始vs改进
# ============================================================

def compare_instructions():
    """对比展示改进前后的效果"""
    
    logger.info("="*100)
    logger.info("💡 改进前后对比：相同的基础操作，通过上下文区分")
    logger.info("="*100 + "\n")
    
    # 模拟的步骤数据：相同操作但不同上下文
    steps_same_operation = [
        {
            'method': 'Create',
            'object': 'E MS Kabel',
            'database': ':elektra',
            'object_id': '121319941725882',
            'test_data': {'create': {'Object': 'E MS Kabel'}}
        },
        {
            'method': 'Create',
            'object': 'E MS Kabel',
            'database': ':topografie',
            'object_id': '1231231',
            'test_data': {'create': {'Object': 'E MS Kabel'}}
        },
        {
            'method': 'Create Object with ID',
            'object': 'E MS Kabel',
            'database': ':catalogus',
            'object_id': '86393281400162',
            'test_data': {'create': {'Object': 'E MS Kabel'}}
        },
    ]
    
    # 原始做法（简单）
    logger.info("原始做法（当前01脚本）:")
    logger.info("  所有步骤 → 相同指令: 「Create E MS Kabel」")
    logger.info("  结果: ❌ 3条重复指令\n")
    
    # 改进做法（上下文感知）
    logger.info("改进做法（新的指令生成器）:")
    logger.info("  基于步骤数据的不同上下文生成不同指令:\n")
    
    generator = EnhancedStepInstructionGenerator()
    
    for i, step in enumerate(steps_same_operation, 1):
        result = generator.generate_contextualized_instructions(step)
        
        logger.info(f"  步骤{i}:")
        logger.info(f"    • 基础: 「{result['base_instruction']}」")
        logger.info(f"    • 上下文: {result['context']}")
        logger.info(f"    • 最终指令: 「{result['contextualized_instruction']}」")
        logger.info(f"    • 丰富度: {result['richness_score']:.1f}/3.0")
        if result['variants']:
            logger.info(f"    • 变体: {result['variants']}")
        logger.info()
    
    logger.info("  结果: ✅ 3条不同的指令")
    logger.info("    - 「Create E MS Kabel in Elektra」")
    logger.info("    - 「Create E MS Kabel in Topografie」")
    logger.info("    - 「Create E MS Kabel with ID in Catalogus」\n")
    
    # 优势
    logger.info("=" * 100)
    logger.info("✨ 改进的优势")
    logger.info("=" * 100)
    logger.info("""
    1. 消除虚假的重复
       • 相同的操作在不同的数据库中 → 不同的指令
       • 相同的操作用不同的方式调用 → 不同的指令
       • 不是所有"Create E MS Kabel"都是相同的！

    2. 保留必要的多样性
       • 不同的database/method/参数 → 保留为不同的指令表达
       • 有利于RAG学习该操作的多种场景
       • 有利于后续的细粒度检索

    3. 提升指令的说明力和指导力
       • 「Create E MS Kabel in Elektra」 比 「Create E MS Kabel」更清楚
       • 包含了执行的前置条件（在哪个数据库）
       • RAG可以更准确地理解和生成代码

    4. 支持多层检索
       • 简单检索: 「Create」
       • 精确检索: 「Create E MS Kabel」
       • 特定场景检索: 「Create E MS Kabel in Elektra」

    5. 减少歧义和错误
       • 避免返回错误的"Create E MS Kabel in 错误的数据库"
       • 确保RAG返回的是正确上下文的指令
    """)


def main():
    """主函数"""
    
    logger.info("\n" + "="*100)
    logger.info("🔧 改进的指令生成器 - 上下文感知设计")
    logger.info("="*100 + "\n")
    
    compare_instructions()
    
    logger.info("\n" + "="*100)
    logger.info("📝 如何集成到01脚本")
    logger.info("="*100 + """
    
    在 generate_step_instruction 方法中替换为：
    
    ```python
    def generate_step_instruction(self, step: Dict) -> Dict[str, Any]:
        generator = EnhancedStepInstructionGenerator()
        result = generator.generate_contextualized_instructions(step)
        
        return {
            'instruction': result['contextualized_instruction'],
            'base_instruction': result['base_instruction'],
            'context': result['context'],
            'variants': result['variants'],
            'richness_score': result['richness_score']
        }
    ```
    
    这样每个步骤会生成：
    1. 基础指令（用于简单匹配）
    2. 上下文化指令（用于精确匹配）
    3. 变体列表（用于多层RAG检索）
    4. 上下文信息（用于调试和分析）
    5. 丰富度评分（用于质量评估）
    """)


if __name__ == "__main__":
    main()
