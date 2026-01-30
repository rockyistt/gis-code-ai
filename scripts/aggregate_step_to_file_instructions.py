#!/usr/bin/env python3
"""
从Step级指令聚合生成File级指令
核心思路：
1. 从文件名推断任务类型（create, update, delete等）
2. 从steps聚合所有对象名（避免"multiple objects"）
3. 如果对象过多(>3)，列出前3个+类别
"""
import json
import re
from collections import defaultdict, Counter
from pathlib import Path
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def infer_task_from_filename(filename: str) -> str:
    """从文件名推断任务类型"""
    filename_lower = filename.lower()
    
    # 关键词映射
    task_keywords = {
        'insert': 'create',
        'opvoeren': 'create',
        'nieuw': 'create',
        'create': 'create',
        'crud': 'manage',  # CRUD表示增删改查
        'update': 'update',
        'delete': 'delete',
        'remove': 'delete',
    }
    
    for keyword, task in task_keywords.items():
        if keyword in filename_lower:
            return task
    
    return 'manage'  # 默认


def aggregate_objects(objects: List[str], max_display: int = 3) -> Dict[str, Any]:
    """
    聚合对象列表
    如果对象过多，显示前N个+类别
    """
    unique_objects = list(dict.fromkeys(objects))  # 去重保序
    
    if len(unique_objects) == 0:
        return {
            'display': 'objects',
            'count': 0,
            'list': []
        }
    elif len(unique_objects) <= max_display:
        return {
            'display': ', '.join(unique_objects),
            'count': len(unique_objects),
            'list': unique_objects
        }
    else:
        # 提取类别（通常是第一个词，如"E MS Kabel"中的"E"）
        categories = [obj.split()[0] for obj in unique_objects if ' ' in obj]
        category_counts = Counter(categories)
        most_common_category = category_counts.most_common(1)[0][0] if category_counts else None
        
        # 显示前N个 + 类别
        top_objects = unique_objects[:max_display]
        if most_common_category:
            display_str = f"{', '.join(top_objects)} and other {most_common_category} objects"
        else:
            display_str = f"{', '.join(top_objects)} and {len(unique_objects) - max_display} more objects"
        
        return {
            'display': display_str,
            'count': len(unique_objects),
            'list': unique_objects,
            'top_category': most_common_category
        }


def infer_object_category(objects: List[str]) -> str:
    """从对象列表推断对象类别（高层次概括）"""
    if not objects:
        return "objects"
    
    # 提取对象类型前缀（如 E MS, E HS, E LS）
    type_counts = Counter()
    for obj in objects:
        parts = obj.split()
        if len(parts) >= 2:
            # 提取类型前缀（如 "E MS", "E HS"）
            prefix = ' '.join(parts[:2])
            type_counts[prefix] += 1
    
    # 如果有明确的主要类型
    if type_counts:
        most_common = type_counts.most_common(2)
        if len(most_common) == 1:
            return f"{most_common[0][0]} components"
        elif len(most_common) >= 2:
            return f"{most_common[0][0]}/{most_common[1][0]} components"
    
    # 提取对象类别关键词（如 Kabel, Installatie, Aardingstrafo）
    category_keywords = []
    for obj in objects:
        # 取最后一个有意义的词作为类别
        words = [w for w in obj.split() if w not in ['FP', 'E', 'MS', 'HS', 'LS', 'Sec']]
        if words:
            category_keywords.append(words[-1])
    
    if category_keywords:
        category_counts = Counter(category_keywords)
        main_category = category_counts.most_common(1)[0][0]
        if category_counts[main_category] > 1:
            return f"{main_category} components"
        else:
            return f"electrical components"
    
    return "objects"


def aggregate_file_instruction(file_id: str, steps: List[Dict]) -> Dict[str, Any]:
    """从steps聚合生成file级指令（高层次任务描述）"""
    
    # 1. 从文件名推断主要任务
    task = infer_task_from_filename(file_id)
    
    # 2. 聚合所有步骤的信息
    all_objects = []
    all_actions = []
    all_databases = set()
    all_keywords = []
    test_app = None
    is_high_quality = any(s.get('is_high_quality', False) for s in steps)
    
    for step in steps:
        # 对象
        if 'structure' in step and 'object' in step['structure']:
            obj = step['structure']['object']
            if obj and obj not in ['object', 'objects']:  # 过滤泛化词
                # 清理对象名（去掉"object"后缀）
                obj_clean = re.sub(r'\s+object$', '', obj, flags=re.IGNORECASE)
                all_objects.append(obj_clean)
        
        # 动作
        if 'structure' in step and 'action' in step['structure']:
            action = step['structure']['action']
            if action:
                all_actions.append(action.lower())
        
        # 数据库/上下文
        if 'structure' in step:
            # 从context字段提取
            if 'context' in step['structure']:
                ctx = step['structure']['context']
                if ctx:
                    all_databases.add(ctx)
            
            # 从adverbials提取（如"in elektra dataset"）
            if 'adverbials' in step['structure']:
                adverbs = step['structure']['adverbials']
                # 查找"in XXX dataset/system"模式
                for i, adv in enumerate(adverbs):
                    if adv == 'in' and i + 1 < len(adverbs):
                        next_word = adverbs[i + 1]
                        # 过滤掉泛化词
                        if next_word not in ['object', 'objects', 'dataset', 'system', 'database']:
                            all_databases.add(next_word)
        
        # 关键词
        if 'keywords' in step:
            all_keywords.extend(step['keywords'])
        
        # 应用名
        if 'instruction' in step:
            # 尝试从instruction提取app名（通常在末尾）
            match = re.search(r'in (NRG [^\.]+)', step['instruction'])
            if match:
                test_app = match.group(1).strip()
    
    # 3. 推断主要动作（只取最主要的业务动作，忽略辅助动作）
    action_counts = Counter(all_actions)
    # 过滤掉辅助动作（open, switch, navigate等）
    auxiliary_actions = {'open', 'switch', 'navigate', 'select', 'close'}
    business_actions = {action: count for action, count in action_counts.items() 
                       if action not in auxiliary_actions}
    
    if business_actions:
        # 如果有CRUD动作（create/update/delete），优先使用
        crud_actions = ['create', 'update', 'delete']
        crud_found = [a for a in crud_actions if a in business_actions]
        
        if len(crud_found) >= 2:
            # 多个CRUD动作，使用"manage"
            primary_action = 'manage'
        elif crud_found:
            # 单个CRUD动作
            primary_action = crud_found[0]
        else:
            # 取最频繁的业务动作
            primary_action = max(business_actions, key=business_actions.get)
    else:
        # 如果没有业务动作，使用推断的任务
        primary_action = task
    
    # 4. 推断对象类别（高层次概括）
    object_category = infer_object_category(all_objects)
    
    # 5. 提取数据库和应用信息
    database_str = ', '.join(all_databases) if all_databases else None
    app_str = test_app
    
    # 6. 构建高层次的instruction文本
    # 格式："Manage E MS components in elektra system" 或 "Create cables for NRG Beheerkaart"
    instruction_parts = []
    
    # 主要动作 + 对象类别
    instruction_parts.append(f"{primary_action.capitalize()} {object_category}")
    
    # 添加上下文（优先database，其次app）
    if database_str:
        instruction_parts.append(f"in {database_str} system")
    elif app_str:
        instruction_parts.append(f"for {app_str}")
    
    instruction = ' '.join(instruction_parts)
    instruction = ' '.join(instruction_parts)
    
    # 7. 聚合关键词（去重并保留权重）
    keyword_dict = {}
    for kw, weight in all_keywords:
        if kw in keyword_dict:
            keyword_dict[kw] = max(keyword_dict[kw], weight)  # 取最高权重
        else:
            keyword_dict[kw] = weight
    
    aggregated_keywords = [[kw, weight] for kw, weight in keyword_dict.items()]
    
    # 8. 保存详细的对象列表（用于训练数据）
    unique_objects = list(dict.fromkeys(all_objects))  # 去重保序
    
    # 9. 返回结果
    return {
        'file_id': file_id,
        'is_high_quality': is_high_quality,
        'instruction': instruction,
        'provider': 'step_aggregation_v2',
        'test_app': app_str,
        'total_steps': len(steps),
        'keywords': aggregated_keywords,
        'primary_action': primary_action,
        'object_category': object_category,
        'objects': unique_objects,  # 保留详细对象列表
        'object_count': len(unique_objects),
        'databases': list(all_databases),
        'inferred_task': task
    }


def main():
    """主函数"""
    input_file = Path('data/processed/step_level_instructions_weighted.jsonl')
    output_file = Path('data/processed/file_level_instructions_aggregated.jsonl')
    
    logging.info(f"📖 Reading step-level instructions from {input_file}")
    
    # 1. 读取step级数据并按file_id分组
    steps_by_file = defaultdict(list)
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            step = json.loads(line)
            steps_by_file[step['file_id']].append(step)
    
    logging.info(f"✅ Loaded {len(steps_by_file)} files with {sum(len(steps) for steps in steps_by_file.values())} total steps")
    
    # 2. 聚合生成file级指令
    logging.info("📝 Aggregating file-level instructions from steps...")
    file_instructions = []
    for file_id, steps in steps_by_file.items():
        file_inst = aggregate_file_instruction(file_id, steps)
        file_instructions.append(file_inst)
    
    # 3. 保存结果
    logging.info(f"💾 Saving to {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        for inst in file_instructions:
            f.write(json.dumps(inst, ensure_ascii=False) + '\n')
    
    # 4. 统计"multiple objects"出现次数
    multiple_count = sum(1 for inst in file_instructions if 'multiple objects' in inst['instruction'].lower())
    
    logging.info("\n" + "="*60)
    logging.info("🎉 聚合完成！")
    logging.info(f"📄 输出文件: {output_file}")
    logging.info(f"📊 统计:")
    logging.info(f"   - 总文件数: {len(file_instructions)}")
    logging.info(f"   - 含\"multiple objects\"的文件: {multiple_count} ({multiple_count/len(file_instructions)*100:.1f}%)")
    logging.info(f"   - 平均每个文件步骤数: {sum(inst['total_steps'] for inst in file_instructions) / len(file_instructions):.1f}")
    logging.info("="*60)
    
    # 5. 显示样本
    logging.info("\n=== Sample aggregated instructions ===")
    for inst in file_instructions[:5]:
        logging.info(f"\nFile: {inst['file_id']}")
        logging.info(f"  Task: {inst['inferred_task']} -> Action: {inst['primary_action']}")
        logging.info(f"  Category: {inst['object_category']}")
        logging.info(f"  Instruction: {inst['instruction']}")
        logging.info(f"  Objects ({inst['object_count']}): {', '.join(inst['objects'][:3])}...")


if __name__ == '__main__':
    main()
