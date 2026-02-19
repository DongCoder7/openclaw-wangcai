# QMD 使用指南

## 安装

```bash
npm install -g @tobilu/qmd
```

## 当前配置状态

### Collections

| Collection | 路径 | 文件数 | Context |
|:-----------|:-----|:------:|:--------|
| docs | /root/.openclaw/workspace/docs | 12 | SOP文档和使用指南 |
| study | /root/.openclaw/workspace/study | 4 | 学习笔记和研究报告 |
| a-stock-analysis | /root/.openclaw/workspace/skills/a-stock-analysis | 2 | A股个股分析Skill |
| a-sector-analysis | /root/.openclaw/workspace/skills/a-sector-analysis | 2 | A股板块分析Skill |
| h-stock-analysis | /root/.openclaw/workspace/skills/h-stock-analysis | 2 | H股个股分析Skill |

### 使用命令

#### 1. 搜索文档

```bash
# 关键词搜索
qmd search "股票分析" -c docs

# 语义搜索（需要embeddings）
qmd vsearch "风险管理" -c docs

# 混合搜索（推荐）
qmd query "量化投资策略" -c docs
```

#### 2. 获取文档

```bash
# 获取指定文档
qmd get "docs/stock_analysis_sop.md"

# 获取多个文档
qmd multi-get "docs/*.md" -l 50
```

#### 3. 列出文档

```bash
# 列出所有collections
qmd collection list

# 列出docs中的文件
qmd ls docs
```

#### 4. 更新索引

```bash
# 更新所有collections
qmd update

# 生成embeddings（用于语义搜索）
qmd embed
```

#### 5. 查看状态

```bash
qmd status
```

## 输出格式

```bash
# JSON格式（适合LLM）
qmd search "策略" --json

# Markdown格式
qmd search "策略" --md

# 文件列表格式
qmd search "策略" --files
```

## 注意事项

- 当前运行在 CPU 模式（无 GPU 加速）
- embeddings 生成需要下载模型（约 300MB）
- 首次使用可能需要编译 llama.cpp

## 示例工作流

```bash
# 1. 更新索引
qmd update

# 2. 搜索相关文档
qmd search "止损策略" -c docs --json

# 3. 获取完整文档
qmd get "docs/risk_management_sop.md" --full
```
