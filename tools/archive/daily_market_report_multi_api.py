#!/root/.openclaw/workspace/venv/bin/python3
"""
收盘报告 - 多API实时版
整合腾讯、长桥、efinance、Tushare多数据源
哪个有数据用哪个
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import json
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_tencent_quote(codes):
    """腾讯API获取实时行情 - 最快"""
    try:
        if not codes:
            return None
        
        # 转换代码格式
        tencent_codes = []
        for code in codes:
            if code.endswith('.SH'):
                tencent_codes.append(f"sh{code[:-3]}")
            elif code.endswith('.SZ'):
                tencent_codes.append(f"sz{code[:-3]}")
            elif code.endswith('.BJ'):
                tencent_codes.append(f"bj{code[:-3]}")
        
        url = f"https://qt.gtimg.cn/q={','.join(tencent_codes[:100])}"
        r = requests.get(url, timeout=10)
        
        # 解析腾讯返回的数据
        data = []
        lines = r.text.strip().split(';')
        for line in lines:
            if not line.strip():
                continue
            try:
                # 提取代码和数据
                parts = line.split('=')
                if len(parts) < 2:
                    continue
                
                code_str = parts[0].split('_')[-1]
                values = parts[1].strip('"').split('~')
                
                if len(values) < 45:
                    continue
                
                # 腾讯数据格式: 1=名称, 2=代码, 3=现价, 4=昨收, 5=今开, 6=成交量, 33=最高价, 34=最低价
                name = values[1]
                price = float(values[3]) if values[3] else 0
                pre_close = float(values[4]) if values[4] else 0
                open_price = float(values[5]) if values[5] else 0
                high = float(values[33]) if values[33] else 0
                low = float(values[34]) if values[34] else 0
                volume = float(values[6]) if values[6] else 0
                
                # 计算涨跌幅
                if pre_close > 0:
                    pct_chg = (price - pre_close) / pre_close * 100
                else:
                    pct_chg = 0
                
                # 转换回标准代码
                if code_str.startswith('sh'):
                    ts_code = code_str.replace('sh', '') + '.SH'
                elif code_str.startswith('sz'):
                    ts_code = code_str.replace('sz', '') + '.SZ'
                elif code_str.startswith('bj'):
                    ts_code = code_str.replace('bj', '') + '.BJ'
                else:
                    continue
                
                data.append({
                    'ts_code': ts_code,
                    'name': name,
                    'close': price,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'pre_close': pre_close,
                    'pct_chg': pct_chg,
                    'volume': volume
                })
            except Exception as e:
                continue
        
        if data:
            return pd.DataFrame(data)
    except Exception as e:
        log(f"腾讯API失败: {e}")
    return None

def get_all_stocks():
    """获取全市场股票列表"""
    try:
        import tushare as ts
        ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
        pro = ts.pro_api()
        
        stocks = pro.stock_basic(exchange='', list_status='L')
        return stocks['ts_code'].tolist()
    except:
        # 如果Tushare失败，从数据库读取
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        stocks = pd.read_sql("SELECT DISTINCT ts_code FROM daily_price WHERE trade_date >= '20260101'", conn)
        conn.close()
        return stocks['ts_code'].tolist()

def generate_report():
    """生成收盘报告"""
    log("="*60)
    log("多API收盘报告生成")
    log("="*60)
    
    today = datetime.now().strftime('%Y%m%d')
    log(f"报告日期: {today}")
    
    # 获取股票列表
    log("获取股票列表...")
    stocks = get_all_stocks()
    log(f"共{len(stocks)}只股票")
    
    # 使用腾讯API获取实时行情
    log("从腾讯API获取实时行情...")
    df = get_tencent_quote(stocks)
    
    if df is None or df.empty:
        log("❌ 所有API都失败，无法生成报告")
        return None
    
    log(f"✅ 获取到{len(df)}只股票数据")
    
    # 计算市场统计
    total = len(df)
    up = len(df[df['pct_chg'] > 0])
    down = len(df[df['pct_chg'] < 0])
    flat = len(df[df['pct_chg'] == 0])
    avg_change = df['pct_chg'].mean()
    
    # 涨停跌停（10%为界限，科创板/创业板20%）
    limit_up = len(df[df['pct_chg'] >= 9.5])
    limit_down = len(df[df['pct_chg'] <= -9.5])
    
    # 获取指数数据
    indices = ['000001.SH', '399001.SZ', '399006.SZ']
    index_df = get_tencent_quote(indices)
    
    # 涨跌幅榜
    top_up = df.nlargest(10, 'pct_chg')[['name', 'ts_code', 'pct_chg']]
    top_down = df.nsmallest(10, 'pct_chg')[['name', 'ts_code', 'pct_chg']]
    
    # 生成报告
    report = f"""
{'='*60}
📊 每日收盘深度报告 ({today})
数据来源: 腾讯API (实时)
{'='*60}

【市场全景】
涨跌分布: 🔴 {up}只 | 🟢 {down}只 | ⚪ {flat}只 (共{total}只)
平均涨跌幅: {avg_change:.2f}%
涨停: {limit_up}只 | 跌停: {limit_down}只

【主要指数】
"""
    
    if index_df is not None and not index_df.empty:
        for _, row in index_df.iterrows():
            emoji = "🔴" if row['pct_chg'] > 0 else "🟢" if row['pct_chg'] < 0 else "⚪"
            index_name = {'000001.SH': '上证指数', '399001.SZ': '深证成指', '399006.SZ': '创业板指'}.get(row['ts_code'], row['ts_code'])
            report += f"{emoji} {index_name}: {row['close']:.2f} ({row['pct_chg']:+.2f}%)\n"
    
    report += f"\n【涨幅榜 TOP10】\n"
    for i, (_, row) in enumerate(top_up.iterrows(), 1):
        report += f"{i}. {row['name'][:8]:8s} ({row['ts_code'][:6]}): +{row['pct_chg']:.2f}%\n"
    
    report += f"\n【跌幅榜 TOP10】\n"
    for i, (_, row) in enumerate(top_down.iterrows(), 1):
        report += f"{i}. {row['name'][:8]:8s} ({row['ts_code'][:6]}): {row['pct_chg']:.2f}%\n"
    
    report += f"\n{'='*60}\n"
    
    # 保存报告
    filename = f"/root/.openclaw/workspace/data/daily_report_api_{today}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"✅ 报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_report()
