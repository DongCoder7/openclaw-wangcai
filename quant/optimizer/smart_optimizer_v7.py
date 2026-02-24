#!/usr/bin/env python3
"""智能优化器 v7 - 超简版"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("📊 智能优化器 v7")
print("="*50)

# 加载
df = pd.read_sql("""
    SELECT ts_code, trade_date, close FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*)>150)
""", sqlite3.connect(DB))

# 指标
df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ma60'] = df.groupby('ts_code')['close'].rolling(60).mean().reset_index(level=0, drop=True)

# 大盘
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['signal'] = (idx['close'] > idx['ma20']).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['signal']))

print(f"股票: {df['ts_code'].nunique()}")

def backtest(p, s, n):
    years = ['2018', '2019', '2020', '2021']
    results = []
    
    for y in years:
        ydf = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dts = sorted(ydf['trade_date'].unique())[::15]  # 每15天
        
        cap = 1000000
        cash = cap
        h = {}
        
        for rd in dts:
            mkt = idx_dict.get(rd, 1)
            eq = cash + sum(h[k]['s'] * ydf[(ydf['trade_date']==rd) & (ydf['ts_code']==k)]['close'].iloc[0] for k in h if not ydf[(ydf['trade_date']==rd) & (ydf['ts_code']==k)].empty)
            
            if mkt == 0:
                for k in list(h.keys()):
                    hd = ydf[(ydf['trade_date']==rd) & (ydf['ts_code']==k)]
                    if not hd.empty:
                        cash += h[k]['s'] * float(hd['close'].iloc[0])
                h = {}
                continue
            
            cd = ydf[ydf['trade_date']==rd]
            cd = cd[cd['ret20'].notna() & (cd['close'] > cd['ma60']) & (cd['ret20'] > 0)]
            if cd.empty: continue
            
            top = cd.nlargest(n, 'ret20')
            tgt = eq * p / len(top)
            
            # 卖出
            for k in list(h.keys()):
                if k not in top['ts_code'].values:
                    hd = cd[cd['ts_code']==k]
                    if not hd.empty:
                        cash += h[k]['s'] * float(hd['close'].iloc[0])
                        del h[k]
            
            # 买入
            for _, r in top.iterrows():
                if r['ts_code'] not in h:
                    sh = int(tgt / r['close'])
                    if sh > 0:
                        h[r['ts_code']] = {'s': sh, 'p': float(r['close'])}
        
        rd = sorted(ydf['trade_date'].unique())[-1]
        fv = cash + sum(h[k]['s'] * float(ydf[(ydf['trade_date']==rd) & (ydf['ts_code']==k)]['close'].iloc[0]) for k in h if not ydf[(ydf['trade_date']==rd) & (ydf['ts_code']==k)].empty)
        results.append({'year': y, 'return': (fv - cap) / cap, 'final': fv})
    
    return results

# 优化
print("\n优化...")
best = {'p': 0.5, 's': 0.15, 'n': 5}
best_ret = -999

for p in [0.3, 0.5, 0.7]:
    for s in [0.10, 0.15]:
        for n in [5, 8]:
            r = backtest(p, s, n)
            avg = np.mean([x['return'] for x in r])
            if avg > best_ret:
                best_ret = avg
                best = {'p': p, 's': s, 'n': n}
                best_r = r

# 汇报
yearly = [f"📊 {d['year']}: {d['return']*100:+.2f}% | ¥{d['final']:,.0f}" for d in best_r]
avg = np.mean([d['return'] for d in best_r]) * 100

print(f"\n🏆 参数: 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
print(f"\n📈 " + "\n📈 ".join(yearly))
print(f"\n📊 平均: {avg:+.2f}%")

# 保存
with open(f'{OUT}/v7_{datetime.now().strftime("%Y%m%d_%H%M")}.txt', 'w') as f:
    f.write(f"参数: {best}\n平均: {avg}%\n" + "\n".join(yearly))

print("✅")
