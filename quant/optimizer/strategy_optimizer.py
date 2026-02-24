#!/usr/bin/env python3
"""
投资策略优化器 - 每日22:00-08:00运行
每15分钟进行一轮优化
"""
import sqlite3
import pandas as pd
import numpy as np
import json
import random
import time
from datetime import datetime
import os

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
OUTPUT_DIR = '/root/.openclaw/workspace/quant/optimizer'

def load_data():
    """加载数据"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT ts_code, trade_date, close, volume 
        FROM daily_price 
        WHERE trade_date BETWEEN '20180101' AND '20211231'
    """, conn)
    conn.close()
    
    # 行业分类
    def get_ind(code):
        c = int(code.split('.')[0])
        if c >= 688000: return '科创'
        if 300000 <= c < 301000: return '创业板'
        if 600000 <= c < 600200: return '金融'
        if 600500 <= c < 600600: return '消费'
        return '其他'
    
    df['ind'] = df['ts_code'].apply(get_ind)
    df = df.sort_values(['ts_code','trade_date'])
    df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
    df['ret60'] = df.groupby('ts_code')['close'].pct_change(60)
    df['volma20'] = df.groupby('ts_code')['volume'].transform(lambda x: x.rolling(20).mean())
    df['volratio'] = df['volume'] / df['volma20']
    
    return df

def backtest(params, df):
    """单次回测"""
    position = params.get('position', 0.7)
    stop_loss = params.get('stop_loss', 0.20)
    rebal_days = params.get('rebalance_days', 20)
    
    yearly = []
    for year in ['2018','2019','2020','2021']:
        ydf = df[(df['trade_date'] >= f'{year}0101') & (df['trade_date'] <= f'{year}1231')]
        dates = sorted(ydf['trade_date'].unique())
        if len(dates) < 100:
            continue
        
        capital = 1000000
        cash = capital * (1 - position)
        holdings = {}
        
        # 初始建仓
        init_date = dates[20]
        init_df = ydf[ydf['trade_date'] == init_date]
        
        for ind_n in ['创业板','科创','消费','金融']:
            ind_df = init_df[(init_df['ind']==ind_n) & init_df['ret20'].notna()]
            if len(ind_df) > 0:
                top = ind_df.nlargest(2, 'ret20')
                for _, r in top.iterrows():
                    if r['close'] > 0:
                        shares = int(capital * position / 8 / r['close'])
                        holdings[r['ts_code']] = {'shares': shares, 'cost': r['close']}
        
        # 调仓
        for month in range(2, 13):
            m_dates = [d for d in dates if d.startswith(f'{year}{month:02d}')]
            if not m_dates:
                continue
            
            check_date = m_dates[0]
            check_df = ydf[ydf['trade_date'] == check_date]
            market = check_df['ret20'].median()
            
            if market > 0.05:
                score_col = 'ret20'
            elif market < -0.05:
                score_col = 'ret60'
            else:
                score_col = 'ret20'
            
            # 止损
            for code in list(holdings.keys()):
                d = check_df[check_df['ts_code']==code]
                if not d.empty:
                    pnl = (d['close'].iloc[0] - holdings[code]['cost']) / holdings[code]['cost']
                    if pnl < -stop_loss:
                        cash += holdings[code]['shares'] * d['close'].iloc[0]
                        del holdings[code]
            
            # 调仓
            if month % max(1, rebal_days // 30) == 0:
                while len(holdings) < 8:
                    added = False
                    for ind_n in ['创业板','科创','消费','金融']:
                        valid = check_df[(check_df['ind']==ind_n) & check_df[score_col].notna()]
                        if len(valid) > 0:
                            top = valid.nlargest(2, score_col)
                            for _, r in top.iterrows():
                                if r['ts_code'] not in holdings and r['close'] > 0:
                                    shares = int(capital * position / 8 / r['close'])
                                    holdings[r['ts_code']] = {'shares': shares, 'cost': r['close']}
                                    cash -= shares * r['close']
                                    added = True
                                    break
                        if added:
                            break
                    if not added:
                        break
        
        # 年末结算
        final_df = ydf[ydf['trade_date'] == dates[-1]]
        fv = cash + sum(h['shares'] * final_df[final_df['ts_code']==c]['close'].iloc[0] 
                       for c,h in holdings.items() if not final_df[final_df['ts_code']==c].empty)
        
        yearly.append((fv - capital) / capital)
    
    return sum(yearly) / 4 if yearly else -1

def random_params():
    """随机生成参数"""
    return {
        'position': random.choice([0.5, 0.6, 0.7, 0.8]),
        'stop_loss': random.choice([0.10, 0.15, 0.20, 0.25]),
        'rebalance_days': random.choice([15, 20, 30, 45]),
        'momentum_weight': random.uniform(0.5, 1.0),
        'reverse_weight': random.uniform(0, 0.5),
    }

def optimize():
    """优化主函数"""
    print(f"\n{'='*60}")
    print(f"🧪 策略优化轮次 - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    
    # 加载数据
    print("加载数据...")
    df = load_data()
    print(f"数据: {df['ts_code'].nunique()}只股票")
    
    # 随机选择模拟时间点
    years = ['2018','2019','2020','2021']
    sim_year = random.choice(years)
    sim_month = random.randint(1, 12)
    sim_day = random.randint(1, 28)
    sim_date = f"{sim_year}{sim_month:02d}{sim_day:02d}"
    
    print(f"模拟时间点: {sim_date}")
    
    # 100次模拟
    results = []
    best_avg = -999
    best_params = None
    
    for i in range(100):
        params = random_params()
        avg = backtest(params, df)
        
        results.append({
            'params': params,
            'avg_return': avg,
            'sim_date': sim_date
        })
        
        if avg > best_avg:
            best_avg = avg
            best_params = params
        
        if (i+1) % 20 == 0:
            print(f"  进度: {i+1}/100, 当前最优: {best_avg*100:+.1f}%")
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    result_file = f"{OUTPUT_DIR}/result_{timestamp}.json"
    with open(result_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'sim_date': sim_date,
            'total_simulations': 100,
            'best_params': best_params,
            'best_return': best_avg,
            'all_results': results
        }, f, indent=2, default=str)
    
    # 更新最佳参数
    best_file = f"{OUTPUT_DIR}/best_params.json"
    try:
        with open(best_file, 'r') as f:
            history = json.load(f)
    except:
        history = {'rounds': []}
    
    history['rounds'].append({
        'timestamp': timestamp,
        'best_params': best_params,
        'best_return': best_avg
    })
    history['latest'] = {
        'params': best_params,
        'return': best_avg
    }
    
    with open(best_file, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"\n🏆 本轮最优参数:")
    print(f"  仓位: {best_params['position']*100:.0f}%")
    print(f"  止损: {best_params['stop_loss']*100:.0f}%")
    print(f"  调仓: {best_params['rebalance_days']}天")
    print(f"  收益: {best_avg*100:+.1f}%")
    
    return best_params, best_avg

if __name__ == '__main__':
    optimize()
