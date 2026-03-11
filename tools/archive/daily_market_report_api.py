#!/root/.openclaw/workspace/venv/bin/python3
"""
收盘报告 - API实时计算版
完全依赖Tushare API，不查询本地数据库
"""
import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

TUSHARE_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_pro_api():
    ts.set_token(TUSHARE_TOKEN)
    return ts.pro_api()

def get_latest_trade_date(pro):
    """获取最近交易日"""
    today = datetime.now().strftime('%Y%m%d')
    df = pro.trade_cal(exchange='SSE', start_date=(datetime.now()-timedelta(days=10)).strftime('%Y%m%d'), end_date=today)
    df = df[df['is_open']==1]
    return df['cal_date'].iloc[-1]

def get_market_overview(pro, trade_date):
    """市场全景 - 通过每日行情API"""
    log(f"获取市场全景 {trade_date}...")
    
    df = pro.daily(trade_date=trade_date)
    time.sleep(0.35)
    
    if df.empty:
        return None
    
    # 计算涨跌幅
    up = len(df[df['pct_chg'] > 0])
    down = len(df[df['pct_chg'] < 0])
    flat = len(df[df['pct_chg'] == 0])
    avg_change = df['pct_chg'].mean()
    
    # 涨停跌停统计
    limit_up = len(df[df['pct_chg'] >= 9.5])
    limit_down = len(df[df['pct_chg'] <= -9.5])
    
    return {
        'date': trade_date,
        'total': len(df),
        'up': up,
        'down': down,
        'flat': flat,
        'avg_change': avg_change,
        'limit_up': limit_up,
        'limit_down': limit_down
    }

def get_index_performance(pro, trade_date):
    """指数表现"""
    log(f"获取指数表现...")
    
    indices = {
        '000001.SH': '上证指数',
        '399001.SZ': '深证成指',
        '399006.SZ': '创业板指',
        '000300.SH': '沪深300',
        '000905.SH': '中证500'
    }
    
    index_data = []
    for code, name in indices.items():
        try:
            df = pro.index_daily(ts_code=code, trade_date=trade_date)
            time.sleep(0.1)
            if not df.empty:
                index_data.append({
                    'name': name,
                    'code': code,
                    'close': df.iloc[0]['close'],
                    'change': df.iloc[0]['pct_chg']
                })
        except:
            continue
    
    return index_data

def get_sector_performance(pro, trade_date):
    """板块表现 - 通过行业指数"""
    log(f"获取板块表现...")
    
    # 获取行业指数
    sectors = [
        ('801010.SI', '农林牧渔'), ('801020.SI', '采掘'), ('801030.SI', '化工'),
        ('801040.SI', '钢铁'), ('801050.SI', '有色金属'), ('801080.SI', '电子'),
        ('801110.SI', '家用电器'), ('801120.SI', '食品饮料'), ('801130.SI', '纺织服装'),
        ('801140.SI', '轻工制造'), ('801150.SI', '医药生物'), ('801160.SI', '公用事业'),
        ('801170.SI', '交通运输'), ('801180.SI', '房地产'), ('801200.SI', '商业贸易'),
        ('801210.SI', '休闲服务'), ('801230.SI', '综合'), ('801710.SI', '建筑材料'),
        ('801720.SI', '建筑装饰'), ('801730.SI', '电气设备'), ('801740.SI', '机械设备'),
        ('801750.SI', '国防军工'), ('801760.SI', '计算机'), ('801770.SI', '传媒'),
        ('801780.SI', '通信'), ('801790.SI', '银行'), ('801880.SI', '汽车'),
        ('801890.SI', '非银金融')
    ]
    
    sector_data = []
    for code, name in sectors:
        try:
            df = pro.index_daily(ts_code=code, trade_date=trade_date)
            time.sleep(0.05)
            if not df.empty:
                sector_data.append({
                    'name': name,
                    'change': df.iloc[0]['pct_chg']
                })
        except:
            continue
    
    # 按涨幅排序
    sector_data.sort(key=lambda x: x['change'], reverse=True)
    return sector_data[:10]  # 前10板块

def get_top_stocks(pro, trade_date):
    """涨跌幅榜"""
    log(f"获取涨跌幅榜...")
    
    df = pro.daily(trade_date=trade_date)
    time.sleep(0.35)
    
    if df.empty:
        return None, None
    
    # 获取股票名称
    stocks = pro.stock_basic(exchange='', list_status='L')[['ts_code', 'name']]
    df = df.merge(stocks, on='ts_code', how='left')
    
    # 涨幅前10
    top_up = df.nlargest(10, 'pct_chg')[['ts_code', 'name', 'pct_chg', 'vol']]
    # 跌幅前10
    top_down = df.nsmallest(10, 'pct_chg')[['ts_code', 'name', 'pct_chg', 'vol']]
    
    return top_up, top_down

def get_north_flow(pro, trade_date):
    """北向资金流向"""
    log(f"获取北向资金...")
    
    try:
        df = pro.moneyflow_hsgt(trade_date=trade_date)
        time.sleep(0.35)
        
        if not df.empty:
            return {
                'buy': df.iloc[0]['buy_amount'],
                'sell': df.iloc[0]['sell_amount'],
                'net': df.iloc[0]['net_amount']
            }
    except:
        pass
    
    return None

def generate_report():
    """生成完整收盘报告"""
    log("="*60)
    log("生成API实时收盘报告")
    log("="*60)
    
    pro = get_pro_api()
    
    # 获取最近交易日
    trade_date = get_latest_trade_date(pro)
    log(f"报告日期: {trade_date}")
    
    # 收集数据
    market = get_market_overview(pro, trade_date)
    indices = get_index_performance(pro, trade_date)
    sectors = get_sector_performance(pro, trade_date)
    top_up, top_down = get_top_stocks(pro, trade_date)
    north = get_north_flow(pro, trade_date)
    
    # 生成报告
    report = f"""
{'='*60}
📊 每日收盘深度报告 ({trade_date})
{'='*60}

【市场全景】
涨跌分布: 🔴 {market['up']}只 | 🟢 {market['down']}只 | ⚪ {market['flat']}只 (共{market['total']}只)
平均涨跌幅: {market['avg_change']:.2f}%
涨停: {market['limit_up']}只 | 跌停: {market['limit_down']}只

【主要指数】
"""
    
    for idx in indices:
        emoji = "🔴" if idx['change'] > 0 else "🟢" if idx['change'] < 0 else "⚪"
        report += f"{emoji} {idx['name']}: {idx['close']:.2f} ({idx['change']:+.2f}%)\n"
    
    report += f"\n【领涨板块 TOP5】\n"
    for i, sec in enumerate(sectors[:5], 1):
        emoji = "🔴" if sec['change'] > 0 else "🟢"
        report += f"{i}. {sec['name']}: {sec['change']:+.2f}% {emoji}\n"
    
    report += f"\n【领跌板块 TOP5】\n"
    for i, sec in enumerate(sectors[-5:], 1):
        emoji = "🟢" if sec['change'] < 0 else "🔴"
        report += f"{i}. {sec['name']}: {sec['change']:+.2f}% {emoji}\n"
    
    report += f"\n【涨幅榜 TOP10】\n"
    for i, row in top_up.iterrows():
        report += f"{row['name'][:8]:8s} ({row['ts_code'][:6]}): +{row['pct_chg']:.2f}%\n"
    
    report += f"\n【跌幅榜 TOP10】\n"
    for i, row in top_down.iterrows():
        report += f"{row['name'][:8]:8s} ({row['ts_code'][:6]}): {row['pct_chg']:.2f}%\n"
    
    if north:
        emoji = "🔴流入" if north['net'] > 0 else "🟢流出"
        report += f"\n【北向资金】{emoji}: {north['net']/10000:.1f}亿\n"
    
    report += f"\n{'='*60}\n"
    
    # 保存报告
    filename = f"/root/.openclaw/workspace/data/daily_report_api_{trade_date}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_report()
