#!/usr/bin/env python3
"""Verify the parsed workflow data."""

import json
import os

processed_dir = 'data/processed'

print('=' * 70)
print('📊 生成的数据文件统计')
print('=' * 70)
print()

for file in sorted(os.listdir(processed_dir)):
    if file.endswith(('.json', '.jsonl')):
        path = os.path.join(processed_dir, file)
        size = os.path.getsize(path) / (1024 * 1024)
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = sum(1 for _ in f)
        
        print(f'  {file}: {size:.2f} MB, {lines} 行')

print()
print('=' * 70)
print('📋 样本数据结构')
print('=' * 70)
print()

with open('data/processed/parsed_workflows.jsonl', 'r', encoding='utf-8') as f:
    sample = json.loads(f.readline())

print('第一个文件级数据：')
print(f'  file_id: {sample["file_id"]}')
print(f'  test_app: {sample["test_app"]}')
print(f'  test_env: {sample["test_env"]}')
print(f'  total_steps: {sample["total_steps"]}')
print()

if sample['steps']:
    print('第一个步骤的数据：')
    step = sample['steps'][0]
    print(f'  step_index: {step["step_index"]}')
    print(f'  database: {step["database"]}')
    print(f'  object: {step["object"]}')
    print(f'  object_id: {step["object_id"]}')
    print(f'  module: {step["module"]}')
    print(f'  method: {step["method"]}')
    print(f'  command: {step["command"]}')
    print(f'  test_data keys: {list(step["test_data"].keys())}')

print()
print('=' * 70)
print('✅ 数据验证完成！')
print('=' * 70)
