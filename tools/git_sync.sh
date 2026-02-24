#!/bin/bash
# Git自动同步脚本
# 仅同步：skills、sop文档、学习资料
# 排除：市场报告、临时数据文件

WORKSPACE_DIR="/root/.openclaw/workspace"
LOG_FILE="$WORKSPACE_DIR/.git-sync.log"

cd "$WORKSPACE_DIR"

# 检查是否有变更（限定范围）
# 只检查需要同步的目录
git status --short \
    skills/ \
    docs/ \
    study/ \
    "*.md" 2>/dev/null | \
    grep -v ".openclaw/workshop/data/" | \
    grep -v "memory/" > /tmp/git_changes.txt

CHANGES=$(cat /tmp/git_changes.txt)

if [ -n "$CHANGES" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检测到文件变更，开始同步..." >> "$LOG_FILE"
    
    # 只添加指定目录和配置文件
    git add skills/ docs/ study/ *.md 2>/dev/null || true
    # 同步本地配置文件
    git add .gitignore .qmdrc.json .git-sync.log 2>/dev/null || true
    git add TOOLS.md IDENTITY.md USER.md 2>/dev/null || true
    
    # 移除不需要同步的文件（如果已被暂存）
    git reset HEAD .openclaw/workshop/data/ memory/ 2>/dev/null || true
    
    # 提交变更
    COMMIT_MSG="[$(date '+%Y-%m-%d %H:%M')] 自动同步文档更新"
    git commit -m "$COMMIT_MSG" >> "$LOG_FILE" 2>&1
    
    # 尝试推送到远程
    PUSH_RESULT=$(git push origin master 2>&1)
    if [ $? -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 同步成功: $COMMIT_MSG" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Push失败: $PUSH_RESULT" >> "$LOG_FILE"
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 无变更，跳过同步" >> "$LOG_FILE"
fi

# 保留最近1000行日志
tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
