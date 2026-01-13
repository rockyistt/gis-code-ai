"""
Complete data processing pipeline: Parse JSON -> Generate Instructions (OpenAI & Qwen)
"""

import argparse
import logging
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_processing.workflow_parser import WorkflowParser
from data_processing.instruction_generator import InstructionGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_pipeline(
    raw_data_dir: str = "data/raw",
    processed_dir: str = "data/processed",
    openai_key: str = None,
    qianwen_key: str = None,
    max_workflows: int = None
):
    """
    Run the complete data processing pipeline.
    
    Args:
        raw_data_dir: Directory with raw JSON files
        processed_dir: Output directory for processed data
        openai_key: OpenAI API key (or set OPENAI_API_KEY env var)
        qianwen_key: DashScope API key (or set DASHSCOPE_API_KEY env var)
        max_workflows: Max workflows to process (for testing)
    """
    processed_path = Path(processed_dir)
    processed_path.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Parse workflows
    logger.info("=" * 60)
    logger.info("STEP 1: Parsing JSON workflows")
    logger.info("=" * 60)
    
    parser = WorkflowParser(raw_data_dir=raw_data_dir)
    parsed_output = processed_path / "parsed_workflows.jsonl"
    workflows = parser.parse_all(output_path=str(parsed_output))
    
    if not workflows:
        logger.error("No workflows parsed. Check your raw data directory.")
        return
    
    logger.info(f"\n✓ Parsed {len(workflows)} workflows")
    
    # Step 2: Generate instructions with OpenAI
    if openai_key or True:  # Allow env var
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: Generating instructions with OpenAI GPT-4")
        logger.info("=" * 60)
        
        try:
            openai_gen = InstructionGenerator(provider="openai", api_key=openai_key)
            openai_gen.batch_generate(
                workflows_path=str(parsed_output),
                output_file_level=str(processed_path / "file_level_instructions_openai.jsonl"),
                output_step_level=str(processed_path / "step_level_instructions_openai.jsonl"),
                max_workflows=max_workflows
            )
            logger.info("✓ OpenAI instruction generation complete")
        except Exception as e:
            logger.error(f"✗ OpenAI generation failed: {e}")
    
    # Step 3: Generate instructions with Qianwen
    if qianwen_key or True:  # Allow env var
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: Generating instructions with Tongyi Qianwen")
        logger.info("=" * 60)
        
        try:
            qianwen_gen = InstructionGenerator(provider="qianwen", api_key=qianwen_key)
            qianwen_gen.batch_generate(
                workflows_path=str(parsed_output),
                output_file_level=str(processed_path / "file_level_instructions_qianwen.jsonl"),
                output_step_level=str(processed_path / "step_level_instructions_qianwen.jsonl"),
                max_workflows=max_workflows
            )
            logger.info("✓ Qianwen instruction generation complete")
        except Exception as e:
            logger.error(f"✗ Qianwen generation failed: {e}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Output directory: {processed_dir}")
    logger.info(f"Files generated:")
    for file in processed_path.glob("*.jsonl"):
        logger.info(f"  - {file.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run GIS data processing pipeline")
    parser.add_argument(
        "--raw-dir",
        default="data/raw",
        help="Directory containing raw JSON files"
    )
    parser.add_argument(
        "--processed-dir",
        default="data/processed",
        help="Output directory for processed data"
    )
    parser.add_argument(
        "--openai-key",
        help="OpenAI API key (or set OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--qianwen-key",
        help="DashScope API key (or set DASHSCOPE_API_KEY env var)"
    )
    parser.add_argument(
        "--max-workflows",
        type=int,
        help="Max workflows to process (for testing)"
    )
    
    args = parser.parse_args()
    
    run_pipeline(
        raw_data_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        openai_key=args.openai_key,
        qianwen_key=args.qianwen_key,
        max_workflows=args.max_workflows
    )
