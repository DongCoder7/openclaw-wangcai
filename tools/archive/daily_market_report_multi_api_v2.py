#!/root/.openclaw/workspace/venv/bin/python3
"""
收盘报告 - 多API实时版 (v2)
API优先级: 长桥 > 腾讯 > efinance > Tushare
自动降级，一个失败用下一个
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
    """获取长桥token - 从环境变量或配置文件"""
    try:
        # 1. 先尝试环境变量
        token = os.environ.get('LONGPORT_ACCESS_TOKEN')
        if token:
            return token
        
        # 2. 从配置文件读取
        env_file = '/root/.openclaw/workspace/.longbridge.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('LONGPORT_ACCESS_TOKEN='):
                        token = line.split('=', 1)[1].strip().strip('"\'')
                        return token
        
        # 3. 尝试token.ini
        token_path = os.path.expanduser('~/.openclaw/longbridge/token.ini')
        if os.path.exists(token_path):
            from configparser import ConfigParser
            config = ConfigParser()
            config.read(token_path)
            if 'auth' in config:
                return config['auth'].get('access_token')
                
    except Exception as e:
        log(f"长桥token读取失败: {e}")
    return None

def get_longbridge_quote(codes):
    """长桥API获取实时行情 - 首选"""
    token = get_longbridge_token()
    if not token:
        log("长桥token不存在或已过期")
        return None
    
    try:
        import requests
        
        # 转换代码格式为长桥格式
        lb_codes = []
        for code in codes:
            if code.endswith('.SH'):
                lb_codes.append(f"SH.{code[:-3]}")
            elif code.endswith('.SZ'):
                lb_codes.append(f"SZ.{code[:-3]}")
            elif code.endswith('.BJ'):
                lb_codes.append(f"BJ.{code[:-3]}")
        
        # 长桥API每次最多100只，需要分批
        all_data = []
        batch_size = 100
        
        for i in range(0, len(lb_codes), batch_size):
            batch = lb_codes[i:i+batch_size]
            url = "https://openapi.longbridge.sg/v1/quote/realtime"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {"symbols": batch}
            
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            if r.status_code == 200:
                result = r.json()
                if result.get('code') == 0 and 'data' in result:
                    for item in result['data']:
                        try:
                            # 转换回标准代码
                            symbol = item.get('symbol', '')
                            if symbol.startswith('SH.'):
                                ts_code = symbol.replace('SH.', '') + '.SH'
                            elif symbol.startswith('SZ.'):
                                ts_code = symbol.replace('SZ.', '') + '.SZ'
                            elif symbol.startswith('BJ.'):
                                ts_code = symbol.replace('BJ.', '') + '.BJ'
                            else:
                                continue
                            
                            # 获取价格数据
                            price = item.get('last_done', 0) or item.get('price', 0)
                            open_price = item.get('open', 0)
                            high = item.get('high', 0)
                            low = item.get('low', 0)
                            pre_close = item.get('prev_close', 0)
                            volume = item.get('volume', 0)
                            
                            if pre_close > 0:
                                pct_chg = (price - pre_close) / pre_close * 100
                            else:
                                pct_chg = 0
                            
                            all_data.append({
                                'ts_code': ts_code,
                                'name': item.get('name', ''),
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
            
            time.sleep(0.5)  # 限速
        
        if all_data:
            return pd.DataFrame(all_data)
    except Exception as e:
        log(f"长桥API失败: {e}")
    return None

def get_tencent_quote_batch(codes):
    """腾讯API获取实时行情 - 分批获取全市场"""
    all_data = []
    batch_size = 800  # 腾讯每批最多800只
    
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        
        try:
            # 转换代码格式
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
            
            # 解析腾讯返回的数据
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
                    
                    # 腾讯数据格式: 1=名称, 2=代码, 3=现价, 4=昨收, 5=今开, 6=成交量, 33=最高价, 34=最低价
                    name = values[1]
                    price = float(values[3]) if values[3] else 0
                    pre_close = float(values[4]) if values[4] else 0
                    open_price = float(values[5]) if values[5] else 0
                    high = float(values[33]) if values[33] else 0
                    low = float(values[34]) if values[34] else 0
                    volume = float(values[6]) if values[6] else 0
                    
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
                    
                    all_data.append({
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
            
            time.sleep(0.3)  # 限速，避免请求过快
            
        except Exception as e:
            log(f"腾讯API批次{i//batch_size}失败: {e}")
            continue
    
    if all_data:
        return pd.DataFrame(all_data)
    return None

def get_efinance_quote(codes):
    """efinance API - 备选"""
    try:
        import efinance as ef
        
        # efinance获取全市场实时行情
        df = ef.stock.get_realtime_quotes()
        
        if df is not None and not df.empty:
            # 转换格式
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
                    open_price = float(row.get('今日开盘价', 0))
                    high = float(row.get('最高', 0))
                    low = float(row.get('最低', 0))
                    volume = float(row.get('成交量', 0))
                    
                    if pre_close > 0:
                        pct_chg = (price - pre_close) / pre_close * 100
                    else:
                        pct_chg = float(row.get('涨跌幅', 0))
                    
                    data.append({
                        'ts_code': ts_code,
                        'name': row.get('股票名称', ''),
                        'close': price,
                        'open': open_price,
                        'high': high,
                        'low': low,
                        'pre_close': pre_close,
                        'pct_chg': pct_chg,
                        'volume': volume
                    })
                except:
                    continue
            
            if data:
                return pd.DataFrame(data)
    except Exception as e:
        log(f"efinance API失败: {e}")
    return None

def get_all_stocks():
    """获取全市场股票列表"""
    try:
        import tushare as ts
        ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
        pro = ts.pro_api()
        
        stocks = pro.stock_basic(exchange='', list_status='L')
        codes = stocks['ts_code'].tolist()
        log(f"Tushare获取股票列表: {len(codes)}只")
        return codes
    except Exception as e:
        log(f"Tushare获取列表失败: {e}")
        # 备选：从数据库读取
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            stocks = pd.read_sql("SELECT DISTINCT ts_code FROM daily_price WHERE trade_date >= '20260101'", conn)
            conn.close()
            codes = stocks['ts_code'].tolist()
            log(f"从数据库获取股票列表: {len(codes)}只")
            return codes
        except:
            return []

def get_market_data(codes):
    """获取市场数据 - 按优先级尝试多个API"""
    
    # 1. 首选长桥
    log("尝试长桥API...")
    df = get_longbridge_quote(codes)
    if df is not None and not df.empty:
        log(f"✅ 长桥API成功: {len(df)}只")
        return df, '长桥API'
    
    # 2. 备选腾讯
    log("长桥失败，尝试腾讯API...")
    df = get_tencent_quote_batch(codes)
    if df is not None and not df.empty:
        log(f"✅ 腾讯API成功: {len(df)}只")
        return df, '腾讯API'
    
    # 3. 备选efinance
    log("腾讯失败，尝试efinance...")
    df = get_efinance_quote(codes)
    if df is not None and not df.empty:
        log(f"✅ efinance成功: {len(df)}只")
        return df, 'efinance'
    
    log("❌ 所有API都失败")
    return None, None

def generate_report():
    """生成收盘报告"""
    log("="*60)
    log("多API收盘报告生成 v2")
    log("="*60)
    
    today = datetime.now().strftime('%Y%m%d')
    log(f"报告日期: {today}")
    
    # 获取股票列表
    log("获取股票列表...")
    stocks = get_all_stocks()
    if not stocks:
        log("❌ 无法获取股票列表")
        return None
    log(f"共{len(stocks)}只股票")
    
    # 获取市场数据（自动选择API）
    df, api_source = get_market_data(stocks)
    
    if df is None or df.empty:
        log("❌ 无法获取市场数据")
        return None
    
    log(f"数据来源: {api_source}, 共{len(df)}只股票")
    
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
    index_df = get_tencent_quote_batch(indices)  # 指数用腾讯API比较稳定
    
    # 涨跌幅榜
    top_up = df.nlargest(10, 'pct_chg')[['name', 'ts_code', 'pct_chg']]
    top_down = df.nsmallest(10, 'pct_chg')[['name', 'ts_code', 'pct_chg']]
    
    # 生成报告
    report = f"""{'='*60}
📊 每日收盘深度报告 ({today})
数据来源: {api_source} (实时)
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
    filename = f"{REPORT_DIR}/daily_report_api_{today}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"✅ 报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_report()
