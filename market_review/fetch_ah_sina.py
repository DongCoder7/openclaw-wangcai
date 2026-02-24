#!/usr/bin/env python3
"""
A+H股开盘前瞻数据获取脚本 - 使用新浪财经API
"""

import requests
import json
import re
from datetime import datetime

def get_sina_quote(codes):
    """使用新浪财经API获取实时行情"""
    # 新浪财经API
    url = f"https://hq.sinajs.cn/list={','.join(codes)}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        
        data = {}
        text = response.text
        
        # 解析返回的数据
        # 格式: var hq_str_sh600519="贵州茅台,1486.60,1486.60,1486.60,...";
        for code in codes:
            pattern = f'var hq_str_{code}="([^"]*)"'
            match = re.search(pattern, text)
            
            if match and match.group(1):
                values = match.group(1).split(',')
                
                # 新浪格式 (股票):
                # 0: 名称, 1: 今日开盘价, 2: 昨日收盘价, 3: 当前价, 4: 最高价, 5: 最低价
                if len(values) >= 6:
                    name = values[0]
                    open_price = float(values[1]) if values[1] else 0
                    prev_close = float(values[2]) if values[2] else 0
                    current = float(values[3]) if values[3] else 0
                    high = float(values[4]) if values[4] else 0
                    low = float(values[5]) if values[5] else 0
                    
                    change = current - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0
                    
                    data[code] = {
                        'name': name,
                        'price': current,
                        'open': open_price,
                        'prev_close': prev_close,
                        'high': high,
                        'low': low,
                        'change': change,
                        'change_pct': change_pct,
                    }
        
        return data
    except Exception as e:
        print(f"获取数据失败: {e}")
        return {}

def get_ah_market_data():
    """获取A+H股市场开盘前瞻数据"""
    
    now = datetime.now()
    print("=" * 60)
    print("A+H股开盘前瞻 - 新浪财经API数据获取")
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    # A股指数代码 (新浪格式)
    a_indices_codes = ['sh000001', 'sz399001', 'sz399006']
    
    # A股个股代码
    a_stock_codes = [
        'sh600519', 'sz000858',  # 白酒
        'sh600030', 'sh601211',  # 券商
        'sh600036', 'sz000001',  # 银行
        'sh601398',              # 工行
        'sz300308', 'sz300502', 'sz300394',  # 光模块
        'sz300750', 'sz002594', 'sh601012',  # 新能源
        'sh600900',              # 长江电力
        'sh601888',              # 中国中免
        'sz300166',              # 东方国信
    ]
    
    # 港股代码 (新浪格式用 hk)
    hk_codes = [
        'hk00700', 'hk09999', 'hk03690', 'hk01810', 
        'hk09618', 'hk09888', 'hk01299', 'hk02318',
        'hk02800',  # 恒指ETF
    ]
    
    all_codes = a_indices_codes + a_stock_codes + hk_codes
    
    print("📊 正在获取行情数据...")
    data = get_sina_quote(all_codes)
    
    # 分类整理数据
    result = {
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
        'a_indices': [],
        'a_stocks': [],
        'hk_stocks': []
    }
    
    # 映射到中文名称
    name_map = {
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
    for code in a_indices_codes:
        if code in data:
            name = name_map.get(code, data[code]['name'])
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
        sector_data = []
        for code in codes:
            if code in data:
                name = name_map.get(code, data[code]['name'])
                d = data[code]
                sector_data.append({
                    'code': code[2:],
                    'name': name,
                    'price': d['price'],
                    'open': d['open'],
                    'prev_close': d['prev_close'],
                    'change': d['change'],
                    'change_pct': d['change_pct']
                })
                result['a_stocks'].append({
                    'code': code[2:],
                    'name': name,
                    'price': d['price'],
                    'open': d['open'],
                    'prev_close': d['prev_close'],
                    'change': d['change'],
                    'change_pct': d['change_pct']
                })
        
        if sector_data:
            print(f"\n  📌 {sector}:")
            for d in sector_data:
                emoji = '🟢' if d['change_pct'] > 0 else '🔴' if d['change_pct'] < 0 else '🟡'
                print(f"    {emoji} {d['name']}: ¥{d['price']:.2f} ({d['change_pct']:+.2f}%)")
    
    print("\n🇭🇰 港股重点个股:")
    for code in hk_codes:
        if code in data:
            name = name_map.get(code, data[code]['name'])
            d = data[code]
            result['hk_stocks'].append({
                'code': code[2:],
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
