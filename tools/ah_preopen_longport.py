#!/root/.openclaw/workspace/venv/bin/python3
"""
A+H股开盘前瞻报告 - 官方长桥API版本 (longport SDK)
每日9:15-9:25执行，生成开盘策略报告
"""

import os
import sys
from datetime import datetime, timedelta

# A股重点板块监控
A_STOCK_SECTORS = {
    '科技/半导体': ['688981', '688012', '603893', '300760'],
    'AI算力': ['300308', '300502', '002230', '603019'],
    '金融': ['600036', '000001', '601318', '601166'],
    '消费医药': ['600519', '000858', '600887', '603259'],
    '新能源/资源': ['300750', '601012', '601899', '600900'],
}

# 港股重点板块监控
H_STOCK_SECTORS = {
    '科技': ['00700', '09988', '03690', '01810'],
    '金融地产': ['02318', '03988', '01109', '00688'],
    '能源资源': ['00883', '00857', '01088', '00998'],
    '消费医药': ['02331', '06690', '09618', '09999'],
}

# 美股指数映射 (ETF)
US_INDICES = {
    'QQQ': '纳斯达克',
    'SPY': '标普500',
    'DIA': '道琼斯',
}


def format_symbol(code, market='CN'):
    code = code.strip().upper()
    if market == 'CN':
        if code.startswith('6') or code.startswith('5'):
            return f"{code}.SH"
        else:
            return f"{code}.SZ"
    elif market == 'HK':
        return f"{code}.HK"
    elif market == 'US':
        return f"{code}.US"
    return code


def get_quotes_longport(codes, market='CN'):
    """使用官方longport SDK获取行情"""
    from longport.openapi import Config, QuoteContext
    
    config = Config.from_env()
    ctx = QuoteContext(config)
    
    symbols = [format_symbol(c, market) for c in codes]
    
    quotes = {}
    try:
        q_results = ctx.quote(symbols)
        s_results = ctx.static_info(symbols)
        
        static_map = {s.symbol: s for s in s_results}
        
        for q in q_results:
            code = q.symbol.split('.')[0]
            static = static_map.get(q.symbol)
            name = ''
            if static:
                name = static.name_cn or static.name_en or static.name_hk or ''
            
            change_pct = (q.last_done - q.prev_close) / q.prev_close * 100 if q.prev_close > 0 else 0
            
            quotes[code] = {
                'name': name,
                'price': q.last_done,
                'change_pct': change_pct,
                'prev_close': q.prev_close,
                'volume': q.volume,
            }
    except Exception as e:
        print(f"   ⚠️ longport获取失败: {e}")
    
    return quotes


def get_us_quotes_tencent():
    """通过腾讯API获取美股ETF行情"""
    import requests
    try:
        us_codes = ['usQQQ', 'usSPY', 'usDIA']
        url = 'https://qt.gtimg.cn/q=' + ','.join(us_codes)
        resp = requests.get(url, timeout=10)
        resp.encoding = 'gbk'
        
        us_data = {}
        etf_map = {
            'QQQ.OQ': '纳斯达克',
            'SPY.AM': '标普500',
            'DIA.AM': '道琼斯',
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
                us_data[etf_map[code]] = {
                    'price': price,
                    'change_pct': change_pct,
                }
        
        return us_data
    except Exception as e:
        print(f"美股数据获取失败: {e}")
        return {}


def analyze_sectors(quotes, sector_map):
    """分析板块强弱"""
    sector_stats = {}
    for sector_name, codes in sector_map.items():
        sector_quotes = [quotes[c] for c in codes if c in quotes]
        if sector_quotes:
            avg_change = sum(q['change_pct'] for q in sector_quotes) / len(sector_quotes)
            up_count = sum(1 for q in sector_quotes if q['change_pct'] > 0)
            sector_stats[sector_name] = {
                'avg_change': avg_change,
                'up_count': up_count,
                'total': len(sector_quotes),
                'stocks': sector_quotes
            }
    
    sorted_sectors = sorted(sector_stats.items(), key=lambda x: x[1]['avg_change'], reverse=True)
    return dict(sorted_sectors)


def generate_report(a_quotes, h_quotes, us_quotes):
    """生成开盘前瞻报告"""
    today = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M')
    weekday = datetime.now().strftime('%A')
    
    # 分析板块
    a_sectors = analyze_sectors(a_quotes, A_STOCK_SECTORS)
    h_sectors = analyze_sectors(h_quotes, H_STOCK_SECTORS)
    
    # 涨跌统计
    a_up = sum(1 for q in a_quotes.values() if q['change_pct'] > 0)
    a_down = sum(1 for q in a_quotes.values() if q['change_pct'] < 0)
    a_flat = len(a_quotes) - a_up - a_down
    
    h_up = sum(1 for q in h_quotes.values() if q['change_pct'] > 0)
    h_down = sum(1 for q in h_quotes.values() if q['change_pct'] < 0)
    h_flat = len(h_quotes) - h_up - h_down
    
    report = f"""📊 A+H股开盘前瞻报告

生成时间: {today} {time_str}（{weekday}）
数据来源: 长桥API (longport) + 腾讯财经API

═══════════════════════════════════════

🇺🇸 一、隔夜美股回顾（周四收盘）
"""
    
    if us_quotes:
        for name, data in us_quotes.items():
            emoji = '📈' if data['change_pct'] > 0 else '📉' if data['change_pct'] < 0 else '➖'
            report += f"• {emoji} {name}: {data['change_pct']:+.2f}%\n"
    else:
        report += "• 美股数据获取中...\n"
    
    report += f"""
═══════════════════════════════════════

🇨🇳 二、A股开盘前瞻（集合竞价）

情绪面: 涨跌比 {a_up}:{a_down}:{a_flat}（涨:跌:平）

板块强弱:
"""
    
    for i, (sector, stats) in enumerate(a_sectors.items(), 1):
        emoji = '🟢' if stats['avg_change'] >= 0 else '🔴'
        report += f"{i}. {emoji} {sector}: {stats['avg_change']:+.2f}% ({stats['up_count']}/{stats['total']}涨)\n"
        for st in stats['stocks'][:2]:
            report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    
    a_sorted = sorted(a_quotes.values(), key=lambda x: x['change_pct'], reverse=True)
    report += "\n📈 涨幅前三:\n"
    for st in a_sorted[:3]:
        report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    report += "\n📉 跌幅前三:\n"
    for st in a_sorted[-3:]:
        report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    
    report += f"""
═══════════════════════════════════════

🇭🇰 三、港股开盘前瞻（集合竞价）

情绪面: 涨跌比 {h_up}:{h_down}:{h_flat}（涨:跌:平）

板块强弱:
"""
    
    for i, (sector, stats) in enumerate(h_sectors.items(), 1):
        emoji = '🟢' if stats['avg_change'] >= 0 else '🔴'
        report += f"{i}. {emoji} {sector}: {stats['avg_change']:+.2f}% ({stats['up_count']}/{stats['total']}涨)\n"
        for st in stats['stocks'][:2]:
            report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
    
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
    if a_sorted:
        top_gainer = a_sorted[0]
        top_loser = a_sorted[-1]
        report += f"• 领涨: {top_gainer['name']}(+{top_gainer['change_pct']:.2f}%)，关注板块扩散效应\n"
        report += f"• 领跌: {top_loser['name']}({top_loser['change_pct']:.2f}%)，观察是否错杀\n"
    
    if a_sectors:
        best = list(a_sectors.items())[0]
        worst = list(a_sectors.items())[-1]
        report += f"• 最强板块: {best[0]}({best[1]['avg_change']:+.2f}%)\n"
        report += f"• 最弱板块: {worst[0]}({worst[1]['avg_change']:+.2f}%)\n"
    
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
    
    return report


def main():
    print('=' * 60)
    print('  A+H股开盘前瞻报告 - 长桥API (longport SDK)')
    print('=' * 60)
    
    # 获取A股数据
    print('\n📊 获取A股行情...')
    a_codes = list(set([c for codes in A_STOCK_SECTORS.values() for c in codes]))
    a_quotes = get_quotes_longport(a_codes, market='CN')
    print(f'   ✅ A股: {len(a_quotes)}/{len(a_codes)}')
    
    # 获取港股数据
    print('\n📊 获取港股行情...')
    h_codes = list(set([c for codes in H_STOCK_SECTORS.values() for c in codes]))
    h_quotes = get_quotes_longport(h_codes, market='HK')
    print(f'   ✅ 港股: {len(h_quotes)}/{len(h_codes)}')
    
    # 获取美股数据（腾讯备用）
    print('\n📊 获取美股数据...')
    us_quotes = get_us_quotes_tencent()
    print(f'   ✅ 美股: {len(us_quotes)}个指数')
    
    # 生成报告
    print('\n📝 生成报告中...')
    report = generate_report(a_quotes, h_quotes, us_quotes)
    
    # 保存
    today = datetime.now().strftime('%Y-%m-%d')
    output_dir = os.path.expanduser('~/.openclaw/workshop/data')
    os.makedirs(output_dir, exist_ok=True)
    filename = f'{output_dir}/ah_preopen_longport_{today}.md'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'✅ 报告已保存: {filename}')
    
    print('\n' + report)
    return report


if __name__ == '__main__':
    main()
