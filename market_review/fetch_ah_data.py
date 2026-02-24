#!/usr/bin/env python3
"""
A+H股开盘前瞻数据获取脚本
使用长桥API获取市场数据
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

# 添加tools目录到路径
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/tools'))

from longbridge_provider import LongbridgeDataProvider, LongbridgeConfig

def get_ah_market_data():
    """获取A+H股市场开盘前瞻数据"""
    
    print("=" * 60)
    print("A+H股开盘前瞻 - 长桥API数据获取")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    try:
        provider = LongbridgeDataProvider()
        
        # 1. 获取A股主要指数（使用ETF作为指数代理）
        print("📊 获取A股主要指数...")
        a_indices = {
            '510300': '沪深300ETF',  # 沪深300
            '510050': '上证50ETF',   # 上证50
            '159915': '创业板ETF',   # 创业板
        }
        
        a_shares_data = []
        for code, name in a_indices.items():
            try:
                quote = provider.get_realtime_quote(code, market='CN')
                if quote:
                    a_shares_data.append({
                        'code': code,
                        'name': name,
                        'price': quote.get('price', 0),
                        'prev_close': quote.get('prev_close', 0),
                        'change_pct': quote.get('change_pct', 0),
                    })
                    print(f"  {name}: ¥{quote['price']:.2f} ({quote['change_pct']:+.2f}%)")
                time.sleep(0.1)
            except Exception as e:
                print(f"  ⚠️ 获取{name}失败: {e}")
        
        print()
        
        # 2. 获取港股主要指数和个股
        print("📈 获取港股主要指数及个股...")
        
        # 港股科技巨头
        hk_stocks = {
            '00700': '腾讯控股',
            '09999': '网易',
            '03690': '美团',
            '01810': '小米集团',
            '09618': '京东集团',
            '09888': '百度集团',
        }
        
        # 港股ETF作为指数代理
        hk_indices = {
            '02800': '恒生指数ETF',
            '03033': '恒生科技ETF',
        }
        
        hk_data = []
        
        # 先获取指数
        for code, name in hk_indices.items():
            try:
                quote = provider.get_realtime_quote(code, market='HK')
                if quote:
                    hk_data.append({
                        'code': code,
                        'name': name,
                        'price': quote.get('price', 0),
                        'prev_close': quote.get('prev_close', 0),
                        'change_pct': quote.get('change_pct', 0),
                        'type': 'index'
                    })
                    print(f"  {name}: HK${quote['price']:.2f} ({quote['change_pct']:+.2f}%)")
                time.sleep(0.1)
            except Exception as e:
                print(f"  ⚠️ 获取{name}失败: {e}")
        
        # 获取个股
        for code, name in hk_stocks.items():
            try:
                quote = provider.get_realtime_quote(code, market='HK')
                if quote:
                    hk_data.append({
                        'code': code,
                        'name': name,
                        'price': quote.get('price', 0),
                        'prev_close': quote.get('prev_close', 0),
                        'change_pct': quote.get('change_pct', 0),
                        'type': 'stock'
                    })
                    print(f"  {name}: HK${quote['price']:.2f} ({quote['change_pct']:+.2f}%)")
                time.sleep(0.1)
            except Exception as e:
                print(f"  ⚠️ 获取{name}失败: {e}")
        
        print()
        
        # 3. 获取重点A股板块股票
        print("🏢 获取重点A股板块股票...")
        
        a_stocks = {
            # 白酒
            '600519': '贵州茅台',
            '000858': '五粮液',
            # 券商
            '600030': '中信证券',
            '601211': '国泰海通',
            # 银行
            '600036': '招商银行',
            '000001': '平安银行',
            # AI算力/光模块
            '300308': '中际旭创',
            '300502': '新易盛',
            '300394': '天孚通信',
            # 新能源
            '300750': '宁德时代',
            '002594': '比亚迪',
            '601012': '隆基绿能',
        }
        
        a_data = []
        for code, name in a_stocks.items():
            try:
                quote = provider.get_realtime_quote(code, market='CN')
                if quote:
                    a_data.append({
                        'code': code,
                        'name': name,
                        'price': quote.get('price', 0),
                        'prev_close': quote.get('prev_close', 0),
                        'change_pct': quote.get('change_pct', 0),
                        'open': quote.get('open', 0),
                        'high': quote.get('high', 0),
                        'low': quote.get('low', 0),
                    })
                    print(f"  {name}: ¥{quote['price']:.2f} ({quote['change_pct']:+.2f}%)")
                time.sleep(0.05)
            except Exception as e:
                print(f"  ⚠️ 获取{name}失败: {e}")
        
        print()
        
        # 4. 整理数据并输出
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'a_indices': a_shares_data,
            'hk_data': hk_data,
            'a_stocks': a_data
        }
        
        # 保存JSON数据供后续使用
        output_file = os.path.expanduser('~/.openclaw/workspace/market_review/ah_data_temp.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 数据已保存至: {output_file}")
        print()
        
        return result
        
    except Exception as e:
        print(f"❌ 数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    data = get_ah_market_data()
    
    if data:
        print("\n" + "=" * 60)
        print("数据获取完成，准备生成开盘前瞻报告...")
        print("=" * 60)
    else:
        print("\n数据获取失败，请检查API配置")
        sys.exit(1)
