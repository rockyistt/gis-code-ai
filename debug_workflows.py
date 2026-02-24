import json

print("=" * 80)
print("诊断: File #11 & File #12 的工作流详情")
print("=" * 80)

with open('data/processed/parsed_workflows.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i == 11 or i == 12:
            data = json.loads(line)
            print(f"\n{'=' * 80}")
            print(f"File #{i}")
            print(f"{'=' * 80}")
            print(f"Test App: {data.get('test_app', 'N/A')}")
            print(f"Total Steps: {len(data.get('steps', []))}")
            print(f"\n前5个steps的方法（Method）：")
            for j, step in enumerate(data.get('steps', [])[:5]):
                print(f"  Step {j}: object='{step.get('object', 'N/A')}', method='{step.get('method', 'N/A')}'")
