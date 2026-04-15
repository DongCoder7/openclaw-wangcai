#!/root/.openclaw/workspace/venv/bin/python3
"""
获取上证指数分钟级别K线数据 - 同花顺接口
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')
import pandas as pd
import numpy as np
from datetime import datetime

print("=" * 70)
print("上证指数分钟K线数据获取 - 同花顺接口")
print("=" * 70)

# 使用同花顺接口
print("\n【使用同花顺板块指数接口】")
try:
    import akshare as ak
    
    # 获取同花顺行业板块指数K线
    # 上证指数可以用 "同花顺大盘" 或直接用 ak.index_zh_a_hist
    
    # 先获取板块名称列表
    print("获取同花顺板块列表...")
    board_df = ak.stock_board_industry_name_ths()
    print(f"共 {len(board_df)} 个行业板块")
    
    # 找与大盘相关的
    print("\n相关板块:")
    for _, row in board_df.iterrows():
        if '综合' in row['name'] or '大盘' in row['name'] or '上证' in row['name']:
            print(f"  - {row['name']} ({row['code']})")
    
    # 获取上证指数的历史数据（用新浪或东方财富）
    print("\n【尝试新浪财经接口】")
    
    # 使用新浪财经的分钟数据接口
    import requests
    
    # 新浪分钟数据
    url = "https://quotes.sina.cn/cn/api/quotes.php"
    params = {
        "symbol": "sh000001",
        "scale": "5",  # 5分钟
        "ma": "5",
        "datalen": "200"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    print(f"新浪API状态码: {resp.status_code}")
    print(f"响应前200字符: {resp.text[:200]}")
    
except Exception as e:
    print(f"❌ 失败: {e}")
    import traceback
    traceback.print_exc()

# 尝试腾讯财经分钟数据
print("\n【尝试腾讯财经分钟数据】")
try:
    import requests
    import json
    
    # 腾讯财经分钟线
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "param": "sh000001,day,,,200,qfq"  # 日线
    }
    
    resp = requests.get(url, params=params, timeout=15)
    print(f"腾讯日线状态码: {resp.status_code}")
    data = resp.json()
    print(f"数据键: {data.keys()}")
    
    # 尝试分钟数据
    print("\n尝试获取5分钟数据...")
    url_5m = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params_5m = {
        "param": "sh000001,5m,,,200,qfq"
    }
    
    resp_5m = requests.get(url_5m, params=params_5m, timeout=15)
    print(f"腾讯5分钟状态码: {resp_5m.status_code}")
    
    try:
        data_5m = resp_5m.json()
        print(f"5分钟数据键: {data_5m.keys()}")
        
        # 解析数据
        if 'data' in data_5m and 'sh000001' in data_5m['data']:
            sh_data = data_5m['data']['sh000001']
            print(f"sh000001 键: {sh_data.keys()}")
            
            if '5m' in sh_data or 'qfq5m' in sh_data:
                kline_key = '5m' if '5m' in sh_data else 'qfq5m'
                klines = sh_data[kline_key]
                print(f"✅ 获取到 {len(klines)} 条5分钟K线")
                
                # 解析
                rows = []
                for k in klines:
                    parts = k.split(',')
                    rows.append({
                        'time': parts[0],
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'low': float(parts[3]),
                        'high': float(parts[4]),
                        'volume': float(parts[5])
                    })
                
                df_5m = pd.DataFrame(rows)
                print("\n最近10条5分钟K线:")
                print(df_5m.tail(10).to_string(index=False))
                df_5m.to_csv('/tmp/sh_5m_tx.csv', index=False)
                print("\n✅ 数据已保存到 /tmp/sh_5m_tx.csv")
    except Exception as e:
        print(f"解析失败: {e}")
        print(f"响应: {resp_5m.text[:300]}")
        
except Exception as e:
    print(f"❌ 腾讯财经失败: {e}")
    import traceback
    traceback.print_exc()

# 尝试网易财经
print("\n【尝试网易财经】")
try:
    import requests
    
    # 网易财经API
    url = "http://quotes.money.163.com/service/chddata.html"
    params = {
        "code": "0000001",  # 上证指数
        "start": "20260414",
        "end": "20260414",
        "fields": "TCLOSE;HIGH;LOW;TOPEN;CHG;PCHG;VOTURNOVER"
    }
    
    resp = requests.get(url, params=params, timeout=15)
    print(f"网易财经状态码: {resp.status_code}")
    print(f"响应前200字符: {resp.text[:200]}")
    
except Exception as e:
    print(f"❌ 网易财经失败: {e}")

print("\n" + "=" * 70)
print("分钟数据获取尝试完成")
print("=" * 70)
