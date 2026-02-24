import json

print("=" * 80)
print("前15条改进后的文件级指令")
print("=" * 80)

with open('data/processed/file_level_instructions.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 15:
            break
        data = json.loads(line)
        print(f'File {i:2d}: {data["instruction"]}')
