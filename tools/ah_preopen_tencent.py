#!/root/.openclaw/workspace/venv/bin/python3
"""
A+H股开盘前瞻报告 - 腾讯API版本（周六补全版）
"""
import requests
from datetime import datetime, timedelta

# ============ A股重点股票 ============
A_STOCKS = {
    '600887': {'name': '伊利股份', 'sector': '消费医药'},
    '600036': {'name': '招商银行', 'sector': '金融'},
    '603893': {'name': '瑞芯微', 'sector': '科技/半导体'},
    '300502': {'name': '新易盛', 'sector': 'AI算力'},
    '600900': {'name': '长江电力', 'sector': '新能源/资源'},
    '601012': {'name': '隆基绿能', 'sector': '新能源/资源'},
    '601318': {'name': '中国平安', 'sector': '金融'},
    '000858': {'name': '五 粮 液', 'sector': '消费医药'},
    '601899': {'name': '紫金矿业', 'sector': '新能源/资源'},
    '600519': {'name': '贵州茅台', 'sector': '消费医药'},
    '300760': {'name': '迈瑞医疗', 'sector': '科技/半导体'},
    '688981': {'name': '中芯国际', 'sector': '科技/半导体'},
    '688012': {'name': '中微公司', 'sector': '科技/半导体'},
    '300750': {'name': '宁德时代', 'sector': '新能源/资源'},
    '603019': {'name': '中科曙光', 'sector': 'AI算力'},
    '002230': {'name': '科大讯飞', 'sector': 'AI算力'},
    '000001': {'name': '平安银行', 'sector': '金融'},
    '300308': {'name': '中际旭创', 'sector': 'AI算力'},
    '601166': {'name': '兴业银行', 'sector': '金融'},
    '603259': {'name': '药明康德', 'sector': '消费医药'},
}

# ============ 港股重点股票 ============
H_STOCKS = {
    '00700': {'name': '腾讯控股', 'sector': '科技'},
    '09988': {'name': '阿里巴巴-W', 'sector': '科技'},
    '03690': {'name': '美团-W', 'sector': '科技'},
    '01810': {'name': '小米集团-W', 'sector': '科技'},
    '02318': {'name': '中国平安', 'sector': '金融地产'},
    '03988': {'name': '中国银行', 'sector': '金融地产'},
    '01109': {'name': '华润置地', 'sector': '金融地产'},
    '00688': {'name': '中国海外发展', 'sector': '金融地产'},
    '00883': {'name': '中国海洋石油', 'sector': '能源资源'},
    '00857': {'name': '中国石油股份', 'sector': '能源资源'},
    '01088': {'name': '中国神华', 'sector': '能源资源'},
    '00998': {'name': '中信银行', 'sector': '能源资源'},
    '02331': {'name': '李宁', 'sector': '消费医药'},
    '06690': {'name': '海尔智家', 'sector': '消费医药'},
    '09618': {'name': '京东集团-SW', 'sector': '消费医药'},
    '09999': {'name': '网易-S', 'sector': '消费医药'},
}

# ============ 美股重点指数 ============
US_INDICES = {
    '.DJI': {'name': '道琼斯'},
    '.IXIC': {'name': '纳斯达克'},
    '.INX': {'name': '标普500'},
}

def get_tencent_quote(codes):
    """通过腾讯API获取行情"""
    url = 'https://qt.gtimg.cn/q=' + ','.join(codes)
    resp = requests.get(url, timeout=10)
    resp.encoding = 'gbk'
    
    results = {}
    for line in resp.text.strip().split(';'):
        if not line.strip() or '~' not in line:
            continue
        # 提取变量名，如 v_sh600519="1~... 或 v_hk00700="100~...
        if '=' in line:
            var_part = line.split('=')[0]
            val_part = line.split('=', 1)[1].strip().strip('"')
        else:
            continue
        
        parts = val_part.split('~')
        if len(parts) < 45:
            continue
        
        code = parts[2]
        name = parts[1]
        price = float(parts[3])
        prev_close = float(parts[4])
        change_pct = (price - prev_close) / prev_close * 100 if prev_close > 0 else 0
        results[code] = {
            'name': name,
            'price': price,
            'change_pct': change_pct,
        }
    return results

def get_a_quotes():
    """获取A股行情"""
    codes = [f"sh{c}" if c.startswith('6') else f"sz{c}" for c in A_STOCKS.keys()]
    quotes = get_tencent_quote(codes)
    
    results = {}
    for code, info in A_STOCKS.items():
        if code in quotes:
            results[code] = {
                'name': info['name'],
                'sector': info['sector'],
                'price': quotes[code]['price'],
                'change_pct': quotes[code]['change_pct'],
            }
    return results

def get_h_quotes():
    """获取港股行情"""
    codes = [f"hk{c}" for c in H_STOCKS.keys()]
    quotes = get_tencent_quote(codes)
    
    results = {}
    for code, info in H_STOCKS.items():
        if code in quotes:
            results[code] = {
                'name': info['name'],
                'sector': info['sector'],
                'price': quotes[code]['price'],
                'change_pct': quotes[code]['change_pct'],
            }
    return results

def get_us_quotes():
    """获取美股指数行情 - 使用ETF数据映射"""
    try:
        # 腾讯API美股ETF格式
        us_codes = ['usQQQ', 'usSPY', 'usDIA']
        url = 'https://qt.gtimg.cn/q=' + ','.join(us_codes)
        resp = requests.get(url, timeout=10)
        resp.encoding = 'gbk'
        
        us_data = {}
        etf_map = {
            'QQQ.OQ': {'name': '纳斯达克', 'etf': '纳指100ETF'},
            'SPY.AM': {'name': '标普500', 'etf': '标普500ETF'},
            'DIA.AM': {'name': '道琼斯', 'etf': '道琼斯ETF'},
        }
        
        for line in resp.text.strip().split(';'):
            if not line.strip() or '~' not in line:
                continue
            if '=' in line:
                val_part = line.split('=', 1)[1].strip().strip('"')
            else:
                continue
            
            parts = val_part.split('~')
            if len(parts) < 45:
                continue
            
            code = parts[2]
            price = float(parts[3])
            prev_close = float(parts[4])
            change_pct = (price - prev_close) / prev_close * 100 if prev_close > 0 else 0
            
            if code in etf_map:
                us_data[etf_map[code]['name']] = {
                    'price': price,
                    'change_pct': change_pct,
                }
        
        return us_data
    except Exception as e:
        print(f"美股数据获取失败: {e}")
        return {}

def analyze_sectors(quotes):
    """分析板块强弱"""
    sectors = {}
    for code, q in quotes.items():
        s = q['sector']
        if s not in sectors:
            sectors[s] = {'stocks': [], 'sum_change': 0}
        sectors[s]['stocks'].append(q)
        sectors[s]['sum_change'] += q['change_pct']
    
    result = []
    for s, data in sectors.items():
        avg = data['sum_change'] / len(data['stocks'])
        up = sum(1 for st in data['stocks'] if st['change_pct'] > 0)
        result.append({
            'name': s,
            'avg': avg,
            'up': up,
            'total': len(data['stocks']),
            'stocks': sorted(data['stocks'], key=lambda x: x['change_pct'], reverse=True)
        })
    return sorted(result, key=lambda x: x['avg'], reverse=True)

def generate_report():
    """生成完整报告"""
    today = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M')
    weekday = datetime.now().strftime('%A')
    
    # 判断是否为交易日
    is_trading_day = weekday not in ['Saturday', 'Sunday']
    
    # 获取数据
    print("📊 获取A股行情...")
    a_quotes = get_a_quotes()
    print(f"   ✅ A股: {len(a_quotes)}/{len(A_STOCKS)}")
    
    print("📊 获取港股行情...")
    h_quotes = get_h_quotes()
    print(f"   ✅ 港股: {len(h_quotes)}/{len(H_STOCKS)}")
    
    print("📊 获取美股数据...")
    us_quotes = get_us_quotes()
    print(f"   ✅ 美股: {len(us_quotes)}个指数")
    
    # 分析板块
    a_sectors = analyze_sectors(a_quotes)
    h_sectors = analyze_sectors(h_quotes)
    
    # 涨跌统计
    a_up = sum(1 for q in a_quotes.values() if q['change_pct'] > 0)
    a_down = sum(1 for q in a_quotes.values() if q['change_pct'] < 0)
    a_flat = len(a_quotes) - a_up - a_down
    
    h_up = sum(1 for q in h_quotes.values() if q['change_pct'] > 0)
    h_down = sum(1 for q in h_quotes.values() if q['change_pct'] < 0)
    h_flat = len(h_quotes) - h_up - h_down
    
    report = f"""📊 A+H股开盘前瞻报告

生成时间: {today} {time_str}（{weekday}）
{"⚠️ 注意：今日为非交易日，以下为上一交易日（周五）收盘数据参考" if not is_trading_day else ""}
数据来源: 腾讯财经API + 东方财富API

═══════════════════════════════════════

🇺🇸 一、隔夜美股回顾（周五收盘）
"""
    
    if us_quotes:
        for name, data in us_quotes.items():
            emoji = '📈' if data['change_pct'] > 0 else '📉' if data['change_pct'] < 0 else '➖'
            report += f"• {emoji} {name}: {data['change_pct']:+.2f}%\n"
    else:
        report += "• 美股数据获取中...\n"
    
    report += f"""
═══════════════════════════════════════

🇨🇳 二、A股回顾（周五收盘）

情绪面: 涨跌比 {a_up}:{a_down}:{a_flat}（涨:跌:平）

板块强弱:
"""
    
    for i, s in enumerate(a_sectors, 1):
        emoji = '🟢' if s['avg'] >= 0 else '🔴'
        report += f"{i}. {emoji} {s['name']}: {s['avg']:+.2f}% ({s['up']}/{s['total']}涨)\n"
        for st in s['stocks'][:2]:
            report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    
    # A股涨跌幅排行
    a_sorted = sorted(a_quotes.values(), key=lambda x: x['change_pct'], reverse=True)
    report += "\n📈 涨幅前三:\n"
    for st in a_sorted[:3]:
        report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    report += "\n📉 跌幅前三:\n"
    for st in a_sorted[-3:]:
        report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    
    report += f"""
═══════════════════════════════════════

🇭🇰 三、港股回顾（周五收盘）

情绪面: 涨跌比 {h_up}:{h_down}:{h_flat}（涨:跌:平）

板块强弱:
"""
    
    for i, s in enumerate(h_sectors, 1):
        emoji = '🟢' if s['avg'] >= 0 else '🔴'
        report += f"{i}. {emoji} {s['name']}: {s['avg']:+.2f}% ({s['up']}/{s['total']}涨)\n"
        for st in s['stocks'][:2]:
            report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    
    # 港股涨跌幅排行
    h_sorted = sorted(h_quotes.values(), key=lambda x: x['change_pct'], reverse=True)
    report += "\n📈 涨幅前三:\n"
    for st in h_sorted[:3]:
        report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    report += "\n📉 跌幅前三:\n"
    for st in h_sorted[-3:]:
        report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    
    report += """
═══════════════════════════════════════

🎯 四、市场策略建议

【A股】
"""
    
    # 根据数据生成策略
    if a_sorted:
        top_gainer = a_sorted[0]
        top_loser = a_sorted[-1]
        report += f"• 领涨: {top_gainer['name']}(+{top_gainer['change_pct']:.2f}%)，关注板块扩散效应\n"
        report += f"• 领跌: {top_loser['name']}({top_loser['change_pct']:.2f}%)，观察是否错杀\n"
    
    if a_sectors:
        best_sector = a_sectors[0]
        worst_sector = a_sectors[-1]
        report += f"• 最强板块: {best_sector['name']}({best_sector['avg']:+.2f}%)\n"
        report += f"• 最弱板块: {worst_sector['name']}({worst_sector['avg']:+.2f}%)\n"
    
    report += """
【港股】
"""
    
    if h_sorted:
        top_gainer = h_sorted[0]
        top_loser = h_sorted[-1]
        report += f"• 领涨: {top_gainer['name']}(+{top_gainer['change_pct']:.2f}%)\n"
        report += f"• 领跌: {top_loser['name']}({top_loser['change_pct']:.2f}%)\n"
    
    report += """
【跨市场联动】
"""
    
    if us_quotes:
        nasdaq = us_quotes.get('纳斯达克', {})
        if nasdaq.get('change_pct', 0) < -1:
            report += "• 美股科技股承压，注意A股AI/半导体板块情绪\n"
        elif nasdaq.get('change_pct', 0) > 1:
            report += "• 美股科技股强势，A股AI/半导体或有映射\n"
        else:
            report += "• 美股中性，A股按自身逻辑运行\n"
    
    report += """
═══════════════════════════════════════

⚠️ 免责声明: 本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。

"""
    
    print(report)
    return report

if __name__ == '__main__':
    generate_report()
