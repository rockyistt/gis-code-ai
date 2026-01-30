#!/usr/bin/env python3
"""
构建层次化训练数据（Context Window策略）

为每个step添加上下文：
1. file_task: 整个文件的任务描述
2. previous_steps: 之前已完成的步骤
3. remaining_objects: 剩余待处理的对象

这样模型在生成每个step时能够：
- 知道整体目标（file_task）
- 了解进度（previous_steps）
- 知道还需处理什么（remaining_objects）
"""
import json
from pathlib import Path
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def extract_objects_from_step(step: Dict) -> List[str]:
    """从step中提取操作的对象"""
    objects = []
    
    # 从structure.object提取
    if 'structure' in step and 'object' in step['structure']:
        obj = step['structure']['object']
        if obj and obj not in ['object', 'objects']:
            # 清理对象名
            import re
            obj_clean = re.sub(r'\s+object$', '', obj, flags=re.IGNORECASE)
            objects.append(obj_clean)
    
    return objects


def build_context_for_step(
    step: Dict,
    file_instruction: str,
    all_steps: List[Dict],
    current_index: int
) -> Dict[str, Any]:
    """为单个step构建上下文信息"""
    
    # 1. File task（整体任务）
    file_task = file_instruction
    
    # 2. Previous steps（之前的步骤，保留最近3个）
    previous_steps = []
    start_idx = max(0, current_index - 3)
    for i in range(start_idx, current_index):
        prev_step = all_steps[i]
        previous_steps.append({
            'step_index': prev_step['step_index'],
            'instruction': prev_step['instruction'],
            'action': prev_step['structure'].get('action', '') if 'structure' in prev_step else ''
        })
    
    # 3. Remaining objects（剩余对象）
    # 收集所有对象
    all_objects = []
    for s in all_steps:
        objs = extract_objects_from_step(s)
        all_objects.extend(objs)
    
    # 去重并保序
    unique_objects = []
    seen = set()
    for obj in all_objects:
        if obj not in seen:
            unique_objects.append(obj)
            seen.add(obj)
    
    # 已处理的对象（当前步骤之前）
    processed_objects = set()
    for i in range(current_index):
        objs = extract_objects_from_step(all_steps[i])
        processed_objects.update(objs)
    
    # 剩余对象
    remaining_objects = [obj for obj in unique_objects if obj not in processed_objects]
    
    # 4. 当前步骤的对象
    current_objects = extract_objects_from_step(step)
    
    return {
        'file_task': file_task,
        'previous_steps': previous_steps,
        'remaining_objects': remaining_objects[:5],  # 最多显示5个
        'current_objects': current_objects,
        'progress': {
            'current_step': current_index + 1,
            'total_steps': len(all_steps),
            'processed_objects': len(processed_objects),
            'remaining_objects': len(remaining_objects)
        }
    }


def build_hierarchical_training_sample(
    step: Dict,
    context: Dict,
    output_json: Dict
) -> Dict[str, Any]:
    """构建单个训练样本（带层次化上下文）"""
    
    # 构建增强的instruction（包含上下文提示）
    instruction_parts = []
    
    # 添加文件任务上下文
    if context['file_task']:
        instruction_parts.append(f"File Task: {context['file_task']}")
    
    # 添加进度信息
    progress = context['progress']
    instruction_parts.append(
        f"Progress: Step {progress['current_step']}/{progress['total_steps']}"
    )
    
    # 添加之前的步骤（如果有）
    if context['previous_steps']:
        prev_str = "; ".join([
            f"{ps['action']} {ps['instruction'].split()[1] if len(ps['instruction'].split()) > 1 else ''}"
            for ps in context['previous_steps']
        ])
        instruction_parts.append(f"Previous: {prev_str}")
    
    # 添加剩余对象（如果有）
    if context['remaining_objects']:
        remaining_str = ", ".join(context['remaining_objects'][:3])
        instruction_parts.append(f"Remaining: {remaining_str}")
    
    # 当前步骤的指令
    instruction_parts.append(f"\nCurrent Step: {step['instruction']}")
    
    full_instruction = "\n".join(instruction_parts)
    
    # 构建训练样本
    return {
        'instruction': full_instruction,
        'input': '',  # 对于instruction-tuning，input通常为空
        'output': json.dumps(output_json, ensure_ascii=False),
        
        # 元数据（用于分析，不用于训练）
        'metadata': {
            'file_id': step['file_id'],
            'step_index': step['step_index'],
            'step_type': step['step_type'],
            'is_high_quality': step.get('is_high_quality', False),
            'provider': 'hierarchical_context_window',
            'keywords': step.get('keywords', []),
            'context': context
        }
    }


def main():
    """主函数"""
    logging.info("="*70)
    logging.info("🏗️  构建层次化训练数据（Context Window策略）")
    logging.info("="*70)
    
    # 1. 加载数据
    logging.info("\n📖 加载数据...")
    
    # 加载step级指令
    step_insts = []
    with open('data/processed/step_level_instructions_weighted.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            step_insts.append(json.loads(line))
    logging.info(f"   ✓ Step指令: {len(step_insts)}")
    
    # 加载file级指令
    file_insts = {}
    with open('data/processed/file_level_instructions_aggregated.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            file_insts[data['file_id']] = data
    logging.info(f"   ✓ File指令: {len(file_insts)}")
    
    # 加载原始工作流（获取完整的step输出JSON）
    workflows = {}
    with open('data/processed/parsed_workflows.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            workflows[data['file_id']] = data
    logging.info(f"   ✓ 工作流: {len(workflows)}")
    
    # 2. 按file_id分组step
    logging.info("\n📊 按文件分组步骤...")
    steps_by_file = {}
    for step in step_insts:
        file_id = step['file_id']
        if file_id not in steps_by_file:
            steps_by_file[file_id] = []
        steps_by_file[file_id].append(step)
    
    # 确保每个文件的步骤按step_index排序
    for file_id in steps_by_file:
        steps_by_file[file_id].sort(key=lambda s: s['step_index'])
    
    logging.info(f"   ✓ 文件数: {len(steps_by_file)}")
    
    # 3. 构建层次化训练样本
    logging.info("\n🏗️  构建训练样本...")
    training_samples = []
    
    for file_id, steps in steps_by_file.items():
        file_inst = file_insts.get(file_id)
        workflow = workflows.get(file_id)
        
        if not file_inst or not workflow:
            logging.warning(f"   ⚠️  跳过 {file_id}: 缺少file指令或工作流")
            continue
        
        file_instruction = file_inst['instruction']
        
        # 为每个step构建上下文和训练样本
        for i, step in enumerate(steps):
            # 获取step的输出JSON（从原始工作流）
            if i < len(workflow['steps']):
                output_json = workflow['steps'][i]
            else:
                logging.warning(f"   ⚠️  {file_id} step {i}: 无法找到对应的原始step")
                continue
            
            # 构建上下文
            context = build_context_for_step(step, file_instruction, steps, i)
            
            # 构建训练样本
            sample = build_hierarchical_training_sample(step, context, output_json)
            training_samples.append(sample)
    
    logging.info(f"   ✓ 生成样本数: {len(training_samples)}")
    
    # 4. 保存结果
    output_path = Path('data/processed/hierarchical_training_data.json')
    logging.info(f"\n💾 保存到: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(training_samples, f, ensure_ascii=False, indent=2)
    
    # 5. 统计信息
    logging.info("\n" + "="*70)
    logging.info("📊 统计信息")
    logging.info("="*70)
    logging.info(f"总样本数: {len(training_samples)}")
    logging.info(f"总文件数: {len(steps_by_file)}")
    logging.info(f"平均每文件步骤数: {len(training_samples) / len(steps_by_file):.1f}")
    
    # 高质量样本统计
    high_quality = sum(1 for s in training_samples if s['metadata'].get('is_high_quality', False))
    logging.info(f"高质量样本: {high_quality} ({high_quality/len(training_samples)*100:.1f}%)")
    
    # 6. 显示样本
    logging.info("\n" + "="*70)
    logging.info("📝 样本示例")
    logging.info("="*70)
    
    sample = training_samples[0]
    logging.info(f"\n文件: {sample['metadata']['file_id']}")
    logging.info(f"步骤: {sample['metadata']['step_index'] + 1}")
    logging.info(f"\n【Instruction】:")
    logging.info(sample['instruction'][:500] + "...")
    logging.info(f"\n【Output】:")
    logging.info(sample['output'][:300] + "...")
    
    # 显示上下文信息
    context = sample['metadata']['context']
    logging.info(f"\n【Context Info】:")
    logging.info(f"  File Task: {context['file_task']}")
    logging.info(f"  Previous Steps: {len(context['previous_steps'])}")
    logging.info(f"  Remaining Objects: {context['remaining_objects'][:3]}")
    logging.info(f"  Progress: {context['progress']['current_step']}/{context['progress']['total_steps']}")
    
    logging.info("\n" + "="*70)
    logging.info("✅ 层次化训练数据构建完成！")
    logging.info("="*70)
    logging.info(f"输出文件: {output_path}")
    logging.info(f"文件大小: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    logging.info("="*70)


if __name__ == '__main__':
    main()
