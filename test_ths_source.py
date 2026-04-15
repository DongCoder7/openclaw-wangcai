#!/root/.openclaw/workspace/venv/bin/python3
"""
测试说明：
用户提到 Kimi 2.5 内置了同花顺数据接口，需要验证是：
1. 模型本身可以直接返回同花顺实时数据
2. 还是通过本地 akshare 库访问

本脚本用于对比测试两种方式的输出
"""

print("=" * 60)
print("同花顺数据源对比测试")
print("=" * 60)

print("\n【方式1: 本地 akshare 获取同花顺数据】")
import akshare as ak

# 获取连续上涨
try:
    df = ak.stock_rank_cxfl_ths()
    print(f"✅ akshare 连续上涨: {len(df)} 条")
    print(df.head(3)[['股票代码', '股票简称', '涨跌幅', '最新价']].to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n" + "=" * 60)
print("【方式2: 直接询问 Kimi 2.5 模型】")
print("=" * 60)
print("\n⚠️ 如果 Kimi 2.5 内置同花顺接口，请模型直接返回：")
print("   - 连续上涨排名 TOP5")
print("   - 最新价、涨跌幅数据")
print("\n请用户验证：模型返回的数据是否与 akshare 获取的一致？")
print("\n如果一致 → 说明模型确实内置同花顺接口")
print("如果不一致 → 说明模型没有实时数据，只有训练数据")
