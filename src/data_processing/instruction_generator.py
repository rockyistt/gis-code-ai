"""
Generate English instructions from structured workflows using OpenAI GPT-4 and Tongyi Qianwen.
Includes module-based classification and context-aware instruction generation.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Literal, Optional
import logging
from openai import OpenAI
import dashscope
from http import HTTPStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module classification based on data analysis
NAVIGATION_MODULES = {
    "Tabs": {"methods": ["Select Tab"], "type": "navigation"},
    "Buttons": {"methods": ["Click Oneshot Button"], "type": "navigation"},
    "Datamodel Consistency Check": {"methods": ["Datamodel Check"], "type": "validation"}
}

DATA_RICH_MODULES = {
    "Editor(s)": {
        "methods": ["Open Object", "Open Object with ID", "Verify Field", "Switch Spatial Context"],
        "type": "editor"
    },
    "Hierarchy Viewer": {
        "methods": ["Select first HV object", "Select second HV object"],
        "type": "hierarchy"
    },
    "Datamodel CRUD": {
        "methods": ["Create", "Update"],
        "type": "crud"
    }
}

# Special cases
SPECIAL_CASES = {
    ("Datamodel CRUD", "Delete"): "empty"
}


class InstructionGenerator:
    """Generate instructions using LLMs (OpenAI GPT-4 and Tongyi Qianwen)."""
    
    def __init__(self, provider: Literal["openai", "qianwen"], api_key: str = None):
        """
        Args:
            provider: "openai" or "qianwen"
            api_key: API key (if None, will read from env)
        """
        self.provider = provider
        
        if provider == "openai":
            self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
            self.model = "gpt-4"
        elif provider == "qianwen":
            dashscope.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
            self.model = "qwen-max"
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert in GIS systems and test automation. Generate clear, concise instructions in English."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    
    def _call_qianwen(self, prompt: str) -> str:
        """Call Tongyi Qianwen API."""
        response = dashscope.Generation.call(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert in GIS systems and test automation. Generate clear, concise instructions in English."},
                {"role": "user", "content": prompt}
            ],
            result_format='message',
            temperature=0.7,
            max_tokens=500
        )
        
        if response.status_code == HTTPStatus.OK:
            return response.output.choices[0].message.content.strip()
        else:
            raise Exception(f"Qianwen API error: {response.message}")
    
    def generate_file_level_instruction(self, workflow: Dict[str, Any]) -> str:
        """
        Generate a file-level instruction describing the entire workflow.
        
        Args:
            workflow: Parsed workflow dict
            
        Returns:
            Generated instruction in English
        """
        # Build context
        steps_summary = []
        for step in workflow['steps']:
            steps_summary.append(f"- {step['module']}: {step['method']} on {step['object']}")
        
        steps_text = "\n".join(steps_summary)
        
        prompt = f"""Given this GIS test workflow, generate a concise user instruction in English that describes what the user wants to accomplish.

Application: {workflow['test_app']}
Total Steps: {workflow['total_steps']}
Steps:
{steps_text}

Generate a single sentence instruction (20-40 words) that describes the user's goal. 
Example: "Open the cable editor in the electrical network and create multiple cable objects with different voltage levels and spatial coordinates."

Instruction:"""

        if self.provider == "openai":
            return self._call_openai(prompt)
        else:
            return self._call_qianwen(prompt)
    
    def _classify_step(self, step: Dict[str, Any]) -> str:
        """Classify step as navigation, validation, or data-rich."""
        module = step['module']
        method = step['method']
        
        # Check special cases first
        if (module, method) in SPECIAL_CASES:
            return SPECIAL_CASES[(module, method)]
        
        # Check navigation modules
        if module in NAVIGATION_MODULES:
            return NAVIGATION_MODULES[module]["type"]
        
        # Check data-rich modules
        if module in DATA_RICH_MODULES:
            if method in DATA_RICH_MODULES[module]["methods"]:
                return DATA_RICH_MODULES[module]["type"]
        
        # Default: check if has data
        has_data = bool(step['test_data']['create'] or 
                       step['test_data']['update'] or 
                       step['test_data']['editor'])
        return "data_rich" if has_data else "empty"
    
    def _get_context_steps(self, workflow: Dict[str, Any], current_step_index: int, context_window: int = 3) -> List[Dict[str, Any]]:
        """Get previous N steps as context."""
        start_idx = max(0, current_step_index - context_window)
        return workflow['steps'][start_idx:current_step_index]
    
    def _format_context(self, context_steps: List[Dict[str, Any]]) -> str:
        """Format context steps into readable string."""
        if not context_steps:
            return "This is the first step."
        
        context_lines = []
        for step in context_steps:
            context_lines.append(f"Step {step['step_index']}: {step['method']} on {step['object']}")
        
        return "Previous steps:\n" + "\n".join(context_lines)
    
    def generate_step_level_instruction(self, workflow: Dict[str, Any], step: Dict[str, Any], include_context: bool = True) -> Optional[str]:
        """
        Generate a step-level instruction for a single step with context awareness.
        
        Args:
            workflow: Parent workflow dict
            step: Single step dict
            include_context: Whether to include previous steps as context
            
        Returns:
            Generated instruction in English, or None if step should be skipped
        """
        # Classify step
        step_type = self._classify_step(step)
        
        # Skip pure navigation steps (optional)
        if step_type in ["navigation", "validation", "empty"]:
            # Generate simple template instruction for navigation
            if step['method'] == "Select Tab":
                return f"Select the {step['object']} tab."
            elif step['method'] == "Click Oneshot Button":
                return f"Click the {step['object']} button."
            elif step['method'] == "Datamodel Check":
                return f"Perform datamodel consistency check on {step['object']}."
            else:
                return None  # Skip other empty steps
        
        # For data-rich steps, generate detailed context-aware instruction
        test_data = step['test_data']
        
        # Get context
        context_str = ""
        if include_context and step['step_index'] > 0:
            context_steps = self._get_context_steps(workflow, step['step_index'])
            context_str = self._format_context(context_steps)
        
        # Build data context
        data_context_parts = []
        if test_data['create']:
            data_context_parts.append(f"Create data: {json.dumps(test_data['create'], indent=2)}")
        if test_data['update']:
            data_context_parts.append(f"Update data: {json.dumps(test_data['update'], indent=2)}")
        if test_data['editor']:
            data_context_parts.append(f"Editor data: {json.dumps(test_data['editor'], indent=2)}")
        
        data_context = "\n".join(data_context_parts) if data_context_parts else "No additional data"
        
        prompt = f"""Given this step from a GIS test workflow, generate a concise instruction in English.

{context_str}

Current step:
Module: {step['module']}
Method: {step['method']}
Object: {step['object']}
Database: {step['database']}
{data_context}

Generate a single sentence instruction (20-40 words) that:
1. Considers the previous steps if provided
2. Clearly describes what this step does
3. Includes key details from the data

Example: "After opening the editor, create an MS cable object in the elektra database with 3-phase status and coordinates (186355533, 439556907)."

Instruction:"""

        if self.provider == "openai":
            return self._call_openai(prompt)
        else:
            return self._call_qianwen(prompt)
    
    def batch_generate(
        self, 
        workflows_path: str,
        output_file_level: str,
        output_step_level: str,
        max_workflows: int = None,
        skip_navigation: bool = False,
        include_context: bool = True
    ):
        """
        Generate instructions for all workflows with module classification.
        
        Args:
            workflows_path: Path to parsed_workflows.jsonl
            output_file_level: Output path for file-level instructions
            output_step_level: Output path for step-level instructions
            max_workflows: Max number of workflows to process (for testing)
            skip_navigation: Whether to skip navigation/empty steps
            include_context: Whether to include previous steps as context
        """
        workflows = []
        with open(workflows_path, 'r', encoding='utf-8') as f:
            for line in f:
                workflows.append(json.loads(line))
        
        if max_workflows:
            workflows = workflows[:max_workflows]
        
        logger.info(f"Generating instructions for {len(workflows)} workflows using {self.provider}")
        logger.info(f"Options: skip_navigation={skip_navigation}, include_context={include_context}")
        
        file_level_results = []
        step_level_results = []
        
        total_steps = 0
        skipped_steps = 0
        processed_steps = 0
        
        for i, workflow in enumerate(workflows):
            try:
                # File-level instruction
                file_instruction = self.generate_file_level_instruction(workflow)
                file_level_results.append({
                    "file_id": workflow['file_id'],
                    "is_high_quality": workflow['is_high_quality'],
                    "instruction": file_instruction,
                    "provider": self.provider,
                    "test_app": workflow['test_app'],
                    "total_steps": workflow['total_steps'],
                    "workflow_summary": {
                        "modules": list(set(s['module'] for s in workflow['steps'])),
                        "objects": list(set(s['object'] for s in workflow['steps']))
                    }
                })
                logger.info(f"✓ [{i+1}/{len(workflows)}] File-level: {workflow['file_id']}")
                
                # Step-level instructions
                for step in workflow['steps']:
                    total_steps += 1
                    step_type = self._classify_step(step)
                    
                    # Skip navigation steps if requested
                    if skip_navigation and step_type in ["navigation", "validation", "empty"]:
                        skipped_steps += 1
                        continue
                    
                    step_instruction = self.generate_step_level_instruction(
                        workflow, step, include_context=include_context
                    )
                    
                    if step_instruction:  # Only save if instruction was generated
                        processed_steps += 1
                        step_level_results.append({
                            "file_id": workflow['file_id'],
                            "step_index": step['step_index'],
                            "step_type": step_type,
                            "is_high_quality": workflow['is_high_quality'],
                            "instruction": step_instruction,
                            "provider": self.provider,
                            "module": step['module'],
                            "method": step['method'],
                            "code": step
                        })
                    else:
                        skipped_steps += 1
                
            except Exception as e:
                logger.error(f"✗ Failed {workflow['file_id']}: {e}")
        
        # Save results
        Path(output_file_level).parent.mkdir(parents=True, exist_ok=True)
        Path(output_step_level).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file_level, 'w', encoding='utf-8') as f:
            for result in file_level_results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        
        with open(output_step_level, 'w', encoding='utf-8') as f:
            for result in step_level_results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        
        logger.info(f"\n=== Summary ===")
        logger.info(f"Total steps processed: {total_steps}")
        logger.info(f"Steps with instructions: {processed_steps}")
        logger.info(f"Skipped steps: {skipped_steps}")
        logger.info(f"Saved {len(file_level_results)} file-level instructions to {output_file_level}")
        logger.info(f"Saved {len(step_level_results)} step-level instructions to {output_step_level}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python instruction_generator.py [openai|qianwen]")
        sys.exit(1)
    
    provider = sys.argv[1]
    
    generator = InstructionGenerator(provider=provider)
    generator.batch_generate(
        workflows_path="data/processed/parsed_workflows.jsonl",
        output_file_level=f"data/processed/file_level_instructions_{provider}.jsonl",
        output_step_level=f"data/processed/step_level_instructions_{provider}.jsonl",
        max_workflows=2,  # Test with 2 workflows first
        skip_navigation=False,  # Keep all steps for testing
        include_context=True  # Include previous 3 steps as context
    )
