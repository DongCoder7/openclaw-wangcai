#!/bin/bash
# QMD 批量压缩脚本 - 使用 Python 工具

set -e

WORKSPACE_DIR="/root/.openclaw/workspace"
COMPRESS_CMD="python3 $WORKSPACE_DIR/tools/md_compress.py"

echo "========================================"
echo "  QMD Token 节约工具"
echo "========================================"
echo ""

# 检查 Python 脚本是否存在
if [ ! -f "$WORKSPACE_DIR/tools/md_compress.py" ]; then
    echo "❌ 压缩工具不存在: $WORKSPACE_DIR/tools/md_compress.py"
    exit 1
fi

echo "✅ 压缩工具已就绪"
echo ""

# 功能选择
echo "请选择操作:"
echo ""
echo "1) 压缩所有 Skills"
echo "2) 压缩指定 Skill"
echo "3) 压缩 SOP 文档"
echo "4) 压缩 HEARTBEAT.md"
echo "5) 查看 Token 节约统计"
echo "6) 恢复原始文件（删除 .min.md）"
echo ""
read -p "输入选项 (1-6): " choice

case $choice in
    1)
        echo ""
        echo "🔄 压缩所有 Skills..."
        for skill_dir in $WORKSPACE_DIR/skills/*/; do
            if [ -d "$skill_dir" ]; then
                skill_name=$(basename "$skill_dir")
                echo ""
                echo "📦 处理: $skill_name"
                
                # 压缩 SKILL.md
                if [ -f "$skill_dir/SKILL.md" ]; then
                    $COMPRESS_CMD compress "$skill_dir/SKILL.md" -o "$skill_dir/SKILL.min.md" --stats || true
                fi
                
                # 压缩 references
                if [ -d "$skill_dir/references" ]; then
                    for ref in "$skill_dir/references"/*.md; do
                        if [ -f "$ref" ] && [[ ! "$ref" == *.min.md ]]; then
                            filename=$(basename "$ref" .md)
                            $COMPRESS_CMD compress "$ref" -o "$skill_dir/references/${filename}.min.md" || true
                        fi
                    done
                fi
            fi
        done
        echo ""
        echo "✅ 所有 Skills 压缩完成"
        ;;
        
    2)
        echo ""
        echo "可用的 Skills:"
        ls -1 $WORKSPACE_DIR/skills/
        echo ""
        read -p "输入 Skill 名称: " skill_name
        
        skill_dir="$WORKSPACE_DIR/skills/$skill_name"
        if [ ! -d "$skill_dir" ]; then
            echo "❌ Skill 不存在: $skill_name"
            exit 1
        fi
        
        echo ""
        echo "🔄 压缩 $skill_name..."
        
        # 压缩 SKILL.md
        if [ -f "$skill_dir/SKILL.md" ]; then
            $COMPRESS_CMD compress "$skill_dir/SKILL.md" -o "$skill_dir/SKILL.min.md" --stats
        fi
        
        # 压缩 references
        if [ -d "$skill_dir/references" ]; then
            for ref in "$skill_dir/references"/*.md; do
                if [ -f "$ref" ] && [[ ! "$ref" == *.min.md ]]; then
                    filename=$(basename "$ref" .md)
                    $COMPRESS_CMD compress "$ref" -o "$skill_dir/references/${filename}.min.md"
                fi
            done
        fi
        
        echo ""
        echo "✅ $skill_name 压缩完成"
        ;;
        
    3)
        echo ""
        echo "🔄 压缩 SOP 文档..."
        for doc in $WORKSPACE_DIR/docs/*.md; do
            if [ -f "$doc" ] && [[ ! "$doc" == *.min.md ]]; then
                filename=$(basename "$doc" .md)
                echo "📄 $filename"
                $COMPRESS_CMD compress "$doc" -o "$WORKSPACE_DIR/docs/${filename}.min.md" || true
            fi
        done
        echo ""
        echo "✅ SOP 文档压缩完成"
        ;;
        
    4)
        echo ""
        echo "🔄 压缩 HEARTBEAT.md..."
        if [ -f "$WORKSPACE_DIR/HEARTBEAT.md" ]; then
            $COMPRESS_CMD compress "$WORKSPACE_DIR/HEARTBEAT.md" -o "$WORKSPACE_DIR/HEARTBEAT.min.md" --stats
            echo ""
            echo "✅ HEARTBEAT.md 压缩完成"
        else
            echo "❌ HEARTBEAT.md 不存在"
        fi
        ;;
        
    5)
        echo ""
        echo "📊 Token 节约统计"
        echo "========================================"
        
        total_original=0
        total_compressed=0
        
        # 统计 Skills
        for skill_dir in $WORKSPACE_DIR/skills/*/; do
            if [ -d "$skill_dir" ]; then
                skill_name=$(basename "$skill_dir")
                
                if [ -f "$skill_dir/SKILL.min.md" ]; then
                    original_size=$(stat -c%s "$skill_dir/SKILL.md" 2>/dev/null)
                    compressed_size=$(stat -c%s "$skill_dir/SKILL.min.md" 2>/dev/null)
                    
                    total_original=$((total_original + original_size))
                    total_compressed=$((total_compressed + compressed_size))
                    
                    saved=$((original_size - compressed_size))
                    if [ $original_size -gt 0 ]; then
                        percent=$((saved * 100 / original_size))
                        echo "$skill_name/SKILL.md: ${original_size}B → ${compressed_size}B (节约 ${percent}%)"
                    fi
                fi
            fi
        done
        
        # 统计 references
        for ref in $WORKSPACE_DIR/skills/*/references/*.min.md; do
            if [ -f "$ref" ]; then
                orig_file="${ref%.min.md}.md"
                if [ -f "$orig_file" ]; then
                    ref_name=$(basename "$ref")
                    orig=$(stat -c%s "$orig_file" 2>/dev/null)
                    comp=$(stat -c%s "$ref" 2>/dev/null)
                    
                    total_original=$((total_original + orig))
                    total_compressed=$((total_compressed + comp))
                fi
            fi
        done
        
        if [ $total_original -gt 0 ]; then
            total_saved=$((total_original - total_compressed))
            total_percent=$((total_saved * 100 / total_original))
            echo ""
            echo "总计: ${total_original}B → ${total_compressed}B"
            echo "节约: ${total_saved}B (${total_percent}%)"
        else
            echo ""
            echo "暂无压缩数据，请先执行压缩操作"
        fi
        ;;
        
    6)
        echo ""
        echo "🔄 恢复原始文件..."
        find $WORKSPACE_DIR -name "*.min.md" -type f -delete
        echo "✅ 已删除所有压缩文件，恢复原始版本"
        ;;
        
    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac

echo ""
echo "========================================"
echo "完成!"
echo "========================================"
