#!/bin/bash
# 板块分析快速启动脚本
# 使用方式: ./analyze_block.sh [板块名称]
#
# 示例:
#   ./analyze_block.sh 氮肥板块
#   ./analyze_block.sh 半导体

BLOCK_NAME="$1"

if [ -z "$BLOCK_NAME" ]; then
    echo "❌ 错误：请提供板块名称"
    echo "用法: ./analyze_block.sh [板块名称]"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     板块分析启动 - $BLOCK_NAME"
echo "║     强制检查清单模式"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 1. 初始化检查清单
echo "📋 步骤1: 初始化检查清单..."
./quality/checklist_block_analysis.py init "$BLOCK_NAME"

echo ""
echo "🔍 步骤2: 执行多源搜索（必须完成！）"
echo ""
echo "请按顺序执行以下搜索："
echo ""
echo "【P1】Exa搜索（复制执行）："
echo "  mcporter call 'exa.web_search_exa({\"query\": \"${BLOCK_NAME} 价格走势 2025\", \"numResults\": 10})'"
echo "  mcporter call 'exa.web_search_exa({\"query\": \"${BLOCK_NAME} 订单 政策\", \"numResults\": 10})'"
echo ""
echo "【P2】知识星球搜索："
echo "  调用 multi_source_news_v2.search_industry_chain_news()"
echo ""
echo "【P3】新浪财经："
echo "  curl \"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=20\""
echo ""
echo "完成后执行："
echo "  ./quality/checklist_block_analysis.py complete p1_exa_search '搜索完成'"
echo "  ./quality/checklist_block_analysis.py complete p2_zsxq_search '搜索完成'"
echo "  ./quality/checklist_block_analysis.py complete p3_sina_api 'API调用完成'"
echo ""
echo "检查状态："
echo "  ./quality/checklist_block_analysis.py status"
echo "  ./quality/checklist_block_analysis.py check"
echo ""
