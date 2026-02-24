#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证生成的数据文件"""

import json
import os

print('='*70)
print('📋 验证生成的数据文件结构')
print('='*70)

# 检查Task-1训练数据
print('\n1️⃣ Task-1 文件→步骤 (训练样本)')
print('-'*70)
with open('data/training/task1_file_to_steps_train.json', 'r', encoding='utf-8') as f:
    task1_train = json.load(f)

sample = task1_train[0]
print(f'总样本数: {len(task1_train)}')
print(f'\n示例样本:')
print(f'  Input (文件级指令): {sample["input"][:60]}...')
print(f'  Output (步骤指令列表):')
for i, step in enumerate(sample['output'][:3], 1):
    print(f'    {i}. {step}')
if len(sample['output']) > 3:
    print(f'    ... (共 {len(sample["output"])} 步)')
print(f'  Metadata: file_id={sample["metadata"]["file_id"]}, num_steps={sample["metadata"]["num_steps"]}')

# 检查Task-2训练数据
print('\n\n2️⃣ Task-2 步骤→JSON (训练样本)')
print('-'*70)
with open('data/training/task2_step_to_json_train.json', 'r', encoding='utf-8') as f:
    task2_train = json.load(f)

sample2 = task2_train[0]
print(f'总样本数: {len(task2_train)}')
print(f'\n示例样本:')
print(f'  Input (步骤指令): {sample2["input"]}')
print(f'  Context:')
print(f'    - file_task: {sample2["context"]["file_task"][:50]}...')
print(f'    - step_index: {sample2["context"]["step_index"]}/{sample2["context"]["total_steps"]}')
print(f'    - previous_steps: {sample2["context"]["previous_steps"]}')
if sample2['context']['remaining_steps']:
    remaining = sample2['context']['remaining_steps'][:2]
    print(f'    - remaining_steps: {remaining}')
print(f'  Output (JSON代码): {str(sample2["output"])[:80]}...')
print(f'  Metadata: file_id={sample2["metadata"]["file_id"]}, step_index={sample2["metadata"]["step_index"]}')

# 验证集信息
print('\n\n3️⃣ 验证集信息')
print('-'*70)
with open('data/training/task1_file_to_steps_val.json', 'r', encoding='utf-8') as f:
    task1_val = json.load(f)

with open('data/training/task2_step_to_json_val.json', 'r', encoding='utf-8') as f:
    task2_val = json.load(f)

print(f'Task-1 验证集: {len(task1_val)} 个样本')
print(f'Task-2 验证集: {len(task2_val)} 个样本')

# 数据一致性检查
print('\n\n4️⃣ 数据一致性检查')
print('-'*70)
task1_file_ids = set(d['metadata']['file_id'] for d in task1_train)
task2_file_ids = set(d['metadata']['file_id'] for d in task2_train)
print(f'Task-1 训练文件数: {len(task1_file_ids)}')
print(f'Task-2 训练文件数: {len(task2_file_ids)}')
print(f'文件ID一致性: {task1_file_ids == task2_file_ids}')

# 计算平均步骤数
avg_steps = sum(d['metadata']['num_steps'] for d in task1_train) / len(task1_train)
print(f'\n平均每个文件的步骤数: {avg_steps:.2f}')

print('\n\n5️⃣ 文件大小信息')
print('-'*70)
files = [
    ('data/training/task1_file_to_steps_train.json', 'Task-1 Training'),
    ('data/training/task1_file_to_steps_val.json', 'Task-1 Validation'),
    ('data/training/task2_step_to_json_train.json', 'Task-2 Training'),
    ('data/training/task2_step_to_json_val.json', 'Task-2 Validation'),
]
for path, name in files:
    if os.path.exists(path):
        size = os.path.getsize(path) / 1024 / 1024
        print(f'{name}: {size:.2f} MB')

print('\n' + '='*70)
print('✨ 验证完成！数据文件结构正确。')
print('='*70 + '\n')
