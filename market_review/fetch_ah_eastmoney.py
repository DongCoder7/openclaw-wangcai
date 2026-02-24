#!/usr/bin/env python3
"""
A+H股开盘前瞻数据获取脚本 - 使用东方财富API
"""

import requests
import json
from datetime import datetime

def get_eastmoney_quote(codes):
    """使用东方财富API获取实时行情"""
    
    url = "http://push2.eastmoney.com/api/qt/ulist.np/get"
    
    fields = "f12,f13,f14,f2,f3,f4,f17,f18,f15,f16,f5,f6"
    
    params = {
        'fltt': 2,
        'invt': 2,
        'fields': fields,
        'secids': ','.join(codes)
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        result = {}
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                code = item.get('f12', '')
                market = item.get('f13', '')
                
                # 构建完整代码
                if market == 1:
                    full_code = f'sh{code}'
                elif market == 0:
                    full_code = f'sz{code}'
                elif market == 116:
                    full_code = f'hk{code}'
                else:
                    full_code = code
                
                # fltt=2时，数据已经是正确格式
                price = item.get('f2', 0)
                change_pct = item.get('f3', 0)
                change = item.get('f4', 0)
                open_price = item.get('f17', 0)
                prev_close = item.get('f18', 0)
                high = item.get('f15', 0)
                low = item.get('f16', 0)
                
                result[full_code] = {
                    'name': item.get('f14', ''),
                    'price': price,
                    'open': open_price,
                    'prev_close': prev_close,
                    'high': high,
                    'low': low,
                    'change': change,
                    'change_pct': change_pct,
                }
        
        return result
    except Exception as e:
        print(f"获取数据失败: {e}")
        return {}

def get_ah_market_data():
    """获取A+H股市场开盘前瞻数据"""
    
    now = datetime.now()
    print("=" * 60)
    print("A+H股开盘前瞻 - 东方财富API数据获取")
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    # 东方财富API格式: 市场.代码 (1=上海, 0=深圳, 116=港股)
    
    # A股指数
    a_indices_codes = ['1.000001', '0.399001', '0.399006']
    
    # A股个股
    a_stock_codes = [
        '1.600519', '0.000858',
        '1.600030', '1.601211',
        '1.600036', '0.000001', '1.601398',
        '0.300308', '0.300502', '0.300394',
        '0.300750', '0.002594', '1.601012',
        '1.600900', '1.601888', '0.300166',
    ]
    
    # 港股
    hk_codes = [
        '116.00700', '116.09999', '116.03690', '116.01810',
        '116.09618', '116.09888', '116.01299', '116.02318', '116.02800',
    ]
    
    all_codes = a_indices_codes + a_stock_codes + hk_codes
    
    print("📊 正在获取行情数据...")
    data = get_eastmoney_quote(all_codes)
    
    result = {
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
        'a_indices': [],
        'a_stocks': [],
        'hk_stocks': []
    }
    
    code_map = {
        'sh000001': '上证指数',
        'sz399001': '深证成指',
        'sz399006': '创业板指',
        'sh600519': '贵州茅台',
        'sz000858': '五粮液',
        'sh600030': '中信证券',
        'sh601211': '国泰海通',
        'sh600036': '招商银行',
        'sz000001': '平安银行',
        'sh601398': '工商银行',
        'sz300308': '中际旭创',
        'sz300502': '新易盛',
        'sz300394': '天孚通信',
        'sz300750': '宁德时代',
        'sz002594': '比亚迪',
        'sh601012': '隆基绿能',
        'sh600900': '长江电力',
        'sh601888': '中国中免',
        'sz300166': '东方国信',
        'hk00700': '腾讯控股',
        'hk09999': '网易',
        'hk03690': '美团',
        'hk01810': '小米集团',
        'hk09618': '京东集团',
        'hk09888': '百度集团',
        'hk01299': '友邦保险',
        'hk02318': '中国平安',
        'hk02800': '盈富基金',
    }
    
    print("\n📈 A股主要指数:")
    a_index_list = ['sh000001', 'sz399001', 'sz399006']
    for code in a_index_list:
        if code in data:
            name = code_map.get(code, code)
            d = data[code]
            result['a_indices'].append({
                'code': code,
                'name': name,
                'price': d['price'],
                'open': d['open'],
                'prev_close': d['prev_close'],
                'change': d['change'],
                'change_pct': d['change_pct']
            })
            emoji = '🟢' if d['change_pct'] > 0 else '🔴' if d['change_pct'] < 0 else '🟡'
            status = '高开' if d['change_pct'] > 0 else '低开' if d['change_pct'] < 0 else '平开'
            print(f"  {emoji} {name}: {d['price']:.2f} ({d['change']:+.2f}, {d['change_pct']:+.2f}%) - {status}")
    
    print("\n🏢 A股重点板块:")
    sectors = {
        '白酒': ['sh600519', 'sz000858'],
        '券商': ['sh600030', 'sh601211'],
        '银行': ['sh600036', 'sz000001', 'sh601398'],
        '光模块': ['sz300308', 'sz300502', 'sz300394'],
        '新能源': ['sz300750', 'sz002594', 'sh601012'],
        '其他': ['sh600900', 'sh601888', 'sz300166']
    }
    
    for sector, codes in sectors.items():
        print(f"\n  📌 {sector}:")
        for code in codes:
            if code in data:
                name = code_map.get(code, code)
                d = data[code]
                result['a_stocks'].append({
                    'code': code[2:],
                    'name': name,
                    'price': d['price'],
                    'open': d['open'],
                    'prev_close': d['prev_close'],
                    'change': d['change'],
                    'change_pct': d['change_pct']
                })
                emoji = '🟢' if d['change_pct'] > 0 else '🔴' if d['change_pct'] < 0 else '🟡'
                print(f"    {emoji} {name}: ¥{d['price']:.2f} ({d['change_pct']:+.2f}%)")
    
    print("\n🇭🇰 港股重点个股:")
    for code in hk_codes:
        code_short = f'hk{code.split(".")[1]}'
        if code_short in data:
            name = code_map.get(code_short, code_short)
            d = data[code_short]
            result['hk_stocks'].append({
                'code': code_short[2:],
                'name': name,
                'price': d['price'],
                'open': d['open'],
                'prev_close': d['prev_close'],
                'change': d['change'],
                'change_pct': d['change_pct']
            })
            emoji = '🟢' if d['change_pct'] > 0 else '🔴' if d['change_pct'] < 0 else '🟡'
            print(f"  {emoji} {name}: HK${d['price']:.2f} ({d['change_pct']:+.2f}%)")
    
    # 保存数据
    date_str = now.strftime('%Y-%m-%d')
    output_file = f'/root/.openclaw/workspace/market_review/ah_data_{date_str}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 数据已保存至: {output_file}")
    
    return result

if __name__ == '__main__':
    get_ah_market_data()
