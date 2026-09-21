# GIS Code AI

**中文** | [English](README_EN.md)

GIS Code AI 是一个面向工业 GIS 测试工程的 AI 研究原型，用于将自然语言测试需求转换为可执行的 JSON 工作流。当前系统已从最初的单步骤生成器扩展为可控的 Agentic Workflow，涵盖任务规划、历史模板检索、本地微调模型回退、结果校验与修复、人工决策以及完整的生成溯源。

## 当前架构

系统按照职责划分为五层：

1. **交互层（Interaction Layer）**：接收自然语言 GIS 指令，并允许用户选择全自动规划或 Human-in-the-loop 模式。
2. **规划层（Planning Layer）**：提取 GIS 意图，并结合领域拓扑规则和历史动作转移关系规划后续操作。
3. **生成层（Generation Layer）**：检索并重排序历史 JSON 模板；RAG 未命中时调用微调模型；模型不可用时使用确定性脚手架作为最终回退。
4. **质量层（Quality Layer）**：检查 schema、ID 和语义一致性，修复可恢复错误，并将无法自动解决的问题路由至重新规划或人工审核。
5. **输出层（Output Layer）**：分别导出干净的可执行 JSON，以及包含 Agent 决策和数据来源的 trace/provenance JSON。

LangGraph 负责管理共享状态、节点执行顺序和条件路由。项目中的各个 Agent 本质上是按照职责划分的工作流节点，而不是拥有独立目标和记忆的完全自治 Agent。

详细说明请参阅[Agent Loop 架构](docs/AGENT_LOOP_ARCHITECTURE.md)和[最新架构流程图](docs/LATEST_ARCHITECTURE_FLOWCHART.md)。

## 项目目录

```text
configs/                 领域同义词和配置示例
data/raw/                历史 GIS 工作流原始数据（受访问控制）
data/processed/          处理后的数据集和紧凑型 RAG 索引
docs/                    架构、部署和重新上手文档
examples/                交互式与端到端 Demo
scripts/                 数据处理、RAG、评测和部署脚本
src/agents/              规划、生成、质量控制、Loop 和 Harness 节点
src/inference/           RAG 与本地模型推理适配器
src/interactive/         多步骤工作流脚手架
tests/                   单元测试和工作流测试
```

大型模型权重、本地 `llama.cpp` 构建产物、临时评测输出、Word 报告和公司内部交接材料不会提交到 Git。

## 快速开始

项目开发环境为 Python 3.12，原本地环境位于 `C:\Python\tf_env`。在其他机器上建议重新创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-langgraph.txt
python -m pip install pytest
```

运行核心测试：

```powershell
python -m pytest tests\test_agent_loop.py -q
```

使用 LangGraph 和 RAG 启动交互式工作流：

```powershell
python examples\demo_agent_loop.py --engine langgraph --use-rag --show-agent-trace
```

Demo 会询问初始 GIS 指令，并让用户选择系统自动完成规划，或者在关键决策点暂停并等待用户选择。也可以直接通过命令行传入 prompt：

```powershell
python examples\demo_agent_loop.py "Create E MS Installatie FP" `
  --engine langgraph --planning-mode auto --max-steps 1 `
  --use-rag --show-agent-trace
```

## RAG 检索与重排序

RAG 使用归一化的 `all-MiniLM-L6-v2` embedding，并将 dense cosine similarity 与加权关键词重合分数组合。初步检索后，规则导向的 reranker 会进一步判断：

- method 是否匹配；
- GIS object 是否兼容；
- 用户要求的字段是否被候选模板覆盖；
- `create`、`update`、`editor` 等 JSON 区域是否与操作类型一致。

查看重排序前后的候选、选择原因及原始 JSON 模板：

```powershell
python scripts\debug_rag_rerank.py "Create E MS Installatie FP" `
  --top-k 10 --show-reasons --show-json all
```

运行内部 non-self reranker benchmark：

```powershell
python scripts\evaluate_rag_reranker.py `
  --query-mode instruction --top-ks 1,3,5,10 --exclude-self `
  --output tmp\rag_reranker_nonself_eval.json
```

该 benchmark 用于衡量现有 865 条模板知识库内部的一致性，只适合作为回归测试，不能直接等同于生产环境准确率。对外报告模型或系统准确率前，仍需要独立的 held-out 用户指令和 GIS 专家标注。

## 本地微调模型

本地 CPU 部署使用 Q4_K_M GGUF 模型，模型权重不会存储在 Git 中：

```text
models/gguf/gis-step-model-Q4_K_M.gguf
```

项目使用 CodeLlama-7B-Instruct + LoRA 完成步骤级 JSON 生成微调，并通过 `llama.cpp` server 接入 Agentic Workflow。RAG 未找到兼容模板时，系统才会调用该模型。

重新获取并构建 `llama.cpp`：

```powershell
git clone https://github.com/ggml-org/llama.cpp external\llama.cpp
powershell -ExecutionPolicy Bypass -File scripts\start_llama_cpp_server.ps1
```

启用微调模型回退：

```powershell
python examples\demo_agent_loop.py "Create E MS Installatie FP" `
  --engine langgraph --planning-mode auto --use-rag --load-llm `
  --model-backend llama_cpp_server --show-agent-trace
```

模型转换和服务启动方法参阅[GGUF 与 llama.cpp 部署指南](docs/GGUF_LLAMA_CPP_DEPLOYMENT.md)。

## 重建数据与 RAG 索引

```powershell
python scripts\00_parse_workflows.py
python scripts\01_generate_instructions_and_data.py
python scripts\02_build_rag.py
```

当前历史数据包括：

- 4,012 个 GIS 测试工作流；
- 40,209 条步骤级指令记录；
- 865 条去重后的高质量 RAG 模板。

原始数据与处理后数据可能包含来自客户项目的结构和领域信息，只能按照适用的公司与客户数据政策进行复制和共享。

## 当前完成情况

- 已实现 LangGraph 工作流及共享状态管理。
- 已实现自动规划与 Human-in-the-loop 两种交互模式。
- 已实现 RAG 检索、规则导向 reranker 和候选调试工具。
- 已实现 fine-tuned model 与 deterministic fallback 的分层生成路径。
- 已实现 Validator、Repairer、Reviewer 和失败路由。
- 已将最终可执行 JSON 与 Agent trace/provenance 分离。
- 已将 CodeLlama-7B LoRA 模型转换为 Q4_K_M GGUF，可通过 `llama.cpp` 进行本地 CPU 推理。

## 已知局限与后续重点

- 带有多个具体字段和值的 parameter-rich instruction 仍是当前主要质量缺口。
- 需要构建独立的 held-out golden dataset，避免使用同一批历史模板同时完成检索和评测。
- reranker 的内部 non-self 结果不能直接作为生产准确率或可靠性指标。
- 本地模型 server 尚未作为持久化服务进行管理，也没有完整的 CI/CD、认证、监控和模型注册机制。
- 下一阶段应优先衡量参数保留率、schema pass rate、semantic pass rate、RAG miss rate、model fallback rate、repair rate 和人工接管率。

长期中断后重新开始项目时，请按照[项目归档与重新上手指南](docs/PROJECT_ARCHIVE_AND_RESTART_GUIDE.md)操作。公司内部接手者还需要获取单独归档的 handover package 和模型 artifact。

## 数据与安全须知

- 不要提交 API key、密码、`.env` 文件、模型权重或能够识别客户的信息。
- 与新成员或外部组织共享项目前，必须确认 GitHub 仓库权限和客户数据授权。
- 模型 artifact、内部报告和评测证据应存储在公司批准的文件或模型管理系统中。
- 干净的 workflow JSON 与 trace JSON 应分开保存，因为 trace 可能包含用户 prompt、Agent 决策和历史模板来源。
