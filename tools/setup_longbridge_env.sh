#!/bin/bash
# 设置长桥API环境变量示例
# 使用前请将值替换为你的实际API密钥

export LONGBRIDGE_APP_KEY="your_app_key_here"
export LONGBRIDGE_APP_SECRET="your_app_secret_here"
# export LONGBRIDGE_ACCESS_TOKEN="your_access_token_here"  # 可选

echo "✅ 长桥API环境变量已设置"
echo ""
echo "当前配置:"
echo "  LONGBRIDGE_APP_KEY: ${LONGBRIDGE_APP_KEY:0:8}..."
echo "  LONGBRIDGE_APP_SECRET: ${LONGBRIDGE_APP_SECRET:0:8}..."
