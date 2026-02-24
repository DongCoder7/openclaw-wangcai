#!/usr/bin/env python3
"""
数据源测试工具 - 测试所有可用数据源
"""
import sys
import time
from datetime import datetime

# Test results
results = {}

def test_akshare():
    """Test AKShare availability"""
    print("\n" + "="*60)
    print("Testing AKShare...")
    print("="*60)
    
    try:
        import akshare as ak
        print(f"✅ AKShare imported successfully (version: {ak.__version__})")
        
        # Test getting stock list
        print("\nTesting stock list fetch...")
        df = ak.stock_zh_a_spot_em()
        print(f"✅ Stock list fetched: {len(df)} stocks")
        
        # Test getting historical data
        print("\nTesting historical data fetch...")
        df = ak.stock_zh_a_hist(symbol="000001", period="daily", start_date="20240101", end_date="20240110", adjust="")
        print(f"✅ Historical data fetched: {len(df)} days")
        print(f"   Columns: {list(df.columns)}")
        
        # Test fundamental data
        print("\nTesting fundamental data...")
        try:
            df = ak.stock_financial_report_sina(stock="000001", symbol="利润表")
            print(f"✅ Fundamental data available")
        except Exception as e:
            print(f"⚠️ Fundamental data: {e}")
        
        results['akshare'] = {
            'available': True,
            'stocks': len(ak.stock_zh_a_spot_em()),
            'notes': 'Fully functional'
        }
        return True
        
    except ImportError as e:
        print(f"❌ AKShare not installed: {e}")
        results['akshare'] = {'available': False, 'error': str(e)}
        return False
    except Exception as e:
        print(f"❌ AKShare test failed: {e}")
        results['akshare'] = {'available': False, 'error': str(e)}
        return False

def test_tushare():
    """Test Tushare availability"""
    print("\n" + "="*60)
    print("Testing Tushare...")
    print("="*60)
    
    try:
        import tushare as ts
        print(f"✅ Tushare imported (version: {ts.__version__})")
        
        # Try to get token from config
        import json
        import os
        config_path = '/root/.openclaw/workspace/config/data_sources.json'
        token = None
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
                token = config.get('tushare', {}).get('token')
        
        if not token:
            print("⚠️ No Tushare token configured")
            results['tushare'] = {
                'available': False,
                'error': 'No token configured',
                'setup': 'Add token to config/data_sources.json'
            }
            return False
        
        pro = ts.pro_api(token)
        df = pro.daily(ts_code='000001.SZ', start_date='20240101', end_date='20240110')
        print(f"✅ Tushare API working: {len(df)} records")
        
        results['tushare'] = {
            'available': True,
            'notes': 'Token valid, API working'
        }
        return True
        
    except ImportError:
        print("❌ Tushare not installed")
        results['tushare'] = {'available': False, 'error': 'Not installed'}
        return False
    except Exception as e:
        print(f"❌ Tushare test failed: {e}")
        results['tushare'] = {'available': False, 'error': str(e)}
        return False

def test_tencent_api():
    """Test Tencent API availability"""
    print("\n" + "="*60)
    print("Testing Tencent API...")
    print("="*60)
    
    try:
        import requests
        import json
        
        # Test single stock quote
        url = "https://qt.gtimg.cn/q=sh600519"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200 and '600519' in response.text:
            print("✅ Tencent API working (single stock)")
        else:
            print(f"⚠️ Tencent API response issue: {response.status_code}")
            results['tencent'] = {'available': False, 'error': 'Response issue'}
            return False
        
        # Test batch quotes
        url = "https://qt.gtimg.cn/q=sh600519,sz000001"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            stocks = response.text.strip().split('v_')
            print(f"✅ Tencent API batch working: {len(stocks)-1} stocks")
        
        results['tencent'] = {
            'available': True,
            'notes': 'No auth required, good for realtime'
        }
        return True
        
    except Exception as e:
        print(f"❌ Tencent API test failed: {e}")
        results['tencent'] = {'available': False, 'error': str(e)}
        return False

def test_local_database():
    """Test local database availability"""
    print("\n" + "="*60)
    print("Testing Local Database...")
    print("="*60)
    
    try:
        import sqlite3
        db_path = '/root/.openclaw/workspace/data/historical/historical.db'
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✅ Database connected")
        print(f"   Tables: {tables}")
        
        # Check data coverage
        if 'stock_factors' in tables:
            cursor.execute("SELECT COUNT(DISTINCT ts_code), MIN(trade_date), MAX(trade_date) FROM stock_factors")
            row = cursor.fetchone()
            print(f"✅ stock_factors: {row[0]} stocks, {row[1]} to {row[2]}")
        
        conn.close()
        
        results['local_db'] = {
            'available': True,
            'tables': tables,
            'notes': 'Local cache available'
        }
        return True
        
    except Exception as e:
        print(f"❌ Local database test failed: {e}")
        results['local_db'] = {'available': False, 'error': str(e)}
        return False

def generate_report():
    """Generate summary report"""
    print("\n" + "="*60)
    print("DATA SOURCE TEST REPORT")
    print("="*60)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    available = []
    unavailable = []
    
    for source, result in results.items():
        if result.get('available'):
            available.append((source, result))
        else:
            unavailable.append((source, result))
    
    print(f"✅ Available Sources ({len(available)}):")
    for source, result in available:
        print(f"   • {source}: {result.get('notes', 'OK')}")
    
    print(f"\n❌ Unavailable Sources ({len(unavailable)}):")
    for source, result in unavailable:
        print(f"   • {source}: {result.get('error', 'Unknown error')}")
    
    # Save report
    import json
    report_path = '/root/.openclaw/workspace/data/source_test_report.json'
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results
        }, f, indent=2, default=str)
    print(f"\n📄 Report saved: {report_path}")
    
    return available, unavailable

def main():
    print("="*60)
    print("HISTORICAL DATA FETCHER - Source Test")
    print("="*60)
    print(f"Testing all available data sources...")
    
    # Run all tests
    test_akshare()
    test_tushare()
    test_tencent_api()
    test_local_database()
    
    # Generate report
    available, unavailable = generate_report()
    
    print("\n" + "="*60)
    if available:
        print(f"✅ {len(available)} source(s) ready to use")
        print(f"   Recommended primary: {available[0][0]}")
    else:
        print("❌ No data sources available!")
        print("   Please install at least one data source.")
    print("="*60)

if __name__ == '__main__':
    main()
