#!/bin/bash
# check_venv_compliance.sh - 检查所有Python脚本是否符合venv规范

echo "=========================================="
echo "检查Python脚本venv合规性"
echo "=========================================="

VENV_SHEBANG="#!/root/.openclaw/workspace/venv/bin/python3"
ERRORS=0

# 检查tools目录下的Python脚本
echo ""
echo "检查 tools/ 目录..."
for file in /root/.openclaw/workspace/tools/*.py; do
    if [ -f "$file" ]; then
        # 检查shebang
        first_line=$(head -n1 "$file")
        if [[ "$first_line" != "$VENV_SHEBANG" ]]; then
            echo "❌ $(basename $file): 缺少正确的shebang"
            echo "   当前: $first_line"
            ERRORS=$((ERRORS + 1))
        else
            echo "✅ $(basename $file)"
        fi
    fi
done

# 检查skills目录下的Python脚本
echo ""
echo "检查 skills/ 目录..."
find /root/.openclaw/workspace/skills -name "*.py" -type f | while read file; do
    # 检查shebang
    first_line=$(head -n1 "$file")
    if [[ "$first_line" != "$VENV_SHEBANG" ]]; then
        echo "❌ ${file##*/}: 缺少正确的shebang"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ ${file##*/}"
    fi
done

echo ""
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo "✅ 所有脚本符合venv规范"
else
    echo "⚠️ 发现 $ERRORS 个脚本需要修复"
    echo "修复命令: ./fix_shebang.sh"
fi
echo "=========================================="
