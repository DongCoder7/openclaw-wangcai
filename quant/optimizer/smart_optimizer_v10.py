#!/usr/bin/env python3
"""智能优化器 v10 - 严谨版"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*40)
print("v10 严谨版...")

# 取300只
df = pd.read_sql("""
    SELECT ts_code, trade_date, close FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*) > 200 LIMIT 300)
""", sqlite3.connect(DB))

df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)

# 大盘
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx_dict = dict(zip(idx['trade_date'], (idx['close'] > idx['ma20']).astype(int)))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, n):
    """单年回测"""
    years = ['2018','2019','2020','2021']
    yearly_returns = []
    
    for y in years:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')].copy()
        dates = sorted(yd['trade_date'].unique())
        
        if len(dates) < 100:
            continue
        
        # 初始100万
        init = 1000000.0
        cash = init
        holdings = {}  # {code: {'shares': int, 'cost': float}}
        
        # 每月第一个交易日调仓
        for m in range(1, 13):
            # 找当月第一个交易日
            mdates = [d for d in dates if d.startswith(f'{y}{m:02d}')]
            if not mdates:
                continue
            rd = mdates[0]
            
            # 大盘择时
            mkt = idx_dict.get(rd, 1)
            rd_data = yd[yd['trade_date'] == rd]
            
            # 计算当前持仓市值
            holdings_val = 0.0
            for code, pos in holdings.items():
                prc_data = rd_data[rd_data['ts_code'] == code]
                if not prc_data.empty:
                    holdings_val += pos['shares'] * float(prc_data['close'].iloc[0])
            
            total_val = cash + holdings_val
            
            # 空仓
            if mkt == 0:
                for code, pos in holdings.items():
                    prc = rd_data[rd_data['ts_code'] == code]
                    if not prc.empty:
                        cash += pos['shares'] * float(prc['close'].iloc[0])
                holdings = {}
                continue
            
            # 选股：动量前N
            cand = rd_data[rd_data['ret20'].notna()].nlargest(n, 'ret20')
            if cand.empty:
                continue
            
            # 目标持仓
            target_val = total_val * p
            target_per_stock = target_val / len(cand)
            
            # 卖出不在候选的
            for code in list(holdings.keys()):
                if code not in cand['ts_code'].values:
                    prc = rd_data[rd_data['ts_code'] == code]
                    if not prc.empty:
                        cash += holdings[code]['shares'] * float(prc['close'].iloc[0])
                        del holdings[code]
            
            # 买入
            for _, row in cand.iterrows():
                code = row['ts_code']
                if code in holdings:
                    continue
                price = float(row['close'])
                shares = int(target_per_stock / price)
                if shares > 0:
                    holdings[code] = {'shares': shares, 'cost': price}
                    cash -= shares * price
            
            # 止损
            for code in list(holdings.keys()):
                prc = rd_data[rd_data['ts_code'] == code]
                if not prc.empty:
                    cur_price = float(prc['close'].iloc[0])
                    cost = holdings[code]['cost']
                    if (cur_price - cost) / cost < -0.10:  # 10%止损
                        cash += holdings[code]['shares'] * cur_price
                        del holdings[code]
        
        # 年末
        rd = dates[-1]
        rd_data = yd[yd['trade_date'] == rd]
        final_val = cash
        for code, pos in holdings.items():
            prc = rd_data[rd_data['ts_code'] == code]
            if not prc.empty:
                final_val += pos['shares'] * float(prc['close'].iloc[0])
        
        ret = (final_val - init) / init
        yearly_returns.append({'year': y, 'return': ret, 'final': final_val})
    
    return yearly_returns

# 测试参数
print("\n测试...")
best = {'p': 0.5, 'n': 5}
best_r = None
best_avg = -999

for p in [0.3, 0.5, 0.7]:
    for n in [5, 8]:
        r = bt(p, n)
        avg = np.mean([x['return'] for x in r])
        if avg > best_avg:
            best_avg = avg
            best = {'p': p, 'n': n}
            best_r = r

yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
avg = np.mean([d['return'] for d in best_r]) * 100

print(f"\n🏆 仓位{best['p']*100:.0f}% 持仓{best['n']}只 止损10%")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}%")

# 保存
fn = f'{OUT}/v10_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
with open(fn, 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 持仓{best['n']}只\n平均: {avg:+.1f}%\n" + "\n".join(yearly))
print(f"✅ 已保存")
