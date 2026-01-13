# 配置目录

将敏感配置（如 API Key、数据库密码）放在本地环境变量或单独配置文件中，请勿把真实密钥提交到仓库。

建议：
- 在仓库中保留 `configs/example_config.yaml`（不含密钥）
- 开发者本地复制并重命名为 `configs/local_config.yaml`（在 .gitignore 中）
