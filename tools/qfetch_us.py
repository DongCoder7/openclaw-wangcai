#!/usr/bin/env python3
import requests, datetime

us_stocks = {
    '纳指100': 'usQQQ',
    '标普500': 'usSPY',
    '英伟达': 'usNVDA',
    '苹果': 'usAAPL',
    '微软': 'usMSFT',
    '特斯拉': 'usTSLA',
    '谷歌': 'usGOOGL',
    '亚马逊': 'usAMZN',
    'Meta': 'usMETA',
}

print(f'=== 美股行情 ({datetime.datetime.now().strftime("%H:%M:%S")}) ===')
codes = ','.join(us_stocks.values())
try:
    url = f'https://qt.gtimg.cn/q={codes}'
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
    if r.status_code == 200:
        lines = r.text.strip().split('\n')
        name_map = {v: k for k, v in us_stocks.items()}
        for line in lines:
            if '=' in line:
                parts = line.split('~')
                if len(parts) > 5:
                    code = parts[0].replace('v_','').replace('"','')
                    name = name_map.get(code, code)
                    price = parts[3]
                    pct = parts[32] if len(parts)>32 else parts[31]
                    print(f'{name}: {price} ({pct})')
except Exception as e:
    print(f'获取失败: {e}')