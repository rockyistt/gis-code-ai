"""验证脱敏数据"""
import json

print('Sample from parsed_workflows_anonymized.jsonl:')
with open('data/processed/parsed_workflows_anonymized.jsonl', 'r', encoding='utf-8') as f:
    for i in range(3):
        line = f.readline()
        data = json.loads(line)
        print(f'  {i+1}. file_id: {data["file_id"]}, steps: {data["total_steps"]}')

print('\nSample from file_level_instructions_anonymized.jsonl:')
with open('data/processed/file_level_instructions_anonymized.jsonl', 'r', encoding='utf-8') as f:
    for i in range(3):
        line = f.readline()
        data = json.loads(line)
        print(f'  {i+1}. file_id: {data["file_id"]}, step_idx: {data.get("step_idx", "N/A")}')

print('\nMapping statistics:')
with open('data/processed/file_id_mapping.json', 'r', encoding='utf-8') as f:
    mapping = json.load(f)
    print(f'  Total mappings: {len(mapping)}')
    print(f'  First 5 mappings:')
    for i, (orig, anon) in enumerate(list(mapping.items())[:5]):
        print(f'    {orig:50s} -> {anon}')
