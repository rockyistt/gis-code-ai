"""
Analyze the relationship between empty steps and modules.
"""

import json
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_empty_steps_by_module(workflows_path: str):
    """Analyze which modules tend to have empty steps."""
    
    workflows = []
    with open(workflows_path, 'r', encoding='utf-8') as f:
        for line in f:
            workflows.append(json.loads(line))
    
    # Statistics by module
    module_stats = defaultdict(lambda: {"total": 0, "empty": 0, "has_data": 0})
    
    # Statistics by method
    method_stats = defaultdict(lambda: {"total": 0, "empty": 0, "has_data": 0})
    
    # Combined module + method
    combined_stats = defaultdict(lambda: {"total": 0, "empty": 0, "has_data": 0})
    
    for workflow in workflows:
        for step in workflow['steps']:
            module = step['module']
            method = step['method']
            combined = f"{module} -> {method}"
            
            # Check if empty
            has_create = bool(step['test_data']['create'])
            has_update = bool(step['test_data']['update'])
            has_editor = bool(step['test_data']['editor'])
            is_empty = not (has_create or has_update or has_editor)
            
            # Update module stats
            module_stats[module]["total"] += 1
            if is_empty:
                module_stats[module]["empty"] += 1
            else:
                module_stats[module]["has_data"] += 1
            
            # Update method stats
            method_stats[method]["total"] += 1
            if is_empty:
                method_stats[method]["empty"] += 1
            else:
                method_stats[method]["has_data"] += 1
            
            # Update combined stats
            combined_stats[combined]["total"] += 1
            if is_empty:
                combined_stats[combined]["empty"] += 1
            else:
                combined_stats[combined]["has_data"] += 1
    
    # Calculate percentages and sort
    module_results = []
    for module, stats in module_stats.items():
        empty_pct = (stats["empty"] / stats["total"]) * 100
        module_results.append({
            "module": module,
            "total": stats["total"],
            "empty": stats["empty"],
            "has_data": stats["has_data"],
            "empty_pct": empty_pct
        })
    
    method_results = []
    for method, stats in method_stats.items():
        empty_pct = (stats["empty"] / stats["total"]) * 100
        method_results.append({
            "method": method,
            "total": stats["total"],
            "empty": stats["empty"],
            "has_data": stats["has_data"],
            "empty_pct": empty_pct
        })
    
    combined_results = []
    for combined, stats in combined_stats.items():
        empty_pct = (stats["empty"] / stats["total"]) * 100
        combined_results.append({
            "combined": combined,
            "total": stats["total"],
            "empty": stats["empty"],
            "has_data": stats["has_data"],
            "empty_pct": empty_pct
        })
    
    # Sort by empty percentage
    module_results.sort(key=lambda x: x["empty_pct"], reverse=True)
    method_results.sort(key=lambda x: x["empty_pct"], reverse=True)
    combined_results.sort(key=lambda x: x["total"], reverse=True)
    
    # Print results
    print("=" * 80)
    print("📊 模块（Module）与空步骤的关系")
    print("=" * 80)
    print()
    
    print("🔴 最常为空的模块（Empty步骤比例最高）：")
    print(f"{'模块':<40} {'总数':>8} {'空步骤':>8} {'有数据':>8} {'空步骤%':>10}")
    print("-" * 80)
    for item in module_results[:10]:
        print(f"{item['module']:<40} {item['total']:>8} {item['empty']:>8} "
              f"{item['has_data']:>8} {item['empty_pct']:>9.1f}%")
    
    print("\n")
    print("🟢 最常有数据的模块（Empty步骤比例最低）：")
    print(f"{'模块':<40} {'总数':>8} {'空步骤':>8} {'有数据':>8} {'空步骤%':>10}")
    print("-" * 80)
    for item in sorted(module_results, key=lambda x: x["empty_pct"])[:10]:
        print(f"{item['module']:<40} {item['total']:>8} {item['empty']:>8} "
              f"{item['has_data']:>8} {item['empty_pct']:>9.1f}%")
    
    print("\n")
    print("=" * 80)
    print("📊 方法（Method）与空步骤的关系")
    print("=" * 80)
    print()
    
    print("🔴 最常为空的方法：")
    print(f"{'方法':<40} {'总数':>8} {'空步骤':>8} {'有数据':>8} {'空步骤%':>10}")
    print("-" * 80)
    for item in method_results[:15]:
        print(f"{item['method']:<40} {item['total']:>8} {item['empty']:>8} "
              f"{item['has_data']:>8} {item['empty_pct']:>9.1f}%")
    
    print("\n")
    print("🟢 最常有数据的方法：")
    print(f"{'方法':<40} {'总数':>8} {'空步骤':>8} {'有数据':>8} {'空步骤%':>10}")
    print("-" * 80)
    for item in sorted(method_results, key=lambda x: x["empty_pct"])[:15]:
        if item['total'] > 50:  # Filter out rare methods
            print(f"{item['method']:<40} {item['total']:>8} {item['empty']:>8} "
                  f"{item['has_data']:>8} {item['empty_pct']:>9.1f}%")
    
    print("\n")
    print("=" * 80)
    print("📊 模块+方法组合（最常见的前20个）")
    print("=" * 80)
    print()
    print(f"{'模块 -> 方法':<60} {'总数':>8} {'空%':>8}")
    print("-" * 80)
    for item in combined_results[:20]:
        print(f"{item['combined']:<60} {item['total']:>8} {item['empty_pct']:>7.1f}%")
    
    print("\n")
    print("=" * 80)
    print("💡 关键发现")
    print("=" * 80)
    
    # Find patterns
    always_empty_modules = [m for m in module_results if m['empty_pct'] > 95 and m['total'] > 100]
    always_has_data_modules = [m for m in module_results if m['empty_pct'] < 5 and m['total'] > 100]
    
    print(f"\n🔴 几乎总是空的模块（>95% 空步骤，出现>100次）：")
    for m in always_empty_modules:
        print(f"  - {m['module']}: {m['empty_pct']:.1f}% 空 ({m['empty']}/{m['total']})")
    
    print(f"\n🟢 几乎总是有数据的模块（<5% 空步骤，出现>100次）：")
    for m in always_has_data_modules:
        print(f"  - {m['module']}: {m['empty_pct']:.1f}% 空 ({m['has_data']}/{m['total']} 有数据)")
    
    print("\n💭 建议:")
    print("  1. 对于几乎总是空的模块（如Tabs、Buttons），可以生成简化的导航指令")
    print("  2. 对于总是有数据的模块（如Datamodel CRUD），应该生成详细的操作指令")
    print("  3. 对于混合情况的模块（如Editor），需要检查具体的method来决定")
    print("=" * 80)
    
    # Save detailed results
    results = {
        "module_stats": module_results,
        "method_stats": method_results,
        "combined_stats": combined_results[:50],
        "always_empty_modules": [m['module'] for m in always_empty_modules],
        "always_has_data_modules": [m['module'] for m in always_has_data_modules]
    }
    
    output_path = "data/processed/empty_steps_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n详细结果已保存到: {output_path}")


if __name__ == "__main__":
    analyze_empty_steps_by_module("data/processed/parsed_workflows.jsonl")
