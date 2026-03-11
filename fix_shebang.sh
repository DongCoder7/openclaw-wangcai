#!/bin/bash
# fix_shebang.sh - 自动修复Python脚本的shebang

VENV_SHEBANG="#!/root/.openclaw/workspace/venv/bin/python3"
FIXED=0

echo "=========================================="
echo "修复Python脚本shebang"
echo "=========================================="

# 修复函数
fix_file() {
    local file=$1
    local first_line=$(head -n1 "$file")
    
    # 如果已经是正确的shebang，跳过
    if [[ "$first_line" == "$VENV_SHEBANG" ]]; then
        return 0
    fi
    
    # 如果第一行是shebang，替换它
    if [[ "$first_line" == \#\!*python* ]]; then
        echo "修复: $file"
        echo "  原: $first_line"
        # 使用sed替换第一行
        sed -i "1s|.*|$VENV_SHEBANG|" "$file"
        FIXED=$((FIXED + 1))
    else
        # 如果没有shebang，在第一行添加
        echo "添加shebang: $file"
        sed -i "1i $VENV_SHEBANG" "$file"
        FIXED=$((FIXED + 1))
    fi
}

# 修复tools目录
echo ""
echo "修复 tools/ 目录..."
for file in /root/.openclaw/workspace/tools/*.py; do
    if [ -f "$file" ]; then
        fix_file "$file"
    fi
done

# 修复skills目录
echo ""
echo "修复 skills/ 目录..."
find /root/.openclaw/workspace/skills -name "*.py" -type f | while read file; do
    fix_file "$file"
done

echo ""
echo "=========================================="
echo "✅ 修复完成: $FIXED 个文件"
echo "=========================================="
