#!/bin/bash
# Git自动同步脚本
# 用于备份workspace中的所有md文件到git仓库

WORKSPACE_DIR="/root/.openclaw/workspace"
LOG_FILE="$WORKSPACE_DIR/.git-sync.log"

cd "$WORKSPACE_DIR"

# 检查是否有变更
CHANGES=$(git status --short)

if [ -n "$CHANGES" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检测到文件变更，开始同步..." >> "$LOG_FILE"
    
    # 添加所有变更
    git add -A
    
    # 提交变更
    COMMIT_MSG="[$(date '+%Y-%m-%d %H:%M')] 自动同步文档更新"
    git commit -m "$COMMIT_MSG" >> "$LOG_FILE" 2>&1
    
    # 尝试推送到远程
    PUSH_RESULT=$(git push origin master 2>&1)
    if [ $? -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 同步成功: $COMMIT_MSG" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Push失败(可能未配置远程仓库): $PUSH_RESULT" >> "$LOG_FILE"
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 无变更，跳过同步" >> "$LOG_FILE"
fi

# 保留最近1000行日志
tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
