#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hybrid_inference.py — 混合推理系统（RAG + 微调模型）

这个模块提供了一个统一的推理接口，优先使用 RAG 检索相似的指令，
如果相似度低于阈值，则使用微调的模型进行预测。

使用示例:
    from src.inference.hybrid_inference import HybridInferencer
    
    inferencer = HybridInferencer(
        model_path="/path/to/model",
        rag_index_path="/path/to/rag/index"
    )
    
    result = inferencer.infer(
        instruction="Open E MS Installatie of station 6 002 005",
        rag_threshold=0.8
    )
    
    print(result)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import sys

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class HybridInferencer:
    """
    混合推理引擎：RAG + 微调模型
    
    流程:
      1. 用户输入指令
      2. 在 RAG 中检索相似指令
      3. 如果相似度 >= rag_threshold，返回 RAG 结果
      4. 否则使用模型进行推理
    """
    
    SYSTEM_MSG = (
        "You are a GIS step instruction parser. "
        "Given a natural language instruction, output a JSON object "
        "describing the corresponding GIS step."
    )
    
    def __init__(
        self,
        model_path: str,
        rag_index_path: Optional[str] = None,
        use_rag: bool = True,
        device: str = "auto",
        torch_dtype = None,
    ):
        """
        初始化混合推理引擎
        
        Args:
            model_path: 微调模型的路径（包含 adapter_config.json 或 model.safetensors）
            rag_index_path: RAG 索引的路径（包含 embeddings.npy 和 metadata.jsonl）
            use_rag: 是否使用 RAG
            device: PyTorch 设备（"auto", "cuda", "cpu"）
            torch_dtype: 模型数据类型（默认 torch.float16）
        """
        self.model_path = Path(model_path)
        self.rag_index_path = Path(rag_index_path) if rag_index_path else None
        self.use_rag = use_rag
        self.device = device
        self.torch_dtype = torch_dtype or torch.float16
        
        # 模型和 tokenizer
        self.model = None
        self.tokenizer = None
        self.base_model_name = None
        
        # RAG 索引
        self.rag = None
        self.rag_available = False
        
        # 加载模型
        self._load_model()
        
        # 加载 RAG（如果可用）
        if self.use_rag:
            self._load_rag()
    
    def _load_model(self):
        """加载微调模型"""
        logger.info(f"加载模型: {self.model_path}")
        
        # 获取基础模型名称
        training_info_path = self.model_path / "training_info.json"
        if training_info_path.exists():
            with open(training_info_path, "r", encoding="utf-8") as f:
                training_info = json.load(f)
                self.base_model_name = training_info.get("model_name", "codellama/CodeLlama-7b-Instruct-hf")
        else:
            self.base_model_name = "codellama/CodeLlama-7b-Instruct-hf"
        
        logger.info(f"基础模型: {self.base_model_name}")
        
        try:
            # 尝试加载 tokenizer
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
                logger.info("✅ 从本地路径加载 Tokenizer")
            except:
                self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_name)
                logger.info("✅ 从基础模型加载 Tokenizer")
            
            # 设置 pad token
            if self.tokenizer.pad_token_id is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 尝试加载模型
            model_safetensors = self.model_path / "model.safetensors"
            adapter_config = self.model_path / "adapter_config.json"
            
            if model_safetensors.exists() and not adapter_config.exists():
                # 直接加载为完整模型
                logger.info("加载完整合并的模型...")
                self.model = AutoModelForCausalLM.from_pretrained(
                    str(self.model_path),
                    device_map=self.device,
                    torch_dtype=self.torch_dtype,
                    low_cpu_mem_usage=True
                )
            else:
                # LoRA 加载
                logger.info("加载基础模型进行 LoRA...")
                base_model = AutoModelForCausalLM.from_pretrained(
                    self.base_model_name,
                    device_map=self.device,
                    torch_dtype=self.torch_dtype,
                    low_cpu_mem_usage=True
                )
                
                if adapter_config.exists():
                    self.model = PeftModel.from_pretrained(
                        base_model,
                        str(self.model_path),
                        device_map=self.device,
                        torch_dtype=self.torch_dtype
                    )
                    logger.info("✅ LoRA 适配器已加载")
                else:
                    logger.warning("未找到 adapter 配置，使用基础模型")
                    self.model = base_model
            
            self.model.eval()
            logger.info("✅ 模型加载完成，已设置为评估模式")
        
        except Exception as e:
            logger.error(f"❌ 模型加载失败: {e}")
            raise
    
    def _load_rag(self):
        """加载 RAG 索引"""
        if not self.rag_index_path:
            logger.warning("⚠️ RAG 索引路径未指定")
            return
        
        try:
            # 动态导入 RAG 模块
            from scripts.rag_utils import StepRAG
            
            self.rag = StepRAG()
            self.rag.load()
            self.rag_available = True
            logger.info(f"✅ RAG 索引已加载: {len(self.rag.metadata)} 条记录")
        except Exception as e:
            logger.warning(f"⚠️ RAG 加载失败: {e}")
            logger.warning("   将仅使用模型进行推理")
            self.rag = None
            self.rag_available = False
    
    def _format_prompt(self, instruction: str) -> str:
        """格式化推理提示词"""
        return (
            f"### System:\n{self.SYSTEM_MSG}\n\n"
            f"### Instruction:\n{instruction}\n\n"
            f"### Response:\n"
        )
    
    def _infer_model(self, instruction: str, max_tokens: int = 1024) -> str:
        """使用模型进行推理"""
        prompt = self._format_prompt(instruction)
        
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
            padding=True,
            return_attention_mask=True
        )
        
        input_ids = inputs["input_ids"].to(self.model.device)
        attention_mask = inputs["attention_mask"].to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_tokens,
                do_sample=False,
                num_beams=1,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        
        # 解码生成的部分
        generated_text = self.tokenizer.decode(
            outputs[0][len(inputs["input_ids"][0]):],
            skip_special_tokens=False
        )
        
        # 提取 JSON 部分
        json_str = self._extract_json(generated_text)
        return json_str
    
    @staticmethod
    def _extract_json(text: str) -> str:
        """从生成的文本中提取 JSON"""
        text = text.strip()
        
        # 查找第一个 {
        first_brace = text.find('{')
        if first_brace == -1:
            return text
        
        text = text[first_brace:]
        
        # 找到匹配的 }
        balance = 0
        last_valid_idx = -1
        
        for i, char in enumerate(text):
            if char == '{':
                balance += 1
            elif char == '}':
                balance -= 1
            
            if balance == 0 and char == '}':
                last_valid_idx = i
                break
        
        if last_valid_idx != -1:
            return text[:last_valid_idx + 1]
        
        return text
    
    def infer(
        self,
        instruction: str,
        rag_threshold: float = 0.8,
        top_k: int = 1,
        max_tokens: int = 1024,
        return_details: bool = True,
    ) -> Dict[str, Any]:
        """
        执行混合推理
        
        Args:
            instruction: 用户输入的自然语言指令
            rag_threshold: RAG 相似度阈值（0-1）
            top_k: 检索 RAG 时返回的结果数
            max_tokens: 模型生成的最大 token 数
            return_details: 是否返回详细信息
        
        Returns:
            dict with keys:
                - source: "rag" 或 "model"
                - result: 推理结果（JSON 字符串或字典）
                - confidence: 置信度分数
                - rag_score: RAG 相似度（如果使用了 RAG）
                - rag_details: RAG 检索的详细信息
                - explanation: 处理过程说明
        """
        result = {
            "instruction": instruction,
            "source": None,
            "result": None,
            "confidence": None,
            "rag_score": None,
            "rag_details": None,
            "explanation": ""
        }
        
        # 第一步：尝试 RAG 检索
        if self.use_rag and self.rag_available:
            try:
                rag_results = self.rag.retrieve(instruction, top_k=top_k)
                
                if rag_results:
                    best_result = rag_results[0]
                    best_score = best_result["score"]
                    
                    result["rag_score"] = float(best_score)
                    result["explanation"] = f"RAG 检索 (相似度: {best_score:.4f})"
                    
                    if return_details:
                        result["rag_details"] = {
                            "top_k": len(rag_results),
                            "best_score": float(best_score),
                            "best_instruction": best_result.get("instruction", ""),
                        }
                    
                    # 检查是否超过阈值
                    if best_score >= rag_threshold:
                        result["source"] = "rag"
                        result["confidence"] = float(best_score)
                        
                        # 构建 RAG 结果
                        rag_output = {
                            "module": best_result.get("module", ""),
                            "method": best_result.get("method", ""),
                            "object": best_result.get("object", ""),
                            "database": best_result.get("database", ""),
                            "command": best_result.get("command", ""),
                            "object_id": best_result.get("object_id", ""),
                        }
                        
                        result["result"] = rag_output
                        result["explanation"] += f" → 超过阈值 {rag_threshold}，返回 RAG 结果"
                        
                        return result
                    else:
                        result["explanation"] += f" → 未超过阈值 {rag_threshold}，使用模型推理"
            
            except Exception as e:
                logger.warning(f"⚠️ RAG 检索失败: {e}")
                result["explanation"] = f"RAG 检索失败: {str(e)[:100]}"
        
        # 第二步：使用模型推理
        try:
            model_output = self._infer_model(instruction, max_tokens=max_tokens)
            result["source"] = "model"
            result["confidence"] = 1.0
            
            # 尝试解析为 JSON
            try:
                result["result"] = json.loads(model_output)
            except:
                result["result"] = model_output
            
            if result["explanation"]:
                result["explanation"] += " → 模型推理完成"
            else:
                result["explanation"] = "模型推理"
            
            return result
        
        except Exception as e:
            logger.error(f"❌ 模型推理失败: {e}")
            result["source"] = "error"
            result["result"] = str(e)
            result["explanation"] += f" → 模型推理失败"
            
            return result
    
    def batch_infer(
        self,
        instructions: list,
        rag_threshold: float = 0.8,
        return_details: bool = False,
    ) -> list:
        """
        批量推理
        
        Args:
            instructions: 指令列表
            rag_threshold: RAG 相似度阈值
            return_details: 是否返回详细信息
        
        Returns:
            推理结果列表
        """
        results = []
        for instruction in instructions:
            result = self.infer(
                instruction,
                rag_threshold=rag_threshold,
                return_details=return_details
            )
            results.append(result)
        
        return results


# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    # 配置
    MODEL_PATH = "/path/to/model"
    RAG_INDEX_PATH = "/path/to/rag/index"
    
    # 初始化推理引擎
    inferencer = HybridInferencer(
        model_path=MODEL_PATH,
        rag_index_path=RAG_INDEX_PATH,
        use_rag=True
    )
    
    # 测试指令
    test_instructions = [
        "Open E MS Installatie of station 6 002 005",
        "Create a new high voltage cable",
        "Switch to geographical context view",
    ]
    
    # 执行推理
    print("="*70)
    print("🚀 混合推理系统测试")
    print("="*70)
    
    for instruction in test_instructions:
        print(f"\n📝 指令: {instruction}")
        
        result = inferencer.infer(
            instruction,
            rag_threshold=0.8,
            return_details=True
        )
        
        print(f"来源: {result['source'].upper()}")
        print(f"置信度: {result['confidence']:.4f}")
        print(f"说明: {result['explanation']}")
        
        if isinstance(result["result"], dict):
            print("结果:")
            print(json.dumps(result["result"], indent=2, ensure_ascii=False))
        else:
            print(f"结果: {result['result']}")
