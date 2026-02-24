import json

print("=" * 80)
print("改进后的文件级指令样本（带权重信息）")
print("=" * 80)

with open('data/processed/file_level_instructions.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 15:
            break
        data = json.loads(line)
        print(f"\n【File {i:2d}】")
        print(f"  指令: {data['instruction']}")
        print(f"  动作: {data['actions']}")
        print(f"  对象: {data['objects']}")
        print(f"  权重关键词:")
        for keyword, weight in data['keywords']:
            weight_level = "⭐⭐⭐" if weight >= 3.0 else ("⭐⭐" if weight >= 2.0 else "⭐")
            print(f"    {weight_level} {keyword} = {weight}")
