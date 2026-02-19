# QMD Token 节约指南

## 快速开始

本项目使用**简化版 QMD 工具** (`tools/md_compress.py`)，无需额外安装。

### 1. 使用压缩脚本

```bash
cd /root/.openclaw/workspace
bash tools/qmd_compress.sh
```

### 2. 或直接运行 Python 工具

```bash
# 压缩单个文件
python3 tools/md_compress.py compress SKILL.md -o SKILL.min.md --stats

# 分析但不压缩
python3 tools/md_compress.py analyze SKILL.md
```

### 3. 使用压缩脚本

```bash
# 进入 workspace 目录
cd /root/.openclaw/workspace

# 运行压缩工具
bash tools/qmd_compress.sh
```

## 脚本功能

运行脚本后可以选择：

| 选项 | 功能 |
|:----:|:-----|
| 1 | 压缩所有 Skills |
| 2 | 压缩指定 Skill |
| 3 | 压缩 SOP 文档 |
| 4 | 压缩 HEARTBEAT.md |
| 5 | 查看 Token 节约统计 |
| 6 | 恢复原始文件 |

## 手动压缩单个文件

```bash
# 基础压缩
qmd compress SKILL.md -o SKILL.min.md

# 带统计信息
qmd compress SKILL.md -o SKILL.min.md --stats

# 分析但不保存
qmd analyze SKILL.md
```

## Token 节约效果

| 文件类型 | 原始大小 | 压缩后 | 节约 |
|:---------|:--------:|:------:|:----:|
| SKILL.md (a-stock-analysis) | ~3KB | ~2.1KB | ~30% |
| references/analysis_framework.md | ~3KB | ~2.2KB | ~27% |
| HEARTBEAT.md | ~18KB | ~13KB | ~28% |

## 配置文件说明

`.qmdrc.json` 已创建在项目根目录，配置包括：

- ✅ 移除多余空格和换行
- ✅ 删除 HTML 注释
- ✅ 优化代码块格式
- ✅ 图片替换为占位符 [图]
- ✅ 保留表格结构
- ✅ 保留 Emoji（用于标记）

## 使用压缩后的 Skills

### 方式一: 临时使用
```bash
# 压缩后使用 .min.md 版本
# 测试完成后再恢复
bash tools/qmd_compress.sh
# 选择 6) 恢复原始文件
```

### 方式二: 打包时使用
```bash
# 压缩所有 skills
bash tools/qmd_compress.sh
# 选择 1

# 修改 package_skill.py 使用 .min.md 文件
# 打包后再恢复原始文件
```

## 最佳实践

### 1. 开发时使用原始文件
- 保持可读性
- 方便编辑修改

### 2. 打包前压缩
- 节约 token
- 提高传输效率

### 3. 版本控制
- 原始文件提交到 git
- .min.md 加入 .gitignore

```gitignore
# .gitignore 添加
*.min.md
```

## 注意事项

⚠️ **压缩后的文件**: 
- 移除多余格式，可读性降低
- 仅用于生产环境
- 开发调试使用原始文件

⚠️ **不要直接编辑 .min.md 文件**:
- 编辑原始文件
- 重新生成压缩版本

## 常见问题

### Q: 压缩后功能会丢失吗？
A: 不会，qmd 只移除格式冗余，保留所有内容。

### Q: 如何查看节约了多少 token？
A: 使用 `--stats` 参数或运行脚本选项 5。

### Q: 可以自定义压缩级别吗？
A: 可以，修改 `.qmdrc.json` 配置文件。

### Q: 某些文件不想压缩怎么办？
A: 在 `.qmdrc.json` 的 `ignore` 数组中添加路径。

## 相关命令

```bash
# 查看帮助
qmd --help

# 查看压缩帮助
qmd compress --help

# 检查配置
qmd config validate

# 初始化配置
qmd config init
```
