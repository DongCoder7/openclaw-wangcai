#!/usr/bin/env python3
"""v17 - 修复版，使用真实价格数据+因子选股"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("v17 修复版")
print("="*50)

# 加载价格数据
print("\n[1] 加载数据...")
df = pd.read_sql("""
    SELECT ts_code, trade_date, close FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM stock_factors GROUP BY ts_code LIMIT 400)
""", sqlite3.connect(DB))

# 加载因子
df_fac = pd.read_sql("""
    SELECT ts_code, trade_date, rel_strength, vol_ratio, mom_accel, price_pos_high
    FROM stock_factors
    WHERE trade_date BETWEEN '20180101' AND '20211231'
""", sqlite3.connect(DB))

# 合并
df = df.merge(df_fac, on=['ts_code', 'trade_date'], how='left')

# 计算动量
df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)

# 大盘
idx = df.groupby('trade_date')['ret20'].median().reset_index()
idx['ma5'] = idx['ret20'].rolling(5).mean()
idx['signal'] = (idx['ma5'] > 0).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['signal']))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n, mode):
    res = []
    for y in ['2018','2019','2020','2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')].copy()
        dates = sorted(yd['trade_date'].unique())
        
        init = 1000000.0
        cash = init
        holdings = {}
        
        for m in range(1, 13):
            mdates = [d for d in dates if d.startswith(f'{y}{m:02d}')]
            if not mdates: continue
            rd = mdates[0]
            rd_data = yd[yd['trade_date'] == rd]
            
            # 权益
            hv = 0
            for c in holdings:
                cd = rd_data[rd_data['ts_code']==c]
                if not cd.empty:
                    hv += holdings[c]['shares'] * float(cd['close'].iloc[0])
            total = cash + hv
            
            # 择时
            if idx_dict.get(rd, 1) == 0:
                for c in list(holdings.keys()):
                    cd = rd_data[rd_data['ts_code']==c]
                    if not cd.empty:
                        cash += holdings[c]['shares'] * float(cd['close'].iloc[0])
                holdings = {}
                continue
            
            # 选股
            cand = rd_data[rd_data['ret20'].notna()].copy()
            
            if mode == 'alpha':
                cand = cand.nlargest(n, 'rel_strength')
            elif mode == 'quality':
                cand = cand[cand['vol_ratio'] < 1.0]
                cand = cand.nlargest(n, 'rel_strength')
            elif mode == 'combo':
                cand['score'] = (
                    cand['rel_strength'].rank(pct=0.4).fillna(0.5) * 0.4 +
                    (1 - cand['vol_ratio'].rank(pct=0.4)).fillna(0.5) * 0.3 +
                    cand['ret20'].rank(pct=0.4).fillna(0.5) * 0.3
                )
                cand = cand.nlargest(n, 'score')
            else:
                cand = cand.nlargest(n, 'ret20')
            
            if cand.empty: continue
            
            tgt = total * p / len(cand)
            
            # 卖出
            for c in list(holdings.keys()):
                if c not in cand['ts_code'].values:
                    cd = rd_data[rd_data['ts_code']==c]
                    if not cd.empty:
                        cash += holdings[c]['shares'] * float(cd['close'].iloc[0])
                        del holdings[c]
            
            # 买入
            for _, r in cand.iterrows():
                if r['ts_code'] in holdings: continue
                sh = int(tgt / r['close'])
                if sh > 0:
                    holdings[r['ts_code']] = {'shares': sh, 'cost': float(r['close'])}
                    cash -= sh * r['close']
            
            # 止损
            for c in list(holdings.keys()):
                cd = rd_data[rd_data['ts_code']==c]
                if not cd.empty:
                    cur = float(cd['close'].iloc[0])
                    if (cur - holdings[c]['cost']) / holdings[c]['cost'] < -s:
                        cash += holdings[c]['shares'] * cur
                        del holdings[c]
        
        # 年末
        rd = dates[-1]
        rd_data = yd[yd['trade_date']==rd]
        fv = cash
        for c in holdings:
            cd = rd_data[rd_data['ts_code']==c]
            if not cd.empty:
                fv += holdings[c]['shares'] * float(cd['close'].iloc[0])
        
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

# 测试
print("\n测试...")
best = None
best_r = None
best_avg = -999

for p in [0.3, 0.5, 0.7, 1.0]:
    for s in [0.08, 0.10, 0.15]:
        for n in [5, 10]:
            for mode in ['alpha', 'quality', 'combo', 'momentum']:
                r = bt(p, s, n, mode)
                avg = np.mean([x['return'] for x in r])
                loss = sum(1 for x in r if x['return'] < 0)
                score = avg - loss * 0.15
                if score > best_avg:
                    best_avg = score
                    best = {'p': p, 's': s, 'n': n, 'mode': mode}
                    best_r = r

yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
avg = np.mean([d['return'] for d in best_r]) * 100
loss = sum(1 for d in best_r if d['return'] < 0)

print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
print(f"   模式: {best['mode']}")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}% | 亏损: {loss}年")

# 保存
fn = f'{OUT}/v17_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
with open(fn, 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n模式: {best['mode']}\n平均: {avg:+.1f}%\n" + "\n".join(yearly))

print(f"\n✅ 已保存 {fn}")
