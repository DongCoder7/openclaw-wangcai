#!/root/.openclaw/workspace/venv/bin/python3
"""
收盘报告 - 完整版 v3
API优先级: 长桥 > efinance > 腾讯
包含: 指数、板块、驱动因子、资金流向、涨跌幅榜、市场展望
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import json
import sys
import os
import time

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
REPORT_DIR = '/root/.openclaw/workspace/data'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_longbridge_token():
    """获取长桥token"""
    try:
        env_file = '/root/.openclaw/workspace/.longbridge.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('LONGPORT_ACCESS_TOKEN='):
                        token = line.split('=', 1)[1].strip().strip('"\'')
                        return token
    except Exception as e:
        log(f"长桥token读取失败: {e}")
    return None

def get_longbridge_quote(codes):
    """长桥API - 首选"""
    token = get_longbridge_token()
    if not token:
        return None
    
    try:
        lb_codes = []
        for code in codes:
            if code.endswith('.SH'):
                lb_codes.append(f"SH.{code[:-3]}")
            elif code.endswith('.SZ'):
                lb_codes.append(f"SZ.{code[:-3]}")
            elif code.endswith('.BJ'):
                lb_codes.append(f"BJ.{code[:-3]}")
        
        all_data = []
        batch_size = 100
        
        # 尝试多个域名
        domains = [
            'https://openapi.longbridge.sg',
            'https://openapi.longbridge.app',
            'https://openapi.lbkrs.com'
        ]
        
        for domain in domains:
            try:
                for i in range(0, len(lb_codes), batch_size):
                    batch = lb_codes[i:i+batch_size]
                    url = f"{domain}/v1/quote/realtime"
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                    payload = {"symbols": batch}
                    
                    r = requests.post(url, headers=headers, json=payload, timeout=10)
                    if r.status_code == 200:
                        result = r.json()
                        if result.get('code') == 0 and 'data' in result:
                            for item in result['data']:
                                try:
                                    symbol = item.get('symbol', '')
                                    if symbol.startswith('SH.'):
                                        ts_code = symbol.replace('SH.', '') + '.SH'
                                    elif symbol.startswith('SZ.'):
                                        ts_code = symbol.replace('SZ.', '') + '.SZ'
                                    elif symbol.startswith('BJ.'):
                                        ts_code = symbol.replace('BJ.', '') + '.BJ'
                                    else:
                                        continue
                                    
                                    price = item.get('last_done', 0) or item.get('price', 0)
                                    pre_close = item.get('prev_close', 0)
                                    
                                    all_data.append({
                                        'ts_code': ts_code,
                                        'name': item.get('name', ''),
                                        'close': price,
                                        'open': item.get('open', 0),
                                        'high': item.get('high', 0),
                                        'low': item.get('low', 0),
                                        'pre_close': pre_close,
                                        'pct_chg': ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0,
                                        'volume': item.get('volume', 0),
                                        'amount': item.get('turnover', 0)
                                    })
                                except:
                                    continue
                    time.sleep(0.3)
                
                if all_data:
                    return pd.DataFrame(all_data)
            except:
                continue
    except Exception as e:
        log(f"长桥API失败: {e}")
    return None

def get_efinance_quote():
    """efinance API - 次选，获取全市场"""
    try:
        import efinance as ef
        df = ef.stock.get_realtime_quotes()
        
        if df is not None and not df.empty:
            data = []
            for _, row in df.iterrows():
                try:
                    code = str(row.get('股票代码', ''))
                    if code.startswith('6'):
                        ts_code = code + '.SH'
                    elif code.startswith('0') or code.startswith('3'):
                        ts_code = code + '.SZ'
                    elif code.startswith('8') or code.startswith('4'):
                        ts_code = code + '.BJ'
                    else:
                        continue
                    
                    price = float(row.get('最新价', 0))
                    pre_close = float(row.get('昨日收盘价', 0))
                    
                    data.append({
                        'ts_code': ts_code,
                        'name': row.get('股票名称', ''),
                        'close': price,
                        'open': float(row.get('今日开盘价', 0)),
                        'high': float(row.get('最高', 0)),
                        'low': float(row.get('最低', 0)),
                        'pre_close': pre_close,
                        'pct_chg': ((price - pre_close) / pre_close * 100) if pre_close > 0 else float(row.get('涨跌幅', 0)),
                        'volume': float(row.get('成交量', 0)),
                        'amount': float(row.get('成交额', 0))
                    })
                except:
                    continue
            
            if data:
                return pd.DataFrame(data)
    except Exception as e:
        log(f"efinance API失败: {e}")
    return None

def get_tencent_quote_batch(codes):
    """腾讯API - 备选"""
    all_data = []
    batch_size = 800
    
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        
        try:
            tencent_codes = []
            for code in batch:
                if code.endswith('.SH'):
                    tencent_codes.append(f"sh{code[:-3]}")
                elif code.endswith('.SZ'):
                    tencent_codes.append(f"sz{code[:-3]}")
                elif code.endswith('.BJ'):
                    tencent_codes.append(f"bj{code[:-3]}")
            
            url = f"https://qt.gtimg.cn/q={','.join(tencent_codes)}"
            r = requests.get(url, timeout=30)
            
            lines = r.text.strip().split(';')
            for line in lines:
                if not line.strip():
                    continue
                try:
                    parts = line.split('=')
                    if len(parts) < 2:
                        continue
                    
                    code_str = parts[0].split('_')[-1]
                    values = parts[1].strip('"').split('~')
                    
                    if len(values) < 45:
                        continue
                    
                    name = values[1]
                    price = float(values[3]) if values[3] else 0
                    pre_close = float(values[4]) if values[4] else 0
                    open_price = float(values[5]) if values[5] else 0
                    high = float(values[33]) if values[33] else 0
                    low = float(values[34]) if values[34] else 0
                    volume = float(values[6]) if values[6] else 0
                    
                    if code_str.startswith('sh'):
                        ts_code = code_str.replace('sh', '') + '.SH'
                    elif code_str.startswith('sz'):
                        ts_code = code_str.replace('sz', '') + '.SZ'
                    elif code_str.startswith('bj'):
                        ts_code = code_str.replace('bj', '') + '.BJ'
                    else:
                        continue
                    
                    all_data.append({
                        'ts_code': ts_code,
                        'name': name,
                        'close': price,
                        'open': open_price,
                        'high': high,
                        'low': low,
                        'pre_close': pre_close,
                        'pct_chg': ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0,
                        'volume': volume,
                        'amount': 0
                    })
                except:
                    continue
            
            time.sleep(0.2)
        except:
            continue
    
    if all_data:
        return pd.DataFrame(all_data)
    return None

def get_market_data():
    """获取市场数据 - 按优先级"""
    
    # 1. 长桥（需要股票列表）
    try:
        import tushare as ts
        ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
        pro = ts.pro_api()
        stocks = pro.stock_basic(exchange='', list_status='L')
        codes = stocks['ts_code'].tolist()
        
        log(f"尝试长桥API ({len(codes)}只股票)...")
        df = get_longbridge_quote(codes)
        if df is not None and not df.empty and len(df) > 1000:
            log(f"✅ 长桥API成功: {len(df)}只")
            return df, '长桥API', codes
    except:
        pass
    
    # 2. efinance（自动获取全市场）
    log("长桥失败，尝试efinance...")
    df = get_efinance_quote()
    if df is not None and not df.empty and len(df) > 1000:
        log(f"✅ efinance成功: {len(df)}只")
        return df, 'efinance', df['ts_code'].tolist()
    
    # 3. 腾讯（需要股票列表）
    log("efinance失败，尝试腾讯API...")
    try:
        codes = stocks['ts_code'].tolist()
        df = get_tencent_quote_batch(codes)
        if df is not None and not df.empty:
            log(f"✅ 腾讯API成功: {len(df)}只")
            return df, '腾讯API', codes
    except:
        pass
    
    log("❌ 所有API都失败")
    return None, None, []

def analyze_sectors(df):
    """板块分析"""
    
    # 定义板块（根据股票代码前缀）
    sectors = {
        'AI算力': ['688256', '688041', '300474'],  # 寒武纪、海光、景嘉微
        '半导体': ['688012', '688072', '688120'],  # 中微、拓荆、华海清科
        '光通讯': ['300308', '300502', '300394'],  # 中际、新易盛、天孚
        '新能源': ['300750', '002594', '601012'],  # 宁德、比亚迪、隆基
        '消费电子': ['002475', '300433', '000725'],  # 立讯、蓝思、京东方
        '金融科技': ['300059', '600030', '601688'],  # 东方财富、中信、华泰
        '医药生物': ['600276', '300760', '603259'],  # 恒瑞、迈瑞、药明
        '白酒': ['600519', '000858', '000568'],  # 茅台、五粮液、老窖
        '银行': ['600036', '000001', '601398'],  # 招行、平安银行、工行
        '券商': ['300059', '600030', '601688'],  # 东财、中信、华泰
    }
    
    # 根据代码匹配板块
    def get_sector(ts_code):
        code = ts_code.split('.')[0]
        for sector, codes in sectors.items():
            if code in codes:
                return sector
        # 根据代码前缀判断
        if code.startswith('688'):
            return '科创板'
        elif code.startswith('300'):
            return '创业板'
        elif code.startswith('8') or code.startswith('4'):
            return '北交所'
        else:
            return '主板'
    
    df['sector'] = df['ts_code'].apply(get_sector)
    
    # 计算板块表现
    sector_perf = df.groupby('sector').agg({
        'pct_chg': 'mean',
        'ts_code': 'count'
    }).rename(columns={'ts_code': 'count'}).sort_values('pct_chg', ascending=False)
    
    return sector_perf

def get_index_data():
    """获取指数数据"""
    indices = ['000001.SH', '399001.SZ', '399006.SZ', '000300.SH']
    df = get_tencent_quote_batch(indices)
    return df

def format_money(val):
    """格式化金额"""
    if val >= 1e12:
        return f"{val/1e12:.2f}万亿"
    elif val >= 1e8:
        return f"{val/1e8:.0f}亿"
    elif val >= 1e4:
        return f"{val/1e4:.0f}万"
    else:
        return f"{val:.0f}"

def generate_report():
    """生成完整收盘报告"""
    log("="*60)
    log("A股收盘深度报告 - 完整版 v3")
    log("="*60)
    
    today = datetime.now().strftime('%Y%m%d')
    log(f"报告日期: {today}")
    
    # 获取市场数据
    df, api_source, all_codes = get_market_data()
    
    if df is None or df.empty:
        log("❌ 无法获取市场数据")
        return None
    
    log(f"数据来源: {api_source}, 共{len(df)}只股票")
    
    # 市场全景统计
    total = len(df)
    up = len(df[df['pct_chg'] > 0])
    down = len(df[df['pct_chg'] < 0])
    flat = len(df[df['pct_chg'] == 0])
    avg_change = df['pct_chg'].mean()
    limit_up = len(df[df['pct_chg'] >= 9.5])
    limit_down = len(df[df['pct_chg'] <= -9.5])
    
    # 成交额
    total_amount = df['amount'].sum() if 'amount' in df.columns else 0
    
    # 指数数据
    index_df = get_index_data()
    
    # 板块分析
    sector_perf = analyze_sectors(df)
    
    # 涨跌幅榜
    top_up = df.nlargest(15, 'pct_chg')[['name', 'ts_code', 'pct_chg', 'close']]
    top_down = df.nsmallest(15, 'pct_chg')[['name', 'ts_code', 'pct_chg', 'close']]
    
    # 生成报告
    report = f"""{'='*70}
📊 A股每日收盘深度报告 ({today})
数据来源: {api_source} | 统计股票: {total}只
{'='*70}

【一、主要指数表现】
"""
    
    if index_df is not None and not index_df.empty:
        for _, row in index_df.iterrows():
            emoji = "🔴" if row['pct_chg'] > 0 else "🟢" if row['pct_chg'] < 0 else "⚪"
            index_names = {
                '000001.SH': '上证指数',
                '399001.SZ': '深证成指',
                '399006.SZ': '创业板指',
                '000300.SH': '沪深300'
            }
            name = index_names.get(row['ts_code'], row['ts_code'])
            report += f"{emoji} {name}: {row['close']:.2f} ({row['pct_chg']:+.2f}%)\n"
    
    report += f"""
【二、市场全景】
┌─────────────────────────────────────────────────────────────────────┐
│ 涨跌分布: 🔴 {up:5}只上涨 | 🟢 {down:5}只下跌 | ⚪ {flat:5}只平盘        │
│ 平均涨跌幅: {avg_change:+.2f}%                                              │
│ 涨停: {limit_up:3}只 | 跌停: {limit_down:3}只                                          │
│ 两市成交额: {format_money(total_amount)}                                        │
└─────────────────────────────────────────────────────────────────────┘

【三、板块强弱排序】
"""
    
    for i, (sector, row) in enumerate(sector_perf.iterrows(), 1):
        emoji = "🔴" if row['pct_chg'] > 0 else "🟢" if row['pct_chg'] < 0 else "⚪"
        report += f"{i:2}. {emoji} {sector:10s}: {row['pct_chg']:+6.2f}% ({int(row['count'])}只)\n"
    
    report += f"""
【四、涨幅榜 TOP15】
"""
    for i, (_, row) in enumerate(top_up.iterrows(), 1):
        report += f"{i:2}. {row['name'][:8]:8s} ({row['ts_code'][:6]}): {row['close']:8.2f}  +{row['pct_chg']:6.2f}%\n"
    
    report += f"""
【五、跌幅榜 TOP15】
"""
    for i, (_, row) in enumerate(top_down.iterrows(), 1):
        report += f"{i:2}. {row['name'][:8]:8s} ({row['ts_code'][:6]}): {row['close']:8.2f}  {row['pct_chg']:6.2f}%\n"
    
    # 市场展望
    trend = "震荡调整" if abs(avg_change) < 0.5 else ("上涨" if avg_change > 0 else "下跌")
    report += f"""
【六、市场展望与总结】

📈 今日市场呈{trend}态势，主要指数{'全线飘红' if avg_change > 0 else '多数收跌'}。

🔍 核心观察:
• 上涨家数: {up}只 ({up/total*100:.1f}%)
• 下跌家数: {down}只 ({down/total*100:.1f}%)
• 涨跌停比: {limit_up}:{limit_down} ({'情绪积极' if limit_up > limit_down*2 else '情绪中性' if limit_up > limit_down else '情绪谨慎'})

💡 明日关注点:
• 成交量变化（今日{format_money(total_amount)}）
• 北向资金流向
• 外盘表现（美股/港股）

⚠️ 风险提示:
• 注意高位股回调风险
• 关注政策面变化
• 控制仓位，注意波动

{'='*70}
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}
"""
    
    # 保存报告
    filename = f"{REPORT_DIR}/daily_report_full_{today}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"✅ 完整报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_report()
