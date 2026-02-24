#!/usr/bin/env python3
"""v19 - 深度优化版"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("v19 深度优化版")
print("="*50)

# 加载数据
print("\n[1] 加载数据...")
df = pd.read_sql("""
    SELECT ts_code, trade_date, close, volume, amount FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT DISTINCT ts_code FROM daily_price LIMIT 200)
""", sqlite3.connect(DB))
print(f"数据: {len(df)} 条")

# 计算所有因子
print("\n[2] 计算因子...")

# 动量
df['ret1'] = df.groupby('ts_code')['close'].pct_change(1)
df['ret5'] = df.groupby('ts_code')['close'].pct_change(5)
df['ret10'] = df.groupby('ts_code')['close'].pct_change(10)
df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ret60'] = df.groupby('ts_code')['close'].pct_change(60)
df['ret120'] = df.groupby('ts_code')['close'].pct_change(120)

# 波动率
df['vol5'] = df.groupby('ts_code')['ret1'].rolling(5).std().reset_index(level=0, drop=True)
df['vol20'] = df.groupby('ts_code')['ret1'].rolling(20).std().reset_index(level=0, drop=True)
df['vol60'] = df.groupby('ts_code')['ret1'].rolling(60).std().reset_index(level=0, drop=True)

# 均线
df['ma5'] = df.groupby('ts_code')['close'].rolling(5).mean().reset_index(level=0, drop=True)
df['ma20'] = df.groupby('ts_code')['close'].rolling(20).mean().reset_index(level=0, drop=True)
df['ma60'] = df.groupby('ts_code')['close'].rolling(60).mean().reset_index(level=0, drop=True)

# 成交量
df['vol_ma5'] = df.groupby('ts_code')['volume'].rolling(5).mean().reset_index(level=0, drop=True)
df['vol_ma20'] = df.groupby('ts_code')['volume'].rolling(20).mean().reset_index(level=0, drop=True)

# 资金流向
df['amount_ma5'] = df.groupby('ts_code')['amount'].rolling(5).mean().reset_index(level=0, drop=True)
df['money_flow'] = df['amount'] / df['amount_ma5']

# 相对强弱
idx = df.groupby('trade_date')['ret20'].median().reset_index()
idx.columns = ['trade_date', 'mkt_ret']
df = df.merge(idx, on='trade_date', how='left')
df['rel_strength'] = df['ret20'] - df['mkt_ret']

# 大盘择时
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['trend'] = (idx['close'] > idx['ma20']).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['trend']))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n, mode):
    res = []
    for y in ['2018','2019','2020','2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')].copy()
        dates = sorted(yd['trade_date'].unique())
        
        init = 1000000.0
        cash = init
        h = {}
        
        for rd in dates[::15]:
            rd_d = yd[yd['trade_date']==rd]
            
            hv = sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) 
                    for c in h if not rd_d[rd_d['ts_code']==c].empty)
            tot = cash + hv
            
            # 择时
            if idx_dict.get(rd, 1) == 0:
                for c in list(h.keys()):
                    cd = rd_d[rd_d['ts_code']==c]
                    if not cd.empty:
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                h = {}
                continue
            
            # 选股
            cand = rd_d[rd_d['ret20'].notna()].copy()
            
            if mode == 'momentum':
                cand = cand.nlargest(n, 'ret20')
            elif mode == 'rs':
                cand = cand.nlargest(n, 'rel_strength')
            elif mode == 'quality':
                cand = cand[cand['vol20'] < cand['vol20'].quantile(0.4)]
                cand = cand.nlargest(n, 'rel_strength')
            elif mode == 'trend':
                cand = cand[(cand['close'] > cand['ma20']) & (cand['close'] > cand['ma60'])]
                cand = cand.nlargest(n, 'ret20')
            elif mode == 'combo':
                cand['score'] = (
                    cand['rel_strength'].rank(pct=0.4).fillna(0.5) * 0.25 +
                    (1 - cand['vol20'].rank(pct=0.4)).fillna(0.5) * 0.15 +
                    cand['ret20'].rank(pct=0.4).fillna(0.5) * 0.2 +
                    ((cand['close'] > cand['ma20']).astype(float)) * 0.15 +
                    cand['money_flow'].rank(pct=0.4).fillna(0.5) * 0.15 +
                    cand['ret60'].rank(pct=0.4).fillna(0.5) * 0.1
                )
                cand = cand.nlargest(n, 'score')
            
            if cand.empty: continue
            
            tgt = tot * p / len(cand)
            
            # 调仓
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
            
            # 止损
            for c in list(h.keys()):
                cd = rd_d[rd_d['ts_code']==c]
                if not cd.empty:
                    if (float(cd['close'].iloc[0]) - h[c]['p']) / h[c]['p'] < -s:
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                        del h[c]
        
        # 年末
        rd = dates[-1]
        rd_d = yd[yd['trade_date']==rd]
        fv = cash + sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) 
                       for c in h if not rd_d[rd_d['ts_code']==c].empty)
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

# 测试
print("\n[3] 测试...")
best = None
best_r = None
best_avg = -999

for p in [0.3, 0.5, 0.7, 1.0]:
    for s in [0.05, 0.08, 0.10, 0.15]:
        for n in [3, 5, 8, 10]:
            for mode in ['momentum', 'rs', 'quality', 'trend', 'combo']:
                r = bt(p, s, n, mode)
                avg = np.mean([x['return'] for x in r])
                loss = sum(1 for x in r if x['return'] < 0)
                score = avg - loss * 0.1
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
fn = f'{OUT}/v19_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
with open(fn, 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n")
    f.write(f"模式: {best['mode']}\n")
    f.write(f"平均: {avg:+.1f}%\n" + "\n".join(yearly))

print(f"\n✅ 已保存 {fn}")
