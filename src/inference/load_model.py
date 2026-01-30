"""
模型加载和推理模块 - 支持从Google Drive加载微调的CodeLlama模型
"""

import os
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from typing import Dict, Optional, Tuple


class GISCodeGenerator:
    """GIS代码生成器 - 使用CodeLlama + LoRA微调模型"""
    
    def __init__(
        self,
        model_path: str,
        base_model: str = "codellama/CodeLlama-7b-Instruct-hf",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        use_fp16: bool = True
    ):
        """
        初始化模型
        
        Args:
            model_path: LoRA模型路径 (包含adapter_config.json的目录)
            base_model: 基础模型名称
            device: 计算设备 ("cuda" 或 "cpu")
            use_fp16: 是否使用FP16
        """
        self.device = device
        self.use_fp16 = use_fp16
        
        print(f"🔧 设置推理环境...")
        print(f"  设备: {device}")
        print(f"  FP16: {use_fp16}")
        
        # 检查模型路径
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"模型路径不存在: {model_path}")
        
        if not (model_path / "adapter_config.json").exists():
            raise FileNotFoundError(f"找不到adapter_config.json: {model_path}")
        
        print(f"\n📖 加载Tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            padding_side="right"
        )
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        print(f"✅ Tokenizer加载完成 (vocab_size={len(self.tokenizer)})")
        
        print(f"\n🤖 加载基础模型: {base_model}")
        dtype = torch.float16 if use_fp16 else torch.float32
        
        base_model_obj = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=dtype,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
        
        base_model_obj.config.use_cache = False
        print(f"✅ 基础模型加载完成")
        
        print(f"\n🔧 加载LoRA权重...")
        self.model = PeftModel.from_pretrained(
            base_model_obj,
            str(model_path),
            torch_dtype=dtype,
            device_map="auto",
        )
        
        self.model.eval()
        print(f"✅ LoRA权重加载完成")
        
        # 打印参数信息
        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self.model.parameters())
        print(f"\n📊 模型参数统计:")
        print(f"  总参数: {total:,}")
        print(f"  可训练参数: {trainable:,} ({100*trainable/total:.2f}%)")
        
        print(f"\n✅ 模型初始化完成！")
    
    def generate(
        self,
        instruction: str,
        context: str = "",
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        num_return_sequences: int = 1,
    ) -> Dict[str, str]:
        """
        生成GIS代码
        
        Args:
            instruction: 用户指令
            context: 上下文信息 (可选)
            max_new_tokens: 最大生成token数
            temperature: 温度参数 (0-1)
            top_p: nucleus采样参数
            num_return_sequences: 生成序列数
        
        Returns:
            字典，包含生成的代码
        """
        
        # 构建Prompt
        if context:
            prompt = f"""You are a GIS workflow code generator. Generate complete JSON workflow code based on the instruction.

Instruction: {instruction}
Context: {context}

JSON Code:
"""
        else:
            prompt = f"""You are a GIS workflow code generator. Generate complete JSON workflow code based on the instruction.

Instruction: {instruction}

JSON Code:
"""
        
        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        # 生成
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=top_p,
                num_return_sequences=num_return_sequences,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        
        # 解码
        responses = []
        for output in outputs:
            text = self.tokenizer.decode(output, skip_special_tokens=True)
            # 提取JSON部分
            code = text.split("JSON Code:")[-1].strip()
            responses.append(code)
        
        if num_return_sequences == 1:
            return {
                "instruction": instruction,
                "context": context,
                "generated_code": responses[0]
            }
        else:
            return {
                "instruction": instruction,
                "context": context,
                "generated_codes": responses
            }


def load_model_from_drive(
    drive_path: str = "/content/drive/MyDrive/gis-models/codellama-gis-lora",
    **kwargs
) -> GISCodeGenerator:
    """
    从Google Drive加载模型 (Colab环境)
    
    Args:
        drive_path: Google Drive中的模型路径
        **kwargs: 传递给GISCodeGenerator的其他参数
    
    Returns:
        初始化的GISCodeGenerator对象
    """
    
    if not os.path.exists(drive_path):
        raise FileNotFoundError(
            f"模型路径不存在: {drive_path}\n"
            f"请确保已挂载Google Drive并且模型已保存到该路径"
        )
    
    return GISCodeGenerator(drive_path, **kwargs)


def load_model_from_local(
    local_path: str,
    **kwargs
) -> GISCodeGenerator:
    """
    从本地路径加载模型
    
    Args:
        local_path: 本地模型路径
        **kwargs: 传递给GISCodeGenerator的其他参数
    
    Returns:
        初始化的GISCodeGenerator对象
    """
    
    return GISCodeGenerator(local_path, **kwargs)


if __name__ == "__main__":
    # 测试加载模型 (需要在有GPU的环境中运行)
    import sys
    
    if len(sys.argv) > 1:
        model_path = sys.argv[1]
    else:
        model_path = "/content/drive/MyDrive/gis-models/codellama-gis-lora"
    
    print(f"加载模型: {model_path}")
    generator = load_model_from_drive(model_path)
    
    # 简单测试
    test_instruction = "Create a new MS cable object"
    test_context = "Application: PowerGrid | Database: ND | Steps: 3"
    
    print("\n" + "="*70)
    print("🧪 测试推理...")
    print("="*70)
    result = generator.generate(test_instruction, test_context)
    print(f"\n📝 指令: {result['instruction']}")
    print(f"📍 上下文: {result['context']}")
    print(f"\n💻 生成的代码:\n{result['generated_code'][:500]}...")
