#!/root/.openclaw/workspace/venv/bin/python3
"""
A股收盘报告 - 简化版 (备用)
使用腾讯API获取指数和个股数据
"""
import sys
import requests
import json
from datetime import datetime

REPORT_DIR = '/root/.openclaw/workspace/data'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_index_data():
    """获取官方指数"""
    url = 'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688,sh000016,sh000905'
    r = requests.get(url, timeout=10)
    indices = {}
    name_map = {
        'sh000001': '上证指数',
        'sz399001': '深证成指',
        'sz399006': '创业板指',
        'sh000688': '科创50',
        'sh000016': '上证50',
        'sh000905': '中证500'
    }
    for line in r.text.strip().split(';'):
        if not line.strip():
            continue
        parts = line.split('=')
        if len(parts) < 2:
            continue
        code = parts[0].split('_')[-1]
        values = parts[1].strip('"').split('~')
        if len(values) > 32:
            name = name_map.get(code, code)
            price = float(values[3])
            pre_close = float(values[4])
            open_price = float(values[5])
            high = float(values[33])
            low = float(values[34])
            volume = float(values[36])
            amount = float(values[37])
            change_pct = float(values[32])
            change = price - pre_close
            indices[code] = {
                'name': name, 'price': price, 'pre_close': pre_close,
                'open': open_price, 'high': high, 'low': low,
                'volume': volume, 'amount': amount,
                'change': change, 'change_pct': change_pct
            }
    return indices

def get_us_market():
    url = 'https://qt.gtimg.cn/q=usDJI,usIXIC,usINX'
    r = requests.get(url, timeout=10)
    data = {}
    for line in r.text.strip().split(';'):
        if not line.strip():
            continue
        parts = line.split('=')
        if len(parts) < 2:
            continue
        code = parts[0].split('_')[-1]
        values = parts[1].strip('"').split('~')
        if len(values) > 30:
            name_map = {'usDJI': '道琼斯', 'usIXIC': '纳斯达克', 'usINX': '标普500'}
            name = name_map.get(code, code)
            price = float(values[3])
            pre_close = float(values[4])
            change_pct = (price - pre_close) / pre_close * 100 if pre_close > 0 else 0
            change = price - pre_close
            data[code] = {'name': name, 'price': price, 'change': change, 'change_pct': change_pct}
    return data

def get_hk_market():
    url = 'https://qt.gtimg.cn/q=hkHSI,hkHSTECH'
    r = requests.get(url, timeout=10)
    data = {}
    for line in r.text.strip().split(';'):
        if not line.strip():
            continue
        parts = line.split('=')
        if len(parts) < 2:
            continue
        values = parts[1].strip('"').split('~')
        if len(values) > 30:
            name = values[1]
            price = float(values[3])
            pre_close = float(values[4])
            change_pct = (price - pre_close) / pre_close * 100 if pre_close > 0 else 0
            change = price - pre_close
            data[name] = {'price': price, 'change': change, 'change_pct': change_pct}
    return data

def get_a_stock_list():
    """获取A股涨跌统计 - 通过腾讯批量接口"""
    # 获取主要指数成分股来估算市场情绪
    # 上证指数成分股
    url = 'https://qt.gtimg.cn/q=sh000001'
    r = requests.get(url, timeout=10)
    
    # 直接访问腾讯A股涨跌统计API
    try:
        # 获取部分活跃股票来统计
        test_codes = [
            'sh600519','sh601318','sh600036','sh601012','sh600276',
            'sz000858','sz002594','sz300750','sz300059','sz000001',
            'sh688981','sh688012','sh688008','sh688111','sh688036'
        ]
        url = 'https://qt.gtimg.cn/q=' + ','.join(test_codes)
        r = requests.get(url, timeout=10)
        stocks = []
        for line in r.text.strip().split(';'):
            if not line.strip():
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            code = parts[0].split('_')[-1]
            values = parts[1].strip('"').split('~')
            if len(values) > 32:
                price = float(values[3])
                pre = float(values[4])
                change_pct = float(values[32])
                volume = float(values[36])
                amount = float(values[37])
                stocks.append({
                    'code': code, 'price': price, 'pre': pre,
                    'change_pct': change_pct, 'volume': volume, 'amount': amount
                })
        return stocks
    except Exception as e:
        log(f"获取个股失败: {e}")
        return []

def generate_simple_report():
    today = datetime.now().strftime('%Y%m%d')
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    log("获取外围市场...")
    us = get_us_market()
    hk = get_hk_market()
    
    log("获取A股指数...")
    indices = get_index_data()
    
    log("获取A股样本...")
    stocks = get_a_stock_list()
    
    # 估算市场情绪
    up_count = sum(1 for s in stocks if s['change_pct'] > 0)
    down_count = sum(1 for s in stocks if s['change_pct'] < 0)
    total_sample = len(stocks)
    
    # 样本股涨跌幅榜
    top_up = sorted([s for s in stocks if s['change_pct'] > 0], key=lambda x: x['change_pct'], reverse=True)[:5]
    top_down = sorted([s for s in stocks if s['change_pct'] < 0], key=lambda x: x['change_pct'])[:5]
    
    report = f"""{'='*70}
📊 A股收盘报告 ({today_str})
{'='*70}

【一、外围市场】

🇺🇸 美股隔夜:
"""
    for code, d in us.items():
        emoji = "🔴" if d['change'] > 0 else "🟢"
        report += f"{emoji} {d['name']}: {d['price']:.2f} ({d['change']:+.2f}, {d['change_pct']:+.2f}%)\n"
    
    report += f"""
🇭🇰 港股收盘:
"""
    for name, d in hk.items():
        emoji = "🔴" if d['change'] > 0 else "🟢"
        report += f"{emoji} {name}: {d['price']:.2f} ({d['change']:+.2f}, {d['change_pct']:+.2f}%)\n"
    
    report += f"""
【二、A股官方指数】
"""
    for code in ['sh000001', 'sh000016', 'sz399001', 'sz399006', 'sh000688', 'sh000905']:
        if code in indices:
            d = indices[code]
            emoji = "🔴" if d['change_pct'] > 0 else "🟢"
            report += f"{emoji} {d['name']}: {d['price']:.2f} ({d['change']:+.2f}, {d['change_pct']:+.2f}%)  成交额:{d['amount']/1e8:.0f}亿\n"
    
    report += f"""
【三、市场情绪估算】(基于{total_sample}只活跃样本股)

🔴 上涨: {up_count}只 | 🟢 下跌: {down_count}只
样本股平均涨跌幅: {sum(s['change_pct'] for s in stocks)/len(stocks):+.2f}%

🔥 样本领涨:
"""
    for s in top_up:
        report += f"• {s['code']}: {s['change_pct']:+.2f}%\n"
    
    report += f"""
❄️ 样本领跌:
"""
    for s in top_down:
        report += f"• {s['code']}: {s['change_pct']:+.2f}%\n"
    
    # 趋势判断
    main_index = indices.get('sh000001', {})
    main_change = main_index.get('change_pct', 0)
    trend = "上涨" if main_change > 0.5 else "下跌" if main_change < -0.5 else "震荡"
    
    report += f"""
【四、今日展望】

📊 市场概况: 上证指数 {trend} ({main_change:+.2f}%)
💡 策略建议: {'逢低做多' if main_change > 0 else '震荡观望' if main_change > -0.5 else '控制仓位'}
⚠️ 风险提示: 外围市场波动，注意地缘政治风险

{'='*70}
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
数据来源: 腾讯API | 长桥API Token过期，使用简化版报告
{'='*70}
"""
    
    filename = f"{REPORT_DIR}/daily_report_{today}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"✅ 简化报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_simple_report()
