"""
Parse flat GIS test JSON files into structured workflow format.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowParser:
    """Parse flat JSON structure into structured workflow."""
    
    def __init__(self, raw_data_dir: str):
        """
        Args:
            raw_data_dir: Directory containing raw JSON files
        """
        self.raw_data_dir = Path(raw_data_dir)
        
    def parse_file(self, json_path: Path) -> Dict[str, Any]:
        """
        Parse a single JSON file into structured format.
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            Structured workflow dict
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Determine if from template folder (high quality)
        is_template = 'template' in str(json_path).lower()
        
        # Extract metadata
        # Handle teststeps0 - can be int or string
        total_steps_raw = data.get("teststeps0", [0])
        if total_steps_raw and len(total_steps_raw) > 0:
            try:
                total_steps = int(total_steps_raw[0]) if isinstance(total_steps_raw[0], (str, int)) else 0
            except (ValueError, TypeError):
                total_steps = 0
        else:
            total_steps = 0
        
        # Generate unique file_id with folder prefix to avoid duplicates
        # Example: "template/test_001" instead of just "test_001"
        try:
            relative_path = json_path.relative_to(self.raw_data_dir)
            # Use parent folder + filename (without extension)
            folder_prefix = relative_path.parent.name if relative_path.parent.name != '.' else ''
            file_id = f"{folder_prefix}/{json_path.stem}" if folder_prefix else json_path.stem
        except ValueError:
            # Fallback if relative path calculation fails
            file_id = json_path.stem
        
        workflow = {
            "file_id": file_id,
            "file_path": str(json_path),
            "is_high_quality": is_template,
            "test_env": data.get("testenvs0", ["Unknown"])[0] if data.get("testenvs0") else "Unknown",
            "test_app": data.get("testapps0", ["Unknown"])[0] if data.get("testapps0") else "Unknown",
            "total_steps": total_steps,
            "test_cases": data.get("testcases", []),
            "steps": []
        }
        
        # Parse steps
        total_steps = workflow["total_steps"]
        for step_idx in range(total_steps):
            step = self._parse_step(data, step_idx)
            if step:
                workflow["steps"].append(step)
        
        return workflow
    
    def _parse_step(self, data: Dict, step_idx: int) -> Dict[str, Any]:
        """Parse a single step from flat structure."""
        suffix = f"0_{step_idx}"
        
        step = {
            "step_index": step_idx,
            "database": data.get(f"testdbs{suffix}", ""),
            "object": data.get(f"testobjs{suffix}", ""),
            "object_id": data.get(f"testobj_ids{suffix}", ""),
            "module": data.get(f"testmodules{suffix}", ""),
            "method": data.get(f"testmethodes{suffix}", ""),
            "command": data.get(f"testcommands{suffix}", ""),
            "test_data": {
                "create": data.get(f"testdata_cr{suffix}", {}),
                "update": data.get(f"testdata_upd{suffix}", {}),
                "editor": data.get(f"testdata_editor{suffix}", {})
            }
        }
        
        return step
    
    def parse_all(self, output_path: str) -> List[Dict[str, Any]]:
        """
        Parse all JSON files in raw_data_dir.
        
        Args:
            output_path: Path to save parsed workflows (JSONL format)
            
        Returns:
            List of parsed workflows
        """
        workflows = []
        json_files = list(self.raw_data_dir.rglob("*.json"))
        
        logger.info(f"Found {len(json_files)} JSON files")
        
        for json_path in json_files:
            try:
                workflow = self.parse_file(json_path)
                workflows.append(workflow)
                logger.info(f"✓ Parsed: {json_path.name} ({workflow['total_steps']} steps)")
            except Exception as e:
                logger.error(f"✗ Failed to parse {json_path}: {e}")
        
        # Save to JSONL
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for workflow in workflows:
                f.write(json.dumps(workflow, ensure_ascii=False) + '\n')
        
        logger.info(f"Saved {len(workflows)} workflows to {output_path}")
        
        # Statistics
        high_quality_count = sum(1 for w in workflows if w['is_high_quality'])
        logger.info(f"High quality (template): {high_quality_count}/{len(workflows)}")
        
        return workflows


if __name__ == "__main__":
    # Example usage
    parser = WorkflowParser(raw_data_dir="data/raw")
    workflows = parser.parse_all(output_path="data/processed/parsed_workflows.jsonl")
    
    # Show sample
    if workflows:
        print("\n=== Sample Workflow ===")
        sample = workflows[0]
        print(f"File: {sample['file_id']}")
        print(f"App: {sample['test_app']}")
        print(f"Steps: {sample['total_steps']}")
        print(f"High Quality: {sample['is_high_quality']}")
        if sample['steps']:
            print(f"\nFirst step: {sample['steps'][0]['module']} - {sample['steps'][0]['method']}")
