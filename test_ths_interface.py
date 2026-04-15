#!/root/.openclaw/workspace/venv/bin/python3
"""测试同花顺数据接口"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

print("=" * 50)
print("测试同花顺数据接口")
print("=" * 50)

# 测试1: 通过akshare获取同花顺数据
try:
    import akshare as ak
    print("\n✅ akshare 已安装，版本:", ak.__version__)
    
    # 尝试获取同花顺相关数据
    print("\n--- 测试同花顺行业板块名称 ---")
    try:
        df = ak.stock_board_industry_name_ths()
        print(f"✅ 同花顺行业板块名称: 获取成功，共 {len(df)} 条")
        print(df.head(3).to_string())
    except Exception as e:
        print(f"❌ 同花顺行业板块名称失败: {e}")
    
    # 测试同花顺概念板块
    try:
        print("\n--- 测试同花顺概念板块名称 ---")
        df = ak.stock_board_concept_name_ths()
        print(f"✅ 同花顺概念板块名称: 获取成功，共 {len(df)} 条")
        print(df.head(3).to_string())
    except Exception as e:
        print(f"❌ 同花顺概念板块名称失败: {e}")
    
    # 测试同花顺概念板块成分股
    try:
        print("\n--- 测试同花顺概念板块成分股 ---")
        df = ak.stock_board_concept_cons_ths(symbol="阿里巴巴概念")
        print(f"✅ 同花顺概念板块成分股(阿里巴巴概念): 获取成功，共 {len(df)} 条")
        print(df.head(3).to_string())
    except Exception as e:
        print(f"❌ 同花顺概念板块成分股失败: {e}")
    
    # 测试同花顺盈利预测
    try:
        print("\n--- 测试同花顺盈利预测 ---")
        df = ak.stock_profit_forecast_ths(symbol="000001")
        print(f"✅ 同花顺盈利预测(000001): 获取成功，共 {len(df)} 条")
        if len(df) > 0:
            print(df.head(3).to_string())
    except Exception as e:
        print(f"❌ 同花顺盈利预测失败: {e}")
    
    # 测试同花顺涨停股
    try:
        print("\n--- 测试同花顺涨停股池 ---")
        df = ak.stock_zt_pool_ths(date="20250411")
        print(f"✅ 同花顺涨停股池(20250411): 获取成功，共 {len(df)} 条")
        if len(df) > 0:
            print(df.head(3).to_string())
    except Exception as e:
        print(f"❌ 同花顺涨停股池失败: {e}")
    
    # 测试同花顺炸板股
    try:
        print("\n--- 测试同花顺炸板股池 ---")
        df = ak.stock_zt_pool_zbgc_ths(date="20250411")
        print(f"✅ 同花顺炸板股池(20250411): 获取成功，共 {len(df)} 条")
        if len(df) > 0:
            print(df.head(3).to_string())
    except Exception as e:
        print(f"❌ 同花顺炸板股池失败: {e}")
    
    # 测试同花顺跌停股
    try:
        print("\n--- 测试同花顺跌停股池 ---")
        df = ak.stock_zt_pool_dtgc_ths(date="20250411")
        print(f"✅ 同花顺跌停股池(20250411): 获取成功，共 {len(df)} 条")
        if len(df) > 0:
            print(df.head(3).to_string())
    except Exception as e:
        print(f"❌ 同花顺跌停股池失败: {e}")
    
    # 测试同花顺强势股
    try:
        print("\n--- 测试同花顺强势股池 ---")
        df = ak.stock_zt_pool_strong_ths(date="20250411")
        print(f"✅ 同花顺强势股池(20250411): 获取成功，共 {len(df)} 条")
        if len(df) > 0:
            print(df.head(3).to_string())
    except Exception as e:
        print(f"❌ 同花顺强势股池失败: {e}")
    
    # 列出所有同花顺相关函数
    print("\n--- akshare中所有同花顺相关函数 ---")
    ths_funcs = [f for f in dir(ak) if 'ths' in f.lower()]
    print(f"找到 {len(ths_funcs)} 个同花顺相关函数:")
    for f in sorted(ths_funcs):
        print(f"  - {f}")
        
except ImportError as e:
    print(f"❌ akshare 未安装: {e}")

# 测试2: 检查是否有pywencai或其他同花顺接口
print("\n" + "=" * 50)
print("检查其他同花顺接口")
print("=" * 50)

try:
    import subprocess
    result = subprocess.run(['/root/.openclaw/workspace/venv/bin/pip', 'list'], 
                          capture_output=True, text=True)
    installed = result.stdout
    ths_lines = [line for line in installed.split('\n') if any(x in line.lower() for x in ['ths', 'hexin', 'wencai', 'tonghuashun'])]
    if ths_lines:
        print(f"✅ 找到同花顺相关包:")
        for line in ths_lines:
            print(f"  {line}")
    else:
        print("ℹ️ 未找到同花顺相关包 (ths/hexin/wencai/tonghuashun)")
except Exception as e:
    print(f"检查失败: {e}")

print("\n" + "=" * 50)
print("测试完成")
print("=" * 50)
