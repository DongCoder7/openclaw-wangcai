#!/root/.openclaw/workspace/venv/bin/python3
"""腾讯API获取美股指数行情"""
import requests
import json

def get_us_index(symbol):
    """获取美股指数"""
    try:
        url = f'https://qt.gtimg.cn/q={symbol}'
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        
        data_str = response.text
        if not data_str or '~' not in data_str:
            return None
        
        parts = data_str.split('~')
        if len(parts) < 45:
            return None
        
        return {
            'name': parts[1],
            'price': float(parts[3]),
            'change_pct': float(parts[32]),
        }
    except Exception as e:
        print(f'获取美股指数失败: {e}')
        return None

# 美股三大指数
indices = {
    '.DJI': '道琼斯',
    '.IXIC': '纳斯达克',
    '.INX': '标普500'
}

print('=== 美股隔夜收盘 ===')
for symbol, name in indices.items():
    quote = get_us_index(symbol)
    if quote:
        emoji = '🟢' if quote['change_pct'] >= 0 else '🔴'
        print(f"{emoji} {name}: {quote['price']:.2f} ({quote['change_pct']:+.2f}%)")

# 热门中概
print('\n=== 热门中概股 ===')
us_stocks = {
    'BABA': '阿里巴巴',
    'JD': '京东',
    'PDD': '拼多多',
    'NIO': '蔚来',
    'LI': '理想汽车',
    'XPEV': '小鹏汽车',
    'TSLA': '特斯拉'
}

for symbol, name in us_stocks.items():
    quote = get_us_index(symbol)
    if quote:
        emoji = '🟢' if quote['change_pct'] >= 0 else '🔴'
        print(f"{emoji} {name}({symbol}): {quote['price']:.2f} ({quote['change_pct']:+.2f}%)")
