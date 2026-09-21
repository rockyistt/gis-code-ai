#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
step_llm_predictor.py - Standalone step-level model predictor.

Wraps CodeLlama-7B + LoRA adapter for local CPU/GPU inference.
Can predict GIS JSON steps from natural language instructions.

No VS Code dependencies. Can be imported by scaffolder.py or other modules.
"""

import os
import sys
import json
import torch
import warnings
from pathlib import Path
from typing import Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

warnings.filterwarnings("ignore")

try:
    import bitsandbytes as bnb
    HAS_BNB = True
except ImportError:
    HAS_BNB = False


class StepLevelPredictor:
    """
    Predict GIS workflow steps from natural language instructions
    using a fine-tuned CodeLlama-7B + LoRA model.
    
    Usage:
        predictor = StepLevelPredictor(model_dir="models/step-level-model-865")
        step_data = predictor.predict_step("Create E MS Installatie FP")
        print(step_data)
    """
    
    SYSTEM_PROMPT = (
        "You are a GIS step instruction parser. "
        "Given a natural language instruction, output a JSON object "
        "describing the corresponding GIS step."
    )
    
    def __init__(
        self, 
        model_dir: str = "models/step-level-model-865",
        base_model_name: str = "codellama/CodeLlama-7b-Instruct-hf",
        use_gpu: bool = True,
        dtype: Optional[str] = None,
        quantization: Optional[str] = None,
        max_memory_gb: int = 8,
        verbose: bool = True
    ):
        """
        Initialize the predictor by loading the model and tokenizer.
        
        Args:
            model_dir: Path to the LoRA adapter directory
            base_model_name: HuggingFace model ID for the base model
            use_gpu: Whether to attempt using GPU (auto-detected if not specified)
            dtype: Override dtype ('float32', 'float16', 'int8'). Auto-detect if None.
            quantization: Quantization method ('int4', 'int8', or None for FP32)
            max_memory_gb: Max memory per GPU to allocate
            verbose: Print loading status
        """
        self.model_dir = Path(model_dir)
        self.base_model_name = base_model_name
        self.model = None
        self.tokenizer = None
        self.device = None
        self.dtype = None
        self.verbose = verbose
        self.quantization = quantization
        
        # Auto-detect GPU availability
        gpu_available = torch.cuda.is_available()
        self.use_gpu = use_gpu and gpu_available
        
        if self.verbose:
            print("[INFO] StepLevelPredictor Initialization")
            print("=" * 70)
            print(f"  Model directory: {self.model_dir}")
            print(f"  GPU available:   {gpu_available}")
            print(f"  Using GPU:       {self.use_gpu}")
            print(f"  Quantization:    {quantization if quantization else 'None (FP32)'}")
        
        # Determine dtype
        if dtype is None:
            self.dtype = torch.float16 if self.use_gpu else torch.float32
        else:
            dtype_map = {
                'float32': torch.float32,
                'float16': torch.float16,
                'int8': torch.int8
            }
            self.dtype = dtype_map.get(dtype, torch.float32)
        
        if self.verbose:
            print(f"  Data type:       {self.dtype}")
            print("=" * 70)
        
        self._load_model()
    
    def _load_model(self):
        """Load tokenizer and model with optional quantization."""
        try:
            # Step 1: Load tokenizer (from adapter or base)
            if self.verbose:
                print("[INFO] Loading tokenizer...")
            
            if self.model_dir.exists():
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
                    if self.verbose:
                        print(f"[OK]   Tokenizer loaded from {self.model_dir}")
                except:
                    self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_name)
                    if self.verbose:
                        print(f"[OK]   Tokenizer loaded from base model: {self.base_model_name}")
            else:
                raise FileNotFoundError(f"Model directory not found: {self.model_dir}")
            
            # Ensure pad token is set
            if self.tokenizer.pad_token_id is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Step 2: Setup quantization if requested
            quantization_config = None
            if self.quantization:
                if self.verbose:
                    print(f"[INFO] Setting up {self.quantization.upper()} quantization...")
                
                if not HAS_BNB:
                    if self.verbose:
                        print("[WARN] bitsandbytes not installed. Installing...")
                    import subprocess
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "bitsandbytes"])
                
                if self.quantization == "int4":
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=self.dtype,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4"
                    )
                    if self.verbose:
                        print("[OK]   INT4 quantization configured (model will be ~3-4GB)")
                        
                elif self.quantization == "int8":
                    quantization_config = BitsAndBytesConfig(
                        load_in_8bit=True,
                        llm_int8_threshold=6.0,
                        llm_int8_enable_fp32_cpu_offload=True  # 关键：允许 CPU 推理
                    )
                    if self.verbose:
                        print("[OK]   INT8 quantization configured (model will be ~6-8GB)")
            
            device_map = "auto" if (self.use_gpu or self.quantization) else "cpu"
            
            # Step 3: Detect model type and load accordingly
            model_safetensors = self.model_dir / "model.safetensors"
            pytorch_model_bin = self.model_dir / "pytorch_model.bin"
            adapter_config = self.model_dir / "adapter_config.json"
            adapter_model = self.model_dir / "adapter_model.bin"
            
            # Scheme 1: Complete merged model (model.safetensors or pytorch_model.bin)
            if model_safetensors.exists() or pytorch_model_bin.exists():
                if self.verbose:
                    print("[INFO] Detected Scheme 1: Complete merged model")
                    print(f"[INFO] Loading from {model_safetensors if model_safetensors.exists() else pytorch_model_bin}...")
                
                try:
                    if quantization_config:
                        self.model = AutoModelForCausalLM.from_pretrained(
                            str(self.model_dir),
                            device_map=device_map,
                            quantization_config=quantization_config,
                            low_cpu_mem_usage=True,
                            trust_remote_code=True
                        )
                    else:
                        self.model = AutoModelForCausalLM.from_pretrained(
                            str(self.model_dir),
                            device_map=device_map,
                            torch_dtype=self.dtype,
                            low_cpu_mem_usage=True,
                            trust_remote_code=True
                        )
                    if self.verbose:
                        print(f"[OK]   Complete model loaded on device: {device_map}")
                    
                except Exception as e:
                    if self.verbose:
                        print(f"[WARN] Scheme 1 failed ({str(e)[:100]}), falling back to Scheme 2...")
                    raise
            
            # Scheme 2: LoRA adapter (adapter_config.json + adapter_model.bin)
            elif adapter_config.exists() and adapter_model.exists():
                if self.verbose:
                    print("[INFO] Detected Scheme 2: LoRA adapter")
                    print(f"[INFO] Loading base model: {self.base_model_name}...")
                
                if quantization_config:
                    base_model = AutoModelForCausalLM.from_pretrained(
                        self.base_model_name,
                        device_map=device_map,
                        quantization_config=quantization_config,
                        low_cpu_mem_usage=True,
                        trust_remote_code=True
                    )
                else:
                    base_model = AutoModelForCausalLM.from_pretrained(
                        self.base_model_name,
                        device_map=device_map,
                        torch_dtype=self.dtype,
                        low_cpu_mem_usage=True,
                        trust_remote_code=True
                    )
                if self.verbose:
                    print(f"[OK]   Base model loaded on device: {device_map}")
                
                if self.verbose:
                    print(f"[INFO] Loading LoRA adapter from {self.model_dir}...")
                
                self.model = PeftModel.from_pretrained(
                    base_model,
                    str(self.model_dir),
                    device_map=device_map,
                    is_trainable=False
                )
                if self.verbose:
                    print(f"[OK]   LoRA adapter loaded")
            
            else:
                raise FileNotFoundError(
                    f"Could not detect model type. Missing:\n"
                    f"  Scheme 1: model.safetensors or pytorch_model.bin\n"
                    f"  Scheme 2: adapter_config.json + adapter_model.bin"
                )
            
            # Set to eval mode
            self.model.eval()
            
            # Determine device
            if hasattr(self.model, 'device'):
                self.device = self.model.device
            elif self.use_gpu and torch.cuda.is_available():
                self.device = torch.device('cuda:0')
            else:
                self.device = torch.device('cpu')
            
            if self.verbose:
                print(f"[OK]   Model is on device: {self.device}")
                if self.quantization:
                    print(f"[OK]   Memory usage: ~{self._estimate_memory_usage():.1f} GB")
                print("[OK]   Model ready for inference!")
                print("=" * 70)
        
        except Exception as e:
            print(f"[ERROR] Failed to load model: {e}")
            raise
    
    def _estimate_memory_usage(self):
        """估计模型内存使用"""
        if not self.model:
            return 0
        
        total_params = sum(p.numel() for p in self.model.parameters())
        
        if self.quantization == "int4":
            return (total_params * 0.25) / (1024**3)  # 0.25 bytes per param
        elif self.quantization == "int8":
            return (total_params * 1.0) / (1024**3)   # 1 byte per param
        else:
            if self.dtype == torch.float32:
                return (total_params * 4.0) / (1024**3)  # 4 bytes per param
            elif self.dtype == torch.float16:
                return (total_params * 2.0) / (1024**3)  # 2 bytes per param
        
        return 0
    
    def predict_step(
        self,
        instruction: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Predict a GIS step JSON from a natural language instruction.
        
        Args:
            instruction: Natural language instruction (e.g., "Create E MS Installatie FP")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)
            top_p: Nucleus sampling parameter
        
        Returns:
            Parsed JSON dict if successful, None otherwise
        """
        if self.model is None or self.tokenizer is None:
            print("[ERROR] Model not loaded. Call _load_model() first.")
            return None
        
        try:
            # Format the prompt
            prompt = self._format_prompt(instruction)
            
            # Tokenize
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
                padding=True,
                return_attention_mask=True
            )
            
            # Move to model device
            input_ids = inputs["input_ids"].to(self.device)
            attention_mask = inputs["attention_mask"].to(self.device)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=max_tokens,
                    do_sample=(temperature > 0.0),
                    temperature=temperature if temperature > 0.0 else 1.0,
                    top_p=top_p,
                    num_beams=1,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            # Decode only the generated part (exclude input)
            generated_ids = outputs[0][len(input_ids[0]):]
            generated_text = self.tokenizer.decode(
                generated_ids,
                skip_special_tokens=False
            )
            
            # Extract and parse JSON
            json_dict = self._extract_json(generated_text)
            return json_dict
        
        except Exception as e:
            print(f"[ERROR] Prediction failed: {e}")
            return None
    
    @staticmethod
    def _format_prompt(instruction: str) -> str:
        """Format the input instruction into the model's expected prompt format."""
        system_msg = StepLevelPredictor.SYSTEM_PROMPT
        return (
            f"### System:\n{system_msg}\n\n"
            f"### Instruction:\n{instruction}\n\n"
            f"### Response:\n"
        )
    
    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Extract and parse the first complete JSON object from generated text.
        
        Handles cases where the model generates extra text or multiple objects.
        """
        text = text.strip()
        
        # Find the first opening brace
        first_brace_idx = text.find('{')
        if first_brace_idx == -1:
            return None
        
        text = text[first_brace_idx:]
        
        # Find end markers to cut off extraneous generation
        end_markers = [
            "\n\n### Instruction:",
            "\n\n###",
            "---",
            "<|endoftext|>",
            "</s>"
        ]
        effective_end_idx = len(text)
        
        for marker in end_markers:
            idx = text.find(marker)
            if idx != -1 and idx < effective_end_idx:
                effective_end_idx = idx
        
        text = text[:effective_end_idx].strip()
        
        # Find the first complete JSON object (balanced braces)
        balance = 0
        last_valid_idx = -1
        
        for i, char in enumerate(text):
            if char == '{':
                balance += 1
            elif char == '}':
                balance -= 1
                if balance == 0:
                    last_valid_idx = i
                    break  # Stop at first complete JSON
        
        if last_valid_idx != -1:
            json_str = text[:last_valid_idx + 1]
        else:
            # Fallback: use the last closing brace
            last_brace_idx = text.rfind('}')
            if last_brace_idx != -1:
                json_str = text[:last_brace_idx + 1]
            else:
                json_str = text
        
        # Try to parse
        try:
            parsed = json.loads(json_str)
            return parsed
        except json.JSONDecodeError:
            return None


# For testing only
if __name__ == "__main__":
    predictor = StepLevelPredictor(
        model_dir="models/step-level-model-865",
        verbose=True
    )
    
    test_instructions = [
        "Create E MS Installatie FP",
        "Update the just-created object",
        "Delete E MS Rail FP"
    ]
    
    for instr in test_instructions:
        print(f"\n📝 Instruction: {instr}")
        result = predictor.predict_step(instr)
        if result:
            print(f"✅ Result:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            print("❌ Prediction failed")
