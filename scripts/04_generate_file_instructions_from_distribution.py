#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从步骤级指令分布生成file级指令模板
核心思路：分析4012个file中每一步的指令分布，自动推导file级指令模板
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import Counter, defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class FileInstructionTemplateGenerator:
    """从步骤级指令分布生成file级指令模板"""

    def __init__(self, step_level_instructions_path: str, file_level_data_path: str):
        """
        初始化生成器

        Args:
            step_level_instructions_path: step_level_instructions.jsonl文件路径
            file_level_data_path: file_level_data.jsonl文件路径（用于获取总步数）
        """
        self.step_level_instructions = self._load_step_instructions(step_level_instructions_path)
        self.file_level_data = self._load_file_level_data(file_level_data_path)
        self.step_distributions = defaultdict(Counter)  # {step_position: Counter({instruction: count})}
        self.file_lengths = Counter()  # {num_steps: count}

    def _load_step_instructions(self, path: str) -> List[Dict]:
        """加载step_level_instructions.jsonl"""
        instructions = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        item = json.loads(line)
                        instructions.append(item)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
            return []

        logger.info(f"Loaded {len(instructions)} step-level instructions")
        return instructions

    def _load_file_level_data(self, path: str) -> Dict[str, Dict]:
        """加载file_level_data.jsonl，建立file_id → total_steps的映射"""
        file_data = {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        item = json.loads(line)
                        file_id = item.get('file_id', '')
                        total_steps = item.get('total_steps', 0)
                        file_data[file_id] = total_steps
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
            return {}

        logger.info(f"Loaded {len(file_data)} file-level data records")
        return file_data

    def analyze_step_distributions(self):
        """分析每个步骤位置的指令分布"""
        logger.info("\n" + "="*80)
        logger.info("ANALYZING STEP DISTRIBUTIONS")
        logger.info("="*80)

        for item in self.step_level_instructions:
            file_id = item.get('file_id', '')
            step_index = item.get('step_index', 0)
            instruction = item.get('instruction', '')

            # 从file_level_data获取总步数
            if file_id not in self.file_level_data:
                continue

            total_steps = self.file_level_data[file_id]

            # 记录分布
            self.step_distributions[step_index][instruction] += 1
            self.file_lengths[total_steps] += 1

        # 打印统计信息
        logger.info(f"\nFile length distribution:")
        for length in sorted(self.file_lengths.keys()):
            count = self.file_lengths[length]
            percentage = count / sum(self.file_lengths.values()) * 100
            logger.info(f"  {length:2d} steps: {count:4d} files ({percentage:5.1f}%)")

        logger.info(f"\nStep distributions (top 3 at each position):")
        for step_pos in sorted(self.step_distributions.keys()):
            logger.info(f"\n  Position {step_pos + 1}:")
            top_instructions = self.step_distributions[step_pos].most_common(3)
            total = sum(self.step_distributions[step_pos].values())

            for instruction, count in top_instructions:
                percentage = count / total * 100
                logger.info(f"    [{percentage:5.1f}%] {instruction[:80]}")

    def extract_instruction_action(self, instruction: str) -> Tuple[str, str]:
        """
        从指令中提取action和object

        例如：
        "Step 1/7: Open E MS Installatie" → ("Open", "E MS Installatie")
        "Step 2/7: Select Tab in Elektra" → ("Select", "Tab")
        "Step 3/7: Create MS Kabel where fields have values in Elektra" → ("Create", "MS Kabel")
        """
        # 移除 "Step X/Y: " 前缀
        if "Step " in instruction and ": " in instruction:
            instruction = instruction.split(": ", 1)[1]

        # 分离action和对象
        tokens = instruction.split()
        if len(tokens) > 0:
            action = tokens[0]  # "Open", "Select", "Create", etc.
            # 对象是action之后、前置介词前的部分
            if len(tokens) > 1:
                # 找到第一个介词（in, of, where等）
                prepositions = {"in", "of", "where", "with", "from", "to"}
                object_tokens = []
                for token in tokens[1:]:
                    if token.lower() in prepositions:
                        break
                    object_tokens.append(token)

                obj = " ".join(object_tokens) if object_tokens else "object"
            else:
                obj = "object"

            return action, obj
        return "unknown", "unknown"

    def generate_templates(self) -> List[Dict[str, Any]]:
        """生成file级指令模板"""
        logger.info("\n" + "="*80)
        logger.info("GENERATING FILE-LEVEL INSTRUCTION TEMPLATES")
        logger.info("="*80)

        templates = []

        # 对每个常见的file长度生成模板
        for total_steps in sorted(self.file_lengths.keys()):
            if self.file_lengths[total_steps] < 10:  # 至少10个样本
                continue

            logger.info(f"\n[Template for {total_steps}-step workflows ({self.file_lengths[total_steps]} samples)]")

            # 构建模板
            step_actions = []
            step_objects = []
            template_parts = []

            for step_pos in range(total_steps):
                if step_pos not in self.step_distributions:
                    continue

                # 获取这个位置最常见的指令
                top_instruction, count = self.step_distributions[step_pos].most_common(1)[0]
                action, obj = self.extract_instruction_action(top_instruction)

                step_actions.append(action)
                step_objects.append(obj)

                # 简化对象表示
                if obj.lower() in {'tab', 'button', 'field', 'object'}:
                    template_parts.append(action)
                else:
                    template_parts.append(f"{action} {obj}")

                logger.info(f"  Step {step_pos + 1}: {action:15s} {obj:30s} ({count:3d} samples)")

            # 构建最终的file指令模板
            file_instruction_template = " → ".join(template_parts)

            templates.append({
                "workflow_length": total_steps,
                "num_samples": self.file_lengths[total_steps],
                "template": file_instruction_template,
                "step_actions": step_actions,
                "step_objects": step_objects,
                "detailed_template": [
                    {
                        "position": i,
                        "action": step_actions[i],
                        "object": step_objects[i],
                        "instruction_pattern": f"{step_actions[i]} {step_objects[i]}"
                    }
                    for i in range(len(step_actions))
                ]
            })

            logger.info(f"  Template: {file_instruction_template}")

        return templates

    def apply_templates_to_files(
        self, file_level_data_path: str, output_path: str, templates: List[Dict]
    ):
        """
        应用模板为每个file生成file_instruction

        将原始file_level_data中加入根据模板生成的file_instruction
        """
        logger.info("\n" + "="*80)
        logger.info("APPLYING TEMPLATES TO GENERATE FILE-LEVEL INSTRUCTIONS")
        logger.info("="*80)

        template_map = {t["workflow_length"]: t for t in templates}

        count_total = 0
        count_templated = 0
        count_fallback = 0

        try:
            with open(file_level_data_path, 'r', encoding='utf-8') as f_in:
                with open(output_path, 'w', encoding='utf-8') as f_out:
                    for line in f_in:
                        try:
                            file_data = json.loads(line)
                            count_total += 1

                            total_steps = file_data.get('total_steps', 0)

                            # 查找对应的模板
                            if total_steps in template_map:
                                template = template_map[total_steps]
                                file_instruction = template['template']
                                count_templated += 1
                            else:
                                # fallback：简单聚合
                                steps = file_data.get('steps', [])
                                methods = [s.get('method', 'Unknown') for s in steps]
                                file_instruction = " → ".join(methods[:3])
                                if len(methods) > 3:
                                    file_instruction += f" → ... ({len(methods)} steps)"
                                count_fallback += 1

                            # 添加file_instruction
                            file_data['file_instruction'] = file_instruction

                            # 写出
                            f_out.write(json.dumps(file_data, ensure_ascii=False) + '\n')

                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON error: {e}")
                            continue

        except Exception as e:
            logger.error(f"Error: {e}")
            return

        logger.info(f"\nResults:")
        logger.info(f"  Total files: {count_total}")
        logger.info(f"  Applied template: {count_templated} ({count_templated/count_total*100:.1f}%)")
        logger.info(f"  Used fallback: {count_fallback} ({count_fallback/count_total*100:.1f}%)")
        logger.info(f"  Output: {output_path}")


def main():
    """主入口"""
    # 定义路径
    step_level_path = "data/processed/step_level_instructions.jsonl"
    file_level_path = "data/processed/file_level_data.jsonl"
    output_path = "data/processed/file_level_data_with_instructions.jsonl"
    template_output = "data/processed/file_instruction_templates.json"

    # 初始化生成器
    generator = FileInstructionTemplateGenerator(step_level_path, file_level_path)

    # 第1步：分析分布
    generator.analyze_step_distributions()

    # 第2步：生成模板
    templates = generator.generate_templates()

    # 保存模板为参考
    with open(template_output, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)
    logger.info(f"\nTemplates saved to {template_output}")

    # 第3步：应用模板为所有file生成instruction
    generator.apply_templates_to_files(file_level_path, output_path, templates)

    logger.info("\n✅ Done!")


if __name__ == '__main__':
    main()
