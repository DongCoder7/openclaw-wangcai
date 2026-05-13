#!/root/.openclaw/workspace/venv/bin/python3
"""快速获取美股数据"""
import requests
import json

def get_eastmoney_us():
    """东方财富美股数据"""
    try:
        # 美股三大指数
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            'fltt': 2,
            'invt': 2,
            'fields': 'f1,f2,f3,f4,f12,f13,f14',
            'secids': '100.DJI,100.IXIC,100.INX'
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = {}
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                code = item.get('f12', '')
                name_map = {'DJI': '道琼斯', 'IXIC': '纳斯达克', 'INX': '标普500'}
                results[code] = {
                    'name': name_map.get(code, code),
                    'price': item.get('f2', 0) / 100,
                    'change': item.get('f4', 0) / 100,
                    'change_pct': item.get('f3', 0) / 100
                }
        return results
    except Exception as e:
        print(f'东方财富获取失败: {e}')
        return {}

def get_sina_us():
    """新浪财经美股数据"""
    try:
        url = "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/CN_MarketData.getList"
        params = {'page': 1, 'num': 30}
        response = requests.get(url, params=params, timeout=10)
        # JSONP解析
        text = response.text
        start = text.find('(') + 1
        end = text.rfind(')')
        data = json.loads(text[start:end])
        
        # 找三大指数
        indices = {}
        for item in data.get('data', []):
            symbol = item.get('symbol', '')
            if symbol in ['.DJI', '.IXIC', '.INX']:
                name_map = {'.DJI': '道琼斯', '.IXIC': '纳斯达克', '.INX': '标普500'}
                indices[symbol] = {
                    'name': name_map.get(symbol, symbol),
                    'price': float(item.get('price', 0)),
                    'change_pct': float(item.get('chg', 0))
                }
        return indices
    except Exception as e:
        print(f'新浪美股获取失败: {e}')
        return {}

# 尝试获取
print('=== 美股隔夜收盘 ===')
us_data = get_eastmoney_us()
if not us_data:
    us_data = get_sina_us()

for code, info in us_data.items():
    emoji = '🟢' if info['change_pct'] >= 0 else '🔴'
    print(f"{emoji} {info['name']}: {info['price']:.2f} ({info['change_pct']:+.2f}%)")

if not us_data:
    print('⚠️ 未能获取美股数据，请手动补充')
