#!/root/.openclaw/workspace/venv/bin/python3
"""
长桥API集成测试脚本
用于验证环境配置和数据获取功能
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_env():
    """测试环境变量"""
    print("=" * 60)
    print("步骤1: 检查环境变量")
    print("=" * 60)
    
    app_key = os.getenv('LONGBRIDGE_APP_KEY')
    app_secret = os.getenv('LONGBRIDGE_APP_SECRET')
    
    if not app_key:
        print("❌ LONGBRIDGE_APP_KEY 未设置")
        print("   请执行: export LONGBRIDGE_APP_KEY='your_key'")
        return False
    
    if not app_secret:
        print("❌ LONGBRIDGE_APP_SECRET 未设置")
        print("   请执行: export LONGBRIDGE_APP_SECRET='your_secret'")
        return False
    
    print(f"✅ LONGBRIDGE_APP_KEY: {app_key[:8]}...")
    print(f"✅ LONGBRIDGE_APP_SECRET: {app_secret[:8]}...")
    return True


def test_longbridge_import():
    """测试长桥模块导入"""
    print("\n" + "=" * 60)
    print("步骤2: 测试模块导入")
    print("=" * 60)
    
    try:
        from longbridge_provider import LongbridgeDataProvider
        print("✅ longbridge_provider 模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def test_connection():
    """测试API连接"""
    print("\n" + "=" * 60)
    print("步骤3: 测试API连接")
    print("=" * 60)
    
    try:
        from longbridge_provider import LongbridgeDataProvider
        
        provider = LongbridgeDataProvider()
        print("✅ LongbridgeDataProvider 初始化成功")
        
        # 测试A股行情
        print("\n测试A股行情（平安银行000001）...")
        quote = provider.get_realtime_quote('000001', market='CN')
        
        if quote:
            print(f"✅ A股行情获取成功")
            print(f"   名称: {quote['name']}")
            print(f"   价格: ¥{quote['price']:.2f}")
            print(f"   涨跌: {quote['change_pct']:+.2f}%")
        else:
            print("⚠️ 未获取到数据（可能非交易时间）")
        
        # 测试港股行情
        print("\n测试港股行情（腾讯00700）...")
        hk_quote = provider.get_realtime_quote('00700', market='HK')
        
        if hk_quote:
            print(f"✅ 港股行情获取成功")
            print(f"   名称: {hk_quote['name']}")
            print(f"   价格: HK${hk_quote['price']:.2f}")
            print(f"   涨跌: {hk_quote['change_pct']:+.2f}%")
        else:
            print("⚠️ 未获取到数据")
        
        return True
        
    except Exception as e:
        print(f"❌ API连接测试失败: {e}")
        return False


def test_datasource_manager():
    """测试DataSourceManager"""
    print("\n" + "=" * 60)
    print("步骤4: 测试DataSourceManager（自动回退）")
    print("=" * 60)
    
    try:
        from vqm_trading_monitor import DataSourceManager
        
        ds = DataSourceManager()
        print("✅ DataSourceManager 初始化成功")
        
        # 批量获取测试
        test_codes = ['000001', '600036']
        print(f"\n批量获取 {test_codes} 的行情...")
        quotes = ds.get_realtime_quotes(test_codes)
        
        if quotes:
            print(f"✅ 批量获取成功: {len(quotes)}/{len(test_codes)}")
            for code, q in quotes.items():
                print(f"   {q['name']}({code}): ¥{q['price']:.2f} ({q['change_pct']:+.2f}%) [{q.get('source', 'unknown')}]")
        else:
            print("⚠️ 未获取到数据")
        
        return True
        
    except Exception as e:
        print(f"❌ DataSourceManager测试失败: {e}")
        return False


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "长桥API集成测试" + " " * 28 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    results = []
    
    # 运行测试
    results.append(("环境变量", test_env()))
    results.append(("模块导入", test_longbridge_import()))
    
    # 只有前两个通过才继续
    if all(r[1] for r in results):
        results.append(("API连接", test_connection()))
        results.append(("数据管理器", test_datasource_manager()))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！长桥API已就绪")
    else:
        print("⚠️ 部分测试未通过，请检查配置")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
