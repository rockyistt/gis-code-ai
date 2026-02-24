import json

print("=" * 80)
print("改进后的文件级指令样本（验证'multiple objects'问题修复）")
print("=" * 80)

with open('data/processed/file_level_instructions_weighted.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 20:
            break
        data = json.loads(line)
        print(f"\n【File {i:2d}】")
        print(f"  指令: {data['instruction']}")
        
        # 检查是否还有"multiple objects"
        if "multiple objects" in data['instruction'].lower():
            print(f"  ⚠️  WARNING: 仍含有'multiple objects'")
        
        # 显示对象列表
        print(f"  对象: {data['objects'][:3]}" + ("  ..." if len(data['objects']) > 3 else ""))
        
        # 显示动作
        print(f"  动作: {data['actions']}")
