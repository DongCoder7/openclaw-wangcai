#!/root/.openclaw/workspace/venv/bin/python3
"""
Tushare Pro 财务数据补充 - 杜邦分析等
"""
import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime
import time

TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'
DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")

def init_tushare():
    ts.set_token(TOKEN)
    return ts.pro_api()

def get_fina_data(pro, ts_code, period):
    """获取财务数据"""
    try:
        # 获取财务指标
        df = pro.fina_indicator(ts_code=ts_code, period=period)
        
        if df.empty:
            return None
        
        row = df.iloc[0]
        
        return {
            'ts_code': ts_code,
            'period': period,
            'roe': row.get('roe'),
            'roe_waa': row.get('roe_waa'),
            'roe_dt': row.get('roe_dt'),
            'roa': row.get('roa'),
            'roic': row.get('roic'),
            'netprofit_yoy': row.get('netprofit_yoy'),
            'dt_netprofit_yoy': row.get('dt_netprofit_yoy'),
            'revenue_yoy': row.get('tr_yoy'),  # 使用tr_yoy替代revenue_yoy
            'grossprofit_margin': row.get('grossprofit_margin'),
            'netprofit_margin': row.get('netprofit_margin'),
            'assets_turn': row.get('assets_turn'),
            'op_yoy': row.get('op_yoy'),
            'debt_to_assets': row.get('debt_to_assets'),
            'current_ratio': row.get('current_ratio'),
        }
        
    except Exception as e:
        return None

def main():
    log("="*60)
    log("🚀 Tushare Pro 财务数据补充")
    log("="*60)
    
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    
    # 创建表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fina_tushare (
            ts_code TEXT,
            period TEXT,
            roe REAL,
            roe_waa REAL,
            roe_dt REAL,
            roa REAL,
            roic REAL,
            netprofit_yoy REAL,
            dt_netprofit_yoy REAL,
            revenue_yoy REAL,
            grossprofit_margin REAL,
            netprofit_margin REAL,
            assets_turn REAL,
            op_yoy REAL,
            debt_to_assets REAL,
            current_ratio REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, period)
        )
    ''')
    conn.commit()
    
    # 获取股票列表
    stocks = [s[0] for s in conn.execute('SELECT DISTINCT ts_code FROM stock_basic').fetchall()]
    log(f"股票总数: {len(stocks)}")
    
    # 补充2022-2024年报数据
    periods = ['20221231', '20231231', '20241231']
    
    success = 0
    fail = 0
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 100 == 0:
            log(f"进度: {i}/{len(stocks)} | 成功: {success} | 失败: {fail}")
            conn.commit()
        
        for period in periods:
            data = get_fina_data(pro, ts_code, period)
            if data:
                try:
                    conn.execute('''
                        INSERT OR REPLACE INTO fina_tushare 
                        (ts_code, period, roe, roe_waa, roe_dt, roa, roic,
                         netprofit_yoy, dt_netprofit_yoy, revenue_yoy,
                         grossprofit_margin, netprofit_margin, assets_turn,
                         op_yoy, debt_to_assets, current_ratio, update_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ''', [
                        data['ts_code'], data['period'], data['roe'], data['roe_waa'],
                        data['roe_dt'], data['roa'], data['roic'], data['netprofit_yoy'],
                        data['dt_netprofit_yoy'], data['revenue_yoy'], data['grossprofit_margin'],
                        data['netprofit_margin'], data['assets_turn'], data['op_yoy'],
                        data['debt_to_assets'], data['current_ratio']
                    ])
                    success += 1
                except:
                    fail += 1
            else:
                fail += 1
            
            time.sleep(0.05)  # 限速
    
    conn.commit()
    conn.close()
    
    log(f"\n✅ 完成! 成功: {success}, 失败: {fail}")

if __name__ == '__main__':
    main()
