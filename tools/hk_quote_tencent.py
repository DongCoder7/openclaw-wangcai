#!/root/.openclaw/workspace/venv/bin/python3
"""腾讯API获取港股实时行情"""
import requests
import time

HK_STOCKS = {
    '00700': '腾讯控股',
    '09988': '阿里巴巴',
    '03690': '美团',
    '01810': '小米集团',
    '02318': '中国平安',
    '03988': '中国银行',
    '01109': '华润置地',
    '00688': '中国海外发展',
    '00883': '中国海洋石油',
    '00857': '中国石油股份',
    '01088': '中国神华',
    '00998': '中信银行',
    '02331': '李宁',
    '06690': '百济神州',
    '09618': '京东健康',
    '09999': '网易'
}

def get_hk_quote(code):
    """腾讯API获取港股行情"""
    try:
        url = f'https://qt.gtimg.cn/q=hk{code}'
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        
        data_str = response.text
        if not data_str or '~' not in data_str:
            return None
        
        parts = data_str.split('~')
        if len(parts) < 45:
            return None
        
        return {
            'code': code,
            'name': parts[1],
            'price': float(parts[3]),
            'prev_close': float(parts[4]),
            'open': float(parts[5]),
            'high': float(parts[33]),
            'low': float(parts[34]),
            'change_pct': float(parts[32]),
            'volume': float(parts[36])
        }
    except Exception as e:
        print(f'获取港股 {code} 失败: {e}')
        return None

if __name__ == '__main__':
    print('=== 港股实时行情 (腾讯API) ===')
    results = {}
    for code, name in HK_STOCKS.items():
        quote = get_hk_quote(code)
        if quote:
            results[code] = quote
            emoji = '🟢' if quote['change_pct'] >= 0 else '🔴'
            print(f"{emoji} {name}({code}): {quote['price']:.2f} ({quote['change_pct']:+.2f}%)")
        time.sleep(0.1)
    
    print(f"\n共获取 {len(results)}/{len(HK_STOCKS)} 只港股")
    
    # 输出JSON供其他程序使用
    import json
    print('\n---JSON_START---')
    print(json.dumps(results, ensure_ascii=False))
