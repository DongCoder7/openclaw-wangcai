#!/usr/bin/env python3
"""智能优化器 v13 - 多维度择时"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("v13 多维度优化版")
print("="*50)

# 取数据
df = pd.read_sql("""
    SELECT ts_code, trade_date, close FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*) > 200 LIMIT 300)
""", sqlite3.connect(DB))

# 计算指标
df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ret60'] = df.groupby('ts_code')['close'].pct_change(60)

# 大盘
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['ma60'] = idx['close'].rolling(60).mean()
idx['trend'] = ((idx['close'] > idx['ma20']) & (idx['close'] > idx['ma60'])).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['trend']))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n, strict):
    """回测"""
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
            
            # 权益
            hv = sum(holdings[c]['shares'] * float(rd_data[rd_data['ts_code']==c]['close'].iloc[0]) 
                    for c in holdings if not rd_data[rd_data['ts_code']==c].empty)
            total = cash + hv
            
            # 择时
            trend = idx_dict.get(rd, 1)
            if trend == 0 and strict:
                for c in list(holdings.keys()):
                    prc = rd_data[rd_data['ts_code']==c]
                    if not prc.empty:
                        cash += holdings[c]['shares'] * float(prc['close'].iloc[0])
                holdings = {}
                continue
            
            # 选股
            cand = rd_data[rd_data['ret20'].notna()].copy()
            if strict:
                cand = cand[(cand['ret20'] > 0) & (cand['ret20'] > cand['ret60'])]  # 动量加速
            cand = cand.nlargest(n, 'ret20')
            if cand.empty: continue
            
            tgt = total * p / len(cand)
            
            # 卖出
            for c in list(holdings.keys()):
                if c not in cand['ts_code'].values:
                    prc = rd_data[rd_data['ts_code']==c]
                    if not prc.empty:
                        cash += holdings[c]['shares'] * float(prc['close'].iloc[0])
                        del holdings[c]
            
            # 买入
            for _, r in cand.iterrows():
                if r['ts_code'] not in holdings:
                    sh = int(tgt / r['close'])
                    if sh > 0:
                        holdings[r['ts_code']] = {'shares': sh, 'cost': r['close']}
                        cash -= sh * r['close']
            
            # 止损
            for c in list(holdings.keys()):
                prc = rd_data[rd_data['ts_code']==c]
                if not prc.empty:
                    if (float(prc['close'].iloc[0]) - holdings[c]['cost']) / holdings[c]['cost'] < -s:
                        cash += holdings[c]['shares'] * float(prc['close'].iloc[0])
                        del holdings[c]
        
        # 年末
        rd = dates[-1]
        rd_data = yd[yd['trade_date']==rd]
        fv = cash + sum(holdings[c]['shares'] * float(rd_data[rd_data['ts_code']==c]['close'].iloc[0]) 
                       for c in holdings if not rd_data[rd_data['ts_code']==c].empty)
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

# 测试
print("\n测试...")
configs = [
    {'p': 0.3, 's': 0.10, 'n': 5, 'strict': True},
    {'p': 0.5, 's': 0.10, 'n': 5, 'strict': True},
    {'p': 0.7, 's': 0.10, 'n': 5, 'strict': True},
    {'p': 1.0, 's': 0.10, 'n': 5, 'strict': True},
    {'p': 1.0, 's': 0.15, 'n': 5, 'strict': True},
    {'p': 0.5, 's': 0.15, 'n': 10, 'strict': False},
    {'p': 1.0, 's': 0.10, 'n': 10, 'strict': False},
]

best = None
best_r = None
best_avg = -999

for cfg in configs:
    r = bt(cfg['p'], cfg['s'], cfg['n'], cfg['strict'])
    avg = np.mean([x['return'] for x in r])
    loss = sum(1 for x in r if x['return'] < 0)
    score = avg - loss * 0.1
    if score > best_avg:
        best_avg = score
        best = cfg
        best_r = r

yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
avg = np.mean([d['return'] for d in best_r]) * 100
loss_years = sum(1 for d in best_r if d['return'] < 0)

print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
print(f"   严格模式: {'是' if best['strict'] else '否'}")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}% | 亏损: {loss_years}年")

# 保存
fn = f'{OUT}/v13_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
with open(fn, 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n严格: {'是' if best['strict'] else '否'}\n平均: {avg:+.1f}%\n" + "\n".join(yearly))

print(f"\n✅ 已保存 {fn}")
