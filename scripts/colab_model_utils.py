"""
Google Colab 模型保存与加载 - 防崩溃版
适用于训练后保存到Google Drive，以及从Drive加载模型

使用方法：
1. 训练后运行 Section 1（保存）
2. 新session中运行 Section 2（加载）
"""

# =====================================================================
# Section 1: 训练后保存模型（防崩溃版）
# =====================================================================

def save_model_safely(trainer, tokenizer, output_name="codellama-gis-lora"):
    """
    安全地保存模型到Google Drive
    
    策略：本地保存 → 验证 → 复制到Drive → 等待同步 → 再次验证
    """
    import shutil
    import time
    import os
    import json
    
    LOCAL_TEMP = f"/content/model_temp/{output_name}"
    DRIVE_PATH = f"/content/drive/MyDrive/gis-models/{output_name}"
    
    print("="*70)
    print("💾 安全保存模型到Google Drive")
    print("="*70)
    
    # -------------------------------------------------------------------
    # 步骤1: 保存到本地（快速且可靠）
    # -------------------------------------------------------------------
    print("\n【步骤1/5】保存到本地临时目录...")
    os.makedirs(LOCAL_TEMP, exist_ok=True)
    
    trainer.save_model(LOCAL_TEMP)
    tokenizer.save_pretrained(LOCAL_TEMP)
    
    # 保存训练信息
    training_info = {
        "model_name": getattr(trainer.model, "name_or_path", "unknown"),
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "train_samples": len(trainer.train_dataset) if trainer.train_dataset else 0,
        "eval_samples": len(trainer.eval_dataset) if trainer.eval_dataset else 0,
    }
    with open(f"{LOCAL_TEMP}/training_info.json", 'w') as f:
        json.dump(training_info, f, indent=2)
    
    print(f"   ✅ 已保存到: {LOCAL_TEMP}")
    
    # -------------------------------------------------------------------
    # 步骤2: 验证本地文件完整性
    # -------------------------------------------------------------------
    print("\n【步骤2/5】验证文件完整性...")
    
    required_files = {
        "adapter_config.json": (0.001, 0.1),  # KB 范围
        "tokenizer_config.json": (0.001, 0.1),
        "adapter_model.safetensors": (100, 1000),  # MB 范围
        "tokenizer.model": (0.1, 10),
    }
    
    all_ok = True
    for fname, (min_mb, max_mb) in required_files.items():
        fpath = os.path.join(LOCAL_TEMP, fname)
        
        # 检查存在性
        if not os.path.exists(fpath):
            # safetensors可能保存为bin格式
            if fname == "adapter_model.safetensors":
                fpath_alt = os.path.join(LOCAL_TEMP, "adapter_model.bin")
                if os.path.exists(fpath_alt):
                    fpath = fpath_alt
                    fname = "adapter_model.bin"
                else:
                    print(f"   ❌ {fname} 不存在!")
                    all_ok = False
                    continue
            else:
                print(f"   ❌ {fname} 不存在!")
                all_ok = False
                continue
        
        # 检查大小
        size_mb = os.path.getsize(fpath) / (1024**2)
        status = "✅" if min_mb <= size_mb <= max_mb else "⚠️"
        print(f"   {status} {fname}: {size_mb:.2f} MB")
        
        if not (min_mb <= size_mb <= max_mb):
            print(f"      预期范围: {min_mb}-{max_mb} MB")
            all_ok = False
    
    if not all_ok:
        raise RuntimeError("⚠️ 文件验证失败！请检查训练过程。")
    
    print("   ✅ 所有文件验证通过！")
    
    # -------------------------------------------------------------------
    # 步骤3: 复制到Google Drive
    # -------------------------------------------------------------------
    print(f"\n【步骤3/5】复制到Google Drive...")
    print(f"   目标: {DRIVE_PATH}")
    
    os.makedirs(DRIVE_PATH, exist_ok=True)
    
    # 逐文件复制（显示进度）
    file_count = 0
    for root, dirs, files in os.walk(LOCAL_TEMP):
        for file in files:
            src = os.path.join(root, file)
            rel_path = os.path.relpath(src, LOCAL_TEMP)
            dst = os.path.join(DRIVE_PATH, rel_path)
            
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            
            size_mb = os.path.getsize(src) / (1024**2)
            print(f"   📋 {rel_path} ({size_mb:.2f} MB)")
            
            shutil.copy2(src, dst)
            file_count += 1
            
            # 验证复制
            if os.path.getsize(src) != os.path.getsize(dst):
                raise RuntimeError(f"❌ 复制失败: {rel_path}")
    
    print(f"   ✅ 已复制 {file_count} 个文件")
    
    # -------------------------------------------------------------------
    # 步骤4: 等待Google Drive同步
    # -------------------------------------------------------------------
    print("\n【步骤4/5】等待Google Drive同步...")
    sync_time = 30
    for i in range(sync_time):
        time.sleep(1)
        if (i + 1) % 10 == 0:
            print(f"   ⏱️  已等待 {i+1}/{sync_time} 秒...")
    print("   ✅ 同步等待完成")
    
    # -------------------------------------------------------------------
    # 步骤5: 验证Drive中的文件
    # -------------------------------------------------------------------
    print("\n【步骤5/5】验证Google Drive中的文件...")
    
    drive_ok = True
    for fname in required_files.keys():
        fpath = os.path.join(DRIVE_PATH, fname)
        
        # 处理safetensors/bin两种格式
        if fname == "adapter_model.safetensors":
            if not os.path.exists(fpath):
                fpath = os.path.join(DRIVE_PATH, "adapter_model.bin")
                fname = "adapter_model.bin"
        
        if os.path.exists(fpath):
            size_mb = os.path.getsize(fpath) / (1024**2)
            print(f"   ✅ {fname}: {size_mb:.2f} MB")
        else:
            print(f"   ❌ {fname} 在Drive中缺失!")
            drive_ok = False
    
    if not drive_ok:
        print("\n⚠️  警告: Drive中某些文件缺失，可能需要重新保存")
    
    # -------------------------------------------------------------------
    # 完成
    # -------------------------------------------------------------------
    print("\n" + "="*70)
    print("🎉 模型保存完成！")
    print("="*70)
    print(f"📂 本地副本: {LOCAL_TEMP}")
    print(f"☁️  Drive路径: {DRIVE_PATH}")
    print(f"\n💡 建议:")
    print(f"   1. 从Google Drive网页界面确认文件已上传")
    print(f"   2. 可以安全地断开Colab会话")
    print(f"   3. 使用下面的 load_model_safely() 函数加载模型")
    print("="*70)
    
    return LOCAL_TEMP, DRIVE_PATH


# =====================================================================
# Section 2: 从Google Drive加载模型（防崩溃版）
# =====================================================================

def load_model_safely(
    lora_model_name="codellama-gis-lora",
    base_model_name="codellama/CodeLlama-7b-Instruct-hf",
    use_local_cache=True
):
    """
    安全地从Google Drive加载模型
    
    策略：Drive → 本地缓存 → 清理内存 → 分步加载
    
    Args:
        lora_model_name: LoRA模型名称（在Drive中的文件夹名）
        base_model_name: 基础模型名称或路径
        use_local_cache: 是否先复制到本地缓存（强烈推荐）
    
    Returns:
        model, tokenizer
    """
    import gc
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel
    import shutil
    import time
    from pathlib import Path
    
    DRIVE_PATH = f"/content/drive/MyDrive/gis-models/{lora_model_name}"
    LOCAL_CACHE = f"/content/model_cache/{lora_model_name}"
    
    print("="*70)
    print("🔧 从Google Drive加载模型（防崩溃版）")
    print("="*70)
    print(f"📦 基础模型: {base_model_name}")
    print(f"🔗 LoRA权重: {lora_model_name}")
    print("="*70)
    
    # -------------------------------------------------------------------
    # 预处理: 清理内存
    # -------------------------------------------------------------------
    print("\n【预处理】清理内存...")
    for _ in range(3):
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"   GPU内存: {allocated:.2f}GB / {total:.2f}GB")
        print(f"   可用: {total - allocated:.2f}GB")
        
        if total - allocated < 5:
            print("   ⚠️  警告: 可用显存不足5GB，加载可能失败")
    
    # -------------------------------------------------------------------
    # 步骤1: 准备LoRA权重路径
    # -------------------------------------------------------------------
    if use_local_cache:
        print(f"\n【步骤1/4】复制到本地缓存...")
        print(f"   这将避免Google Drive的I/O瓶颈")
        
        if not Path(DRIVE_PATH).exists():
            raise FileNotFoundError(f"❌ Drive路径不存在: {DRIVE_PATH}")
        
        if Path(LOCAL_CACHE).exists():
            print(f"   ✅ 本地缓存已存在: {LOCAL_CACHE}")
        else:
            print(f"   📋 正在复制...")
            shutil.copytree(DRIVE_PATH, LOCAL_CACHE)
            time.sleep(3)  # 给文件系统一些时间
            print(f"   ✅ 已复制到: {LOCAL_CACHE}")
        
        lora_path = LOCAL_CACHE
    else:
        print(f"\n【步骤1/4】使用Drive路径（可能较慢）...")
        lora_path = DRIVE_PATH
    
    # -------------------------------------------------------------------
    # 步骤2: 加载Tokenizer
    # -------------------------------------------------------------------
    print(f"\n【步骤2/4】加载Tokenizer...")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            lora_path,
            padding_side="right",
            local_files_only=True,
            trust_remote_code=True,
        )
        
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        print(f"   ✅ Tokenizer加载完成")
        print(f"   词表大小: {len(tokenizer)}")
    except Exception as e:
        print(f"   ❌ Tokenizer加载失败: {e}")
        print(f"   💡 尝试从基础模型加载...")
        
        tokenizer = AutoTokenizer.from_pretrained(
            base_model_name,
            padding_side="right",
            trust_remote_code=True,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        print(f"   ✅ 从基础模型加载成功")
    
    # 清理
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # -------------------------------------------------------------------
    # 步骤3: 加载基础模型
    # -------------------------------------------------------------------
    print(f"\n【步骤3/4】加载基础模型...")
    print(f"   模型: {base_model_name}")
    
    try:
        # 尝试使用int8量化（节省显存）
        from transformers import BitsAndBytesConfig
        
        bnb_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0,
        )
        
        print(f"   🔄 使用int8量化加载...")
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            quantization_config=bnb_config,
            device_map="auto",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            max_memory={0: "12GB", "cpu": "30GB"},
        )
        print(f"   ✅ 基础模型加载完成 (int8)")
    
    except Exception as e:
        print(f"   ⚠️  int8量化失败: {str(e)[:80]}...")
        print(f"   📌 使用标准精度加载...")
        
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        print(f"   ✅ 基础模型加载完成 (float16)")
    
    base_model.config.use_cache = False
    
    # 清理
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # -------------------------------------------------------------------
    # 步骤4: 加载LoRA权重
    # -------------------------------------------------------------------
    print(f"\n【步骤4/4】加载LoRA权重...")
    print(f"   路径: {lora_path}")
    
    try:
        model = PeftModel.from_pretrained(
            base_model,
            lora_path,
            is_trainable=False,
            local_files_only=True,
        )
        
        # 移到GPU（如果可用）
        if torch.cuda.is_available():
            model = model.to("cuda")
        
        model.eval()
        print(f"   ✅ LoRA权重加载完成")
    
    except Exception as e:
        print(f"   ❌ LoRA权重加载失败: {e}")
        print(f"\n💡 检查清单:")
        print(f"   1. adapter_config.json 存在? {Path(lora_path) / 'adapter_config.json' exists()}")
        print(f"   2. adapter_model.safetensors 存在? {(Path(lora_path) / 'adapter_model.safetensors').exists()}")
        print(f"   3. 路径正确? {lora_path}")
        raise
    
    # 最终清理
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # -------------------------------------------------------------------
    # 完成
    # -------------------------------------------------------------------
    print("\n" + "="*70)
    print("🎉 模型加载完成！")
    print("="*70)
    
    # 显示模型信息
    total_params = sum(p.numel() for p in model.parameters())
    print(f"📊 模型参数: {total_params / 1e6:.1f}M")
    
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        print(f"💾 GPU内存占用: {allocated:.2f}GB")
    
    print("="*70)
    print("✅ 可以开始推理了！")
    
    return model, tokenizer


# =====================================================================
# 使用示例
# =====================================================================

if __name__ == "__main__":
    # ---------------------------------------------------------------
    # 示例1: 训练后保存（在训练notebook中使用）
    # ---------------------------------------------------------------
    """
    # 假设你已经训练完成，有 trainer 和 tokenizer
    local_path, drive_path = save_model_safely(
        trainer=trainer,
        tokenizer=tokenizer,
        output_name="codellama-gis-lora"
    )
    """
    
    # ---------------------------------------------------------------
    # 示例2: 新session中加载（在推理notebook中使用）
    # ---------------------------------------------------------------
    """
    # 方法A: 使用本地缓存（推荐）
    model, tokenizer = load_model_safely(
        lora_model_name="codellama-gis-lora",
        base_model_name="codellama/CodeLlama-7b-Instruct-hf",
        use_local_cache=True  # 推荐！
    )
    
    # 方法B: 直接从Drive加载（不推荐，可能较慢）
    model, tokenizer = load_model_safely(
        lora_model_name="codellama-gis-lora",
        base_model_name="codellama/CodeLlama-7b-Instruct-hf",
        use_local_cache=False
    )
    
    # 测试推理
    test_prompt = "Create a new cable object"
    inputs = tokenizer(test_prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=256)
    
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"\\n生成结果:\\n{result}")
    """
    
    pass
