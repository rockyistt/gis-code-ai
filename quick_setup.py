#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quick_setup.py - 快速设置脚本

一键设置本地推理环境，包括：
1. 环境检查
2. 依赖安装
3. 配置生成
4. 模型下载指导
5. 功能测试

使用方法:
    python quick_setup.py
"""

import sys
import os
import subprocess
import json
import platform
from pathlib import Path
from typing import Tuple

# ============================================================
# 常量
# ============================================================

PROJECT_ROOT = Path(__file__).parent.absolute()
CONFIGS_DIR = PROJECT_ROOT / "configs"
MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"

# 颜色代码
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# ============================================================
# 工具函数
# ============================================================

def print_header(title: str):
    """打印标题"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {title}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.END}\n")

def print_section(title: str):
    """打印章节"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}  📌 {title}{Colors.END}")
    print(f"{Colors.CYAN}  {'-' * 60}{Colors.END}\n")

def print_ok(msg: str):
    """打印成功消息"""
    print(f"  {Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg: str):
    """打印错误消息"""
    print(f"  {Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg: str):
    """打印警告"""
    print(f"  {Colors.YELLOW}⚠️  {msg}{Colors.END}")

def print_info(msg: str):
    """打印信息"""
    print(f"  {Colors.BLUE}ℹ️  {msg}{Colors.END}")

# ============================================================
# 检查函数
# ============================================================

def check_python_version() -> bool:
    """检查 Python 版本"""
    print_section("检查 Python 版本")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print_info(f"当前 Python: {version_str}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print_error(f"Python 版本过低，需要 3.9+ (当前: {version_str})")
        return False
    
    print_ok(f"Python 版本检查通过")
    return True

def check_cuda() -> Tuple[bool, str]:
    """检查 CUDA 支持"""
    print_section("检查 GPU 支持")
    
    try:
        import torch
        if torch.cuda.is_available():
            print_ok(f"CUDA 可用 ✓")
            print_info(f"GPU: {torch.cuda.get_device_name(0)}")
            print_info(f"CUDA Version: {torch.version.cuda}")
            print_info(f"Device Count: {torch.cuda.device_count()}")
            
            # 检查显存
            try:
                total_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
                print_info(f"显存: {total_mem:.1f} GB")
                
                if total_mem < 12:
                    print_warning("显存 < 12GB，推荐使用 float32 而非 float16")
            except:
                pass
            
            return True, "cuda"
        else:
            print_warning("CUDA 不可用，将使用 CPU (较慢)")
            return False, "cpu"
    except ImportError:
        print_warning("PyTorch 未安装，将在依赖安装后检查")
        return False, "cpu"

def check_dependencies() -> bool:
    """检查关键依赖"""
    print_section("检查依赖包")
    
    required = [
        ("torch", "PyTorch"),
        ("transformers", "Transformers"),
        ("peft", "PEFT"),
        ("numpy", "NumPy"),
        ("sentence_transformers", "Sentence Transformers"),
    ]
    
    optional = [
        ("flask", "Flask (API 需要)"),
        ("flask_cors", "Flask-CORS (API 需要)"),
    ]
    
    missing_required = []
    missing_optional = []
    
    for module, name in required:
        try:
            __import__(module)
            print_ok(f"{name}")
        except ImportError:
            print_error(f"{name}")
            missing_required.append(name)
    
    print()
    for module, name in optional:
        try:
            __import__(module)
            print_ok(f"{name}")
        except ImportError:
            print_warning(f"{name} (可选)")
            missing_optional.append(name)
    
    if missing_required:
        print_error(f"缺少必要依赖: {', '.join(missing_required)}")
        return False
    
    return True

# ============================================================
# 设置函数
# ============================================================

def setup_directories():
    """创建必要目录"""
    print_section("创建目录结构")
    
    dirs = [
        MODELS_DIR,
        MODELS_DIR / "step-level-model-865",
        CONFIGS_DIR,
        DATA_DIR,
        PROJECT_ROOT / "logs",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print_ok(f"目录: {d.relative_to(PROJECT_ROOT)}")

def setup_config():
    """生成配置文件"""
    print_section("生成配置文件")
    
    config_file = CONFIGS_DIR / "local_config.json"
    
    config = {
        "model": {
            "base_model": "codellama/CodeLlama-7b-Instruct-hf",
            "local_path": str(MODELS_DIR / "step-level-model-865"),
            "device": "cuda",
            "torch_dtype": "float16"
        },
        "rag": {
            "enabled": True,
            "index_path": str(DATA_DIR / "processed" / "rag_index"),
            "threshold": 0.8
        },
        "inference": {
            "max_tokens": 1024,
            "temperature": 0.7,
            "top_p": 0.95
        },
        "api": {
            "host": "0.0.0.0",
            "port": 5000,
            "debug": False
        }
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print_ok(f"配置文件: {config_file}")

# ============================================================
# 安装和测试
# ============================================================

def install_dependencies():
    """安装依赖"""
    print_section("安装依赖包")
    
    requirements_file = PROJECT_ROOT / "requirements.txt"
    
    if not requirements_file.exists():
        print_error("requirements.txt 未找到")
        return False
    
    try:
        print_info("安装中 (这可能需要几分钟)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            check=True,
            capture_output=True
        )
        print_ok("依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"依赖安装失败: {e}")
        return False

def test_inference():
    """测试推理"""
    print_section("测试推理引擎")
    
    try:
        print_info("初始化推理引擎...")
        from src.inference import HybridInferencer
        
        # 检查模型是否存在
        model_path = MODELS_DIR / "step-level-model-865"
        if not list(model_path.glob("adapter_*")) and not list(model_path.glob("model.*")):
            print_warning("模型文件不存在，跳过推理测试")
            print_info("请从 Google Drive 或其他云存储下载模型到:")
            print_info(f"  {model_path}")
            return False
        
        inferencer = HybridInferencer(
            model_path=str(model_path),
            rag_index_path=str(DATA_DIR / "processed" / "rag_index"),
            use_rag=True
        )
        
        print_info("执行测试推理...")
        result = inferencer.infer("Open the editor", rag_threshold=0.8)
        
        print_ok(f"推理成功 ✓")
        print_info(f"来源: {result['source']}")
        print_info(f"置信度: {result['confidence']:.4f}")
        
        return True
    
    except FileNotFoundError as e:
        print_warning(f"模型文件未找到: {e}")
        return False
    except Exception as e:
        print_error(f"测试失败: {e}")
        return False

def show_next_steps():
    """显示后续步骤"""
    print_section("后续步骤")
    
    print_info("1️⃣  下载已训练的模型")
    print_info(f"   位置: {MODELS_DIR}/step-level-model-865/")
    print_info("")
    
    print_info("2️⃣  运行推理测试")
    print_info("   python local_inference.py --instruction \"Open the editor\"")
    print_info("")
    
    print_info("3️⃣  启动 API 服务 (可选)")
    print_info("   python api_server.py")
    print_info("")
    
    print_info("4️⃣  查看完整文档")
    print_info("   cat docs/LOCAL_DEPLOYMENT.md")
    print_info("")

def show_system_info():
    """显示系统信息"""
    print_section("系统信息")
    
    print_info(f"操作系统: {platform.system()} {platform.release()}")
    print_info(f"Python: {sys.version.split()[0]}")
    print_info(f"项目位置: {PROJECT_ROOT}")
    
    try:
        import torch
        print_info(f"PyTorch: {torch.__version__}")
        if torch.cuda.is_available():
            print_info(f"CUDA 可用: 是")
        else:
            print_info(f"CUDA 可用: 否")
    except:
        pass

# ============================================================
# 主函数
# ============================================================

def main():
    print_header("🚀 GIS 模型快速设置")
    
    # 第 1 步: 系统检查
    print_section("第 1/4: 系统检查")
    
    if not check_python_version():
        print_error("Python 版本检查失败，请升级 Python 至 3.9+")
        sys.exit(1)
    
    has_cuda, device = check_cuda()
    check_dependencies()
    
    show_system_info()
    
    # 第 2 步: 目录和配置
    print_section("第 2/4: 创建目录和配置")
    setup_directories()
    setup_config()
    
    # 第 3 步: 安装依赖
    print_section("第 3/4: 安装依赖")
    
    try:
        import torch
        print_ok("PyTorch 已安装")
    except ImportError:
        if not install_dependencies():
            print_error("无法自动安装依赖")
            print_info("请手动运行: pip install -r requirements.txt")
            sys.exit(1)
    
    # 第 4 步: 测试
    print_section("第 4/4: 测试")
    test_passed = test_inference()
    
    # 最后: 显示总结和后续步骤
    print_header("✅ 设置完成")
    
    print_info("配置状态:")
    print_ok(f"Python 版本: {sys.version_info.major}.{sys.version_info.minor}+")
    print_ok(f"GPU 支持: {'是 (CUDA)' if has_cuda else '否 (CPU)'}")
    
    if test_passed:
        print_ok("推理测试: 通过 ✓")
    else:
        print_warning("推理测试: 跳过 (等待模型文件)")
    
    print("")
    show_next_steps()
    
    print(f"{Colors.GREEN}{Colors.BOLD}🎉 恭喜！您已准备好使用本地模型了！{Colors.END}\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  设置被中止{Colors.END}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}❌ 发生错误: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
