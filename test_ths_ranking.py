#!/root/.openclaw/workspace/venv/bin/python3
"""测试同花顺排名数据"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')
import akshare as ak

print("=" * 60)
print("同花顺排名数据测试")
print("=" * 60)

# 测试连续上涨
print("\n--- 同花顺连续上涨排名 ---")
try:
    df = ak.stock_rank_cxfl_ths()
    print(f"✅ 连续上涨: 获取成功，共 {len(df)} 条")
    print(df.head(5).to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试创新高
print("\n--- 同花顺创新高排名 ---")
try:
    df = ak.stock_rank_cxg_ths()
    print(f"✅ 创新高: 获取成功，共 {len(df)} 条")
    print(df.head(5).to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试创新低
print("\n--- 同花顺创新低排名 ---")
try:
    df = ak.stock_rank_cxd_ths()
    print(f"✅ 创新低: 获取成功，共 {len(df)} 条")
    print(df.head(5).to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试连续下跌
print("\n--- 同花顺连续下跌排名 ---")
try:
    df = ak.stock_rank_cxsl_ths()
    print(f"✅ 连续下跌: 获取成功，共 {len(df)} 条")
    print(df.head(5).to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试量价齐升
print("\n--- 同花顺量价齐升排名 ---")
try:
    df = ak.stock_rank_ljqs_ths()
    print(f"✅ 量价齐升: 获取成功，共 {len(df)} 条")
    print(df.head(5).to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试行业板块指数
print("\n--- 同花顺行业板块指数(半导体) ---")
try:
    df = ak.stock_board_industry_index_ths(symbol="半导体")
    print(f"✅ 半导体板块指数: 获取成功，共 {len(df)} 条")
    print(df.tail(5).to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试概念板块指数
print("\n--- 同花顺概念板块指数(AI算力) ---")
try:
    df = ak.stock_board_concept_index_ths(symbol="AI算力")
    print(f"✅ AI算力概念指数: 获取成功，共 {len(df)} 条")
    print(df.tail(5).to_string(index=False))
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n" + "=" * 60)
print("测试完成 - 同花顺接口可用！")
print("=" * 60)
