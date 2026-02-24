#!/usr/bin/env python3
"""智能优化器 v12 - 精简参数"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*40)
print("v12...")

df = pd.read_sql("""
    SELECT ts_code, trade_date, close FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*) > 200 LIMIT 400)
""", sqlite3.connect(DB))

df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)

idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx_dict = dict(zip(idx['trade_date'], (idx['close'] > idx['ma20']).astype(int)))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n):
    res = []
    for y in ['2018','2019','2020','2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dates = sorted(yd['trade_date'].unique())
        
        init = 1000000.0
        cash = init
        holdings = {}
        
        for m in range(1, 13):
            mdates = [d for d in dates if d.startswith(f'{y}{m:02d}')]
            if not mdates: continue
            rd = mdates[0]
            rd_data = yd[yd['trade_date'] == rd]
            
            hv = sum(holdings[c]['shares'] * float(rd_data[rd_data['ts_code']==c]['close'].iloc[0]) for c in holdings if not rd_data[rd_data['ts_code']==c].empty)
            total = cash + hv
            
            mkt = idx_dict.get(rd, 1)
            if mkt == 0:
                for c in list(holdings.keys()):
                    prc = rd_data[rd_data['ts_code']==c]
                    if not prc.empty:
                        cash += holdings[c]['shares'] * float(prc['close'].iloc[0])
                holdings = {}
                continue
            
            cand = rd_data[rd_data['ret20'].notna() & (rd_data['ret20']>0)].nlargest(n, 'ret20')
            if cand.empty: continue
            
            tgt = total * p / len(cand)
            
            for c in list(holdings.keys()):
                if c not in cand['ts_code'].values:
                    prc = rd_data[rd_data['ts_code']==c]
                    if not prc.empty:
                        cash += holdings[c]['shares'] * float(prc['close'].iloc[0])
                        del holdings[c]
            
            for _, r in cand.iterrows():
                if r['ts_code'] not in holdings:
                    sh = int(tgt / r['close'])
                    if sh > 0:
                        holdings[r['ts_code']] = {'shares': sh, 'cost': r['close']}
                        cash -= sh * r['close']
            
            for c in list(holdings.keys()):
                prc = rd_data[rd_data['ts_code']==c]
                if not prc.empty:
                    if (float(prc['close'].iloc[0]) - holdings[c]['cost']) / holdings[c]['cost'] < -s:
                        cash += holdings[c]['shares'] * float(prc['close'].iloc[0])
                        del holdings[c]
        
        rd = dates[-1]
        rd_data = yd[yd['trade_date']==rd]
        fv = cash + sum(holdings[c]['shares'] * float(rd_data[rd_data['ts_code']==c]['close'].iloc[0]) for c in holdings if not rd_data[rd_data['ts_code']==c].empty)
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

# 简化测试
best = {'p': 0.5, 's': 0.1, 'n': 5}
best_r = None
best_avg = -999

for p in [0.5, 0.7, 1.0]:
    for s in [0.10, 0.15]:
        for n in [5, 10]:
            r = bt(p, s, n)
            avg = np.mean([x['return'] for x in r])
            if avg > best_avg:
                best_avg, best, best_r = avg, {'p':p,'s':s,'n':n}, r

yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
avg = np.mean([d['return'] for d in best_r]) * 100

print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}%")

with open(f'{OUT}/v12_{datetime.now().strftime("%Y%m%d_%H%M")}.txt', 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n平均: {avg:+.1f}%\n" + "\n".join(yearly))
print("✅")
