# 贡献指南

感谢您考虑为 GIS Code AI 项目做出贡献！

## 如何贡献

### 报告 Bug

如果您发现了 bug，请创建一个 Issue，并包含以下信息：

1. **Bug 描述**: 清晰简洁的描述
2. **重现步骤**: 详细的重现步骤
3. **期望行为**: 您期望发生什么
4. **实际行为**: 实际发生了什么
5. **环境信息**: 操作系统、Python 版本等
6. **截图**: 如果适用，添加截图

### 建议新功能

如果您有新功能的想法：

1. 创建一个 Issue，标记为 "enhancement"
2. 清楚地描述该功能
3. 解释为什么这个功能有用
4. 如果可能，提供示例或原型

### 提交代码

#### 准备工作

1. Fork 本仓库
2. 克隆您的 fork 到本地
3. 创建一个新分支：`git checkout -b feature/your-feature-name`
4. 设置开发环境（参见 [SETUP.md](SETUP.md)）

#### 代码规范

- 遵循 PEP 8 Python 代码风格指南
- 使用有意义的变量和函数名
- 添加必要的注释和文档字符串
- 保持函数简短且功能单一

#### 代码格式化

我们使用以下工具来保持代码质量：

```bash
# 代码格式化
black src/ tests/

# 代码检查
flake8 src/ tests/

# 类型检查
mypy src/
```

#### 编写测试

- 为新功能编写测试
- 确保所有测试通过：`pytest tests/`
- 保持高测试覆盖率

#### 提交信息

使用清晰的提交信息：

```
类型: 简短描述（不超过 50 字符）

更详细的解释说明（如果需要）。每行不超过 72 字符。
说明这个改动做了什么以及为什么这样做。

- 可以使用列表
- 来组织信息

相关 Issue: #123
```

提交类型：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建或辅助工具的变动

#### 创建 Pull Request

1. 推送您的分支到 GitHub
2. 在 GitHub 上创建 Pull Request
3. 填写 PR 模板（如果有）
4. 链接相关的 Issue
5. 等待代码审查

### Pull Request 审查流程

1. 自动化测试必须通过
2. 至少需要一位维护者的批准
3. 解决所有审查意见
4. 保持提交历史清晰

## 开发环境设置

详细的环境设置说明请查看 [SETUP.md](SETUP.md)

### 快速设置

```bash
# 克隆仓库
git clone https://github.com/your-username/gis-code-ai.git
cd gis-code-ai

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖（包括开发依赖）
pip install -r requirements.txt
pip install -e ".[dev]"

# 运行测试
pytest tests/
```

## 代码审查

代码审查的重点：

- **功能性**: 代码是否实现了预期功能
- **可读性**: 代码是否易于理解
- **性能**: 是否有明显的性能问题
- **测试**: 是否有充分的测试覆盖
- **文档**: 是否有必要的文档和注释

## 社区准则

- 尊重所有贡献者
- 建设性地提供反馈
- 接受不同的观点
- 专注于对项目最有利的做法

## 获取帮助

如果您需要帮助：

1. 查看现有的 [文档](docs/)
2. 搜索现有的 [Issues](https://github.com/rockyistt/gis-code-ai/issues)
3. 创建新的 Issue 提问
4. 联系项目维护者

## 许可证

通过贡献代码，您同意您的贡献将在 MIT 许可证下发布。

---

再次感谢您的贡献！🎉
