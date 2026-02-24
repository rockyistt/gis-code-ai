"""
LoRA微调脚本 - 训练GIS代码生成模型

使用Qwen2.5-Coder-7B作为基座模型，通过LoRA在GIS指令数据上微调

依赖：
- transformers
- peft
- torch
- datasets
- accelerate
"""

import os
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional
import torch
from dataclasses import dataclass, field

# Transformers imports
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
    BitsAndBytesConfig
)

# PEFT imports
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)

# Dataset
from datasets import load_dataset, Dataset

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ModelArguments:
    """模型参数"""
    model_name_or_path: str = field(
        default="Qwen/Qwen2.5-Coder-7B-Instruct",
        metadata={"help": "基座模型路径"}
    )
    use_4bit: bool = field(
        default=True,
        metadata={"help": "使用4-bit量化（节省显存）"}
    )
    use_8bit: bool = field(
        default=False,
        metadata={"help": "使用8-bit量化"}
    )


@dataclass
class DataArguments:
    """数据参数"""
    train_file: str = field(
        default="data/processed/training_data_train.json",
        metadata={"help": "训练数据文件"}
    )
    val_file: str = field(
        default="data/processed/training_data_val.json",
        metadata={"help": "验证数据文件"}
    )
    max_length: int = field(
        default=2048,
        metadata={"help": "最大序列长度"}
    )


@dataclass
class LoraArguments:
    """LoRA参数"""
    lora_r: int = field(
        default=64,
        metadata={"help": "LoRA秩"}
    )
    lora_alpha: int = field(
        default=16,
        metadata={"help": "LoRA alpha"}
    )
    lora_dropout: float = field(
        default=0.05,
        metadata={"help": "LoRA dropout"}
    )
    target_modules: List[str] = field(
        default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj",
                                 "gate_proj", "up_proj", "down_proj"],
        metadata={"help": "LoRA目标模块"}
    )


class GISTrainer:
    """GIS代码生成模型训练器"""
    
    def __init__(
        self,
        model_args: ModelArguments,
        data_args: DataArguments,
        lora_args: LoraArguments,
        training_args: TrainingArguments
    ):
        self.model_args = model_args
        self.data_args = data_args
        self.lora_args = lora_args
        self.training_args = training_args
        
        self.tokenizer = None
        self.model = None
        self.train_dataset = None
        self.eval_dataset = None
    
    def load_tokenizer(self):
        """加载tokenizer"""
        logger.info(f"📖 Loading tokenizer from {self.model_args.model_name_or_path}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_args.model_name_or_path,
            trust_remote_code=True,
            padding_side="right"
        )
        
        # 设置特殊token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        logger.info(f"✅ Tokenizer loaded: vocab_size={len(self.tokenizer)}")
    
    def load_model(self):
        """加载模型并应用LoRA"""
        logger.info(f"🤖 Loading model from {self.model_args.model_name_or_path}")
        
        # 量化配置
        quantization_config = None
        if self.model_args.use_4bit:
            logger.info("📉 Using 4-bit quantization")
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
        elif self.model_args.use_8bit:
            logger.info("📉 Using 8-bit quantization")
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True
            )
        
        # 加载基座模型
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_args.model_name_or_path,
            quantization_config=quantization_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.float16,
        )
        
        logger.info("✅ Base model loaded")
        
        # 准备模型用于训练
        if quantization_config:
            self.model = prepare_model_for_kbit_training(self.model)
        
        # 配置LoRA
        logger.info("🔧 Applying LoRA configuration")
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            inference_mode=False,
            r=self.lora_args.lora_r,
            lora_alpha=self.lora_args.lora_alpha,
            lora_dropout=self.lora_args.lora_dropout,
            target_modules=self.lora_args.target_modules,
            bias="none"
        )
        
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()
        
        logger.info("✅ LoRA applied successfully")
    
    def prepare_datasets(self):
        """准备训练和验证数据集"""
        logger.info("📊 Preparing datasets")
        
        # 加载数据
        train_data = load_dataset('json', data_files=self.data_args.train_file, split='train')
        eval_data = load_dataset('json', data_files=self.data_args.val_file, split='train')
        
        logger.info(f"  Train: {len(train_data)} samples")
        logger.info(f"  Val: {len(eval_data)} samples")
        
        # 格式化prompt
        def format_prompt(example):
            """格式化为Qwen的对话格式"""
            instruction = example['instruction']
            input_text = example.get('input', '')
            output = example['output']
            
            # 构建prompt
            if input_text:
                prompt = f"""Below is an instruction that describes a task, paired with context information. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Context:
{input_text}

### Response:
{output}"""
            else:
                prompt = f"""Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Response:
{output}"""
            
            return {"text": prompt}
        
        # 应用格式化
        train_data = train_data.map(format_prompt, remove_columns=train_data.column_names)
        eval_data = eval_data.map(format_prompt, remove_columns=eval_data.column_names)
        
        # Tokenize
        def tokenize_function(examples):
            tokenized = self.tokenizer(
                examples['text'],
                truncation=True,
                max_length=self.data_args.max_length,
                padding=False,
                return_tensors=None
            )
            tokenized["labels"] = tokenized["input_ids"].copy()
            return tokenized
        
        logger.info("🔄 Tokenizing datasets...")
        self.train_dataset = train_data.map(
            tokenize_function,
            batched=True,
            remove_columns=train_data.column_names,
            desc="Tokenizing train"
        )
        
        self.eval_dataset = eval_data.map(
            tokenize_function,
            batched=True,
            remove_columns=eval_data.column_names,
            desc="Tokenizing val"
        )
        
        logger.info("✅ Datasets prepared")
    
    def train(self):
        """开始训练"""
        logger.info("🚀 Starting training...")
        
        # Data collator
        data_collator = DataCollatorForSeq2Seq(
            tokenizer=self.tokenizer,
            model=self.model,
            padding=True
        )
        
        # 创建Trainer
        trainer = Trainer(
            model=self.model,
            args=self.training_args,
            train_dataset=self.train_dataset,
            eval_dataset=self.eval_dataset,
            tokenizer=self.tokenizer,
            data_collator=data_collator,
        )
        
        # 训练
        trainer.train()
        
        # 保存最终模型
        logger.info(f"💾 Saving final model to {self.training_args.output_dir}")
        trainer.save_model()
        self.tokenizer.save_pretrained(self.training_args.output_dir)
        
        logger.info("🎉 Training completed!")
        
        return trainer


def main():
    parser = argparse.ArgumentParser(description="LoRA微调GIS代码生成模型")
    
    # 模型参数
    parser.add_argument('--model-name', type=str,
                       default="Qwen/Qwen2.5-Coder-7B-Instruct",
                       help='基座模型名称')
    parser.add_argument('--use-4bit', action='store_true', default=True,
                       help='使用4-bit量化')
    parser.add_argument('--use-8bit', action='store_true',
                       help='使用8-bit量化')
    
    # 数据参数
    parser.add_argument('--train-file', type=str,
                       default='data/processed/training_data_train.json',
                       help='训练数据文件')
    parser.add_argument('--val-file', type=str,
                       default='data/processed/training_data_val.json',
                       help='验证数据文件')
    parser.add_argument('--max-length', type=int, default=2048,
                       help='最大序列长度')
    
    # LoRA参数
    parser.add_argument('--lora-r', type=int, default=64,
                       help='LoRA秩')
    parser.add_argument('--lora-alpha', type=int, default=16,
                       help='LoRA alpha')
    parser.add_argument('--lora-dropout', type=float, default=0.05,
                       help='LoRA dropout')
    
    # 训练参数
    parser.add_argument('--output-dir', type=str,
                       default='models/qwen-gis-lora',
                       help='模型输出目录')
    parser.add_argument('--num-epochs', type=int, default=3,
                       help='训练轮数')
    parser.add_argument('--batch-size', type=int, default=4,
                       help='训练batch size')
    parser.add_argument('--gradient-accumulation-steps', type=int, default=4,
                       help='梯度累积步数')
    parser.add_argument('--learning-rate', type=float, default=2e-4,
                       help='学习率')
    parser.add_argument('--warmup-steps', type=int, default=100,
                       help='预热步数')
    parser.add_argument('--logging-steps', type=int, default=10,
                       help='日志输出频率')
    parser.add_argument('--save-steps', type=int, default=500,
                       help='模型保存频率')
    
    args = parser.parse_args()
    
    # 创建参数对象
    model_args = ModelArguments(
        model_name_or_path=args.model_name,
        use_4bit=args.use_4bit and not args.use_8bit,
        use_8bit=args.use_8bit
    )
    
    data_args = DataArguments(
        train_file=args.train_file,
        val_file=args.val_file,
        max_length=args.max_length
    )
    
    lora_args = LoraArguments(
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout
    )
    
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_steps=args.warmup_steps,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        eval_steps=args.save_steps,
        evaluation_strategy="steps",
        save_strategy="steps",
        load_best_model_at_end=True,
        fp16=True,
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        save_total_limit=3,
        report_to="none",  # 可改为"tensorboard"或"wandb"
    )
    
    # 检查输入文件
    if not Path(args.train_file).exists():
        logger.error(f"❌ Train file not found: {args.train_file}")
        logger.info("💡 请先运行: python scripts/03_split_training_data.py")
        return
    
    # 创建训练器并开始训练
    logger.info("="*70)
    logger.info("🎯 GIS代码生成模型 - LoRA微调")
    logger.info("="*70)
    logger.info(f"📦 模型: {args.model_name}")
    logger.info(f"📊 训练数据: {args.train_file}")
    logger.info(f"📊 验证数据: {args.val_file}")
    logger.info(f"🔧 LoRA r={args.lora_r}, alpha={args.lora_alpha}")
    logger.info(f"📈 Epochs={args.num_epochs}, Batch={args.batch_size}, LR={args.learning_rate}")
    logger.info(f"💾 输出: {args.output_dir}")
    logger.info("="*70)
    
    trainer = GISTrainer(model_args, data_args, lora_args, training_args)
    
    # 执行训练流程
    trainer.load_tokenizer()
    trainer.load_model()
    trainer.prepare_datasets()
    trainer.train()


if __name__ == "__main__":
    main()
