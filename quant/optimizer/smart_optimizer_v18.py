#!/usr/bin/env python3
"""v18 - 精简版"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*40)
print("v18")

# 加载数据
df = pd.read_sql("""
    SELECT ts_code, trade_date, close FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT DISTINCT ts_code FROM daily_price LIMIT 300)
""", sqlite3.connect(DB))

df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ret60'] = df.groupby('ts_code')['close'].pct_change(60)

# 大盘
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma'] = idx['close'].rolling(10).mean()
idx['signal'] = (idx['close'] > idx['ma']).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['signal']))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n):
    res = []
    for y in ['2018','2019','2020','2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dates = sorted(yd['trade_date'].unique())
        
        init = 1000000.0
        cash = init
        h = {}
        
        for rd in dates[::15]:
            rd_d = yd[yd['trade_date']==rd]
            
            hv = sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) for c in h if not rd_d[rd_d['ts_code']==c].empty)
            tot = cash + hv
            
            if idx_dict.get(rd, 1) == 0:
                for c in list(h.keys()):
                    cd = rd_d[rd_d['ts_code']==c]
                    if not cd.empty:
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                h = {}
                continue
            
            cand = rd_d[rd_d['ret20'].notna()].nlargest(n, 'ret20')
            if cand.empty: continue
            
            tgt = tot * p / len(cand)
            
            for c in list(h.keys()):
                if c not in cand['ts_code'].values:
                    cd = rd_d[rd_d['ts_code']==c]
                    if not cd.empty:
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                        del h[c]
            
            for _, r in cand.iterrows():
                if r['ts_code'] not in h:
                    sh = int(tgt / r['close'])
                    if sh > 0:
                        h[r['ts_code']] = {'s': sh, 'p': r['close']}
                        cash -= sh * r['close']
            
            for c in list(h.keys()):
                cd = rd_d[rd_d['ts_code']==c]
                if not cd.empty:
                    if (float(cd['close'].iloc[0]) - h[c]['p']) / h[c]['p'] < -s:
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                        del h[c]
        
        rd = dates[-1]
        rd_d = yd[yd['trade_date']==rd]
        fv = cash + sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) for c in h if not rd_d[rd_d['ts_code']==c].empty)
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

# 测试
best, best_r = None, None
best_avg = -999

for p in [0.5, 0.7, 1.0]:
    for s in [0.08, 0.10]:
        for n in [5, 10]:
            r = bt(p, s, n)
            avg = np.mean([x['return'] for x in r])
            loss = sum(1 for x in r if x['return'] < 0)
            score = avg - loss * 0.15
            if score > best_avg:
                best_avg, best, best_r = score, {'p':p,'s':s,'n':n}, r

yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
avg = np.mean([d['return'] for d in best_r]) * 100

print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}%")

with open(f'{OUT}/v18_{datetime.now().strftime("%Y%m%d_%H%M")}.txt', 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n平均: {avg:+.1f}%\n" + "\n".join(yearly))
print("✅")
