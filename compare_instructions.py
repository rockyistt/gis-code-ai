#!/usr/bin/env python3
"""对比旧版file级指令和新版聚合指令"""
import json

# 读取两个文件
old_file = 'data/processed/file_level_instructions_weighted.jsonl'
new_file = 'data/processed/file_level_instructions_aggregated.jsonl'

old_data = [json.loads(line) for line in open(old_file, 'r', encoding='utf-8')]
new_data = [json.loads(line) for line in open(new_file, 'r', encoding='utf-8')]

# 统计"multiple objects"
old_multiple = sum(1 for d in old_data if 'multiple objects' in d.get('instruction', '').lower())
new_multiple = sum(1 for d in new_data if 'multiple objects' in d.get('instruction', '').lower())

print("="*70)
print("📊 旧版 vs 新版 File级指令对比")
print("="*70)
print(f"\n旧版 (规则生成):")
print(f"  - 文件: {old_file}")
print(f"  - 记录数: {len(old_data)}")
print(f"  - 含\"multiple objects\": {old_multiple} ({old_multiple/len(old_data)*100:.1f}%)")
print(f"  - 提供者: {old_data[0]['provider']}")

print(f"\n新版 (Step聚合):")
print(f"  - 文件: {new_file}")
print(f"  - 记录数: {len(new_data)}")
print(f"  - 含\"multiple objects\": {new_multiple} ({new_multiple/len(new_data)*100:.1f}%)")
print(f"  - 提供者: {new_data[0]['provider']}")

print(f"\n✅ 改进效果: {old_multiple - new_multiple} 个文件不再使用模糊描述 (↓ {(old_multiple-new_multiple)/len(old_data)*100:.1f}%)")

# 对比样本
print("\n" + "="*70)
print("📝 样本对比 (同一个文件)")
print("="*70)

# 找一个有"multiple objects"的旧文件
old_sample = None
for old in old_data:
    if 'multiple objects' in old['instruction'].lower():
        old_sample = old
        break

if old_sample:
    file_id = old_sample['file_id']
    new_sample = next(d for d in new_data if d['file_id'] == file_id)
    
    print(f"\nFile ID: {file_id}")
    print(f"\n旧版指令:")
    print(f"  {old_sample['instruction']}")
    print(f"  对象列表: {old_sample.get('objects', [])}")
    
    print(f"\n新版指令:")
    print(f"  {new_sample['instruction']}")
    print(f"  对象列表: {new_sample.get('objects', [])}")
    print(f"  对象数量: {new_sample.get('object_count', 0)}")

print("\n" + "="*70)
