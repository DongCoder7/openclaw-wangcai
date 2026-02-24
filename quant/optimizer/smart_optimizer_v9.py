#!/usr/bin/env python3
"""智能优化器 v9 - 修复索引bug"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*40)
print("v9 优化中...")

# 取500只股票
df = pd.read_sql("""
    SELECT ts_code, trade_date, close FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*) > 200 LIMIT 500)
""", sqlite3.connect(DB))

df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df = df.dropna(subset=['ret20'])

# 大盘
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx_dict = dict(zip(idx['trade_date'], (idx['close'] > idx['ma20']).astype(int)))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n):
    res = []
    for y in ['2018','2019','2020','2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dts = sorted(yd['trade_date'].unique())[::20]
        
        cap = 1000000
        cash = cap
        h = {}
        
        for rd in dts:
            # 用当日全部数据计算权益
            rd_all = yd[yd['trade_date']==rd]
            eq = cash
            for k in h:
                kd = rd_all[rd_all['ts_code']==k]
                if not kd.empty:
                    eq += h[k]['s'] * float(kd['close'].iloc[0])
            
            mkt = idx_dict.get(rd, 1)
            if mkt == 0:
                for k in list(h.keys()):
                    kd = rd_all[rd_all['ts_code']==k]
                    if not kd.empty:
                        cash += h[k]['s'] * float(kd['close'].iloc[0])
                h = {}
                continue
            
            # 选股
            cd = yd[yd['trade_date']==rd].nlargest(n, 'ret20')
            if cd.empty: continue
            
            tgt = eq * p / len(cd)
            
            # 卖出
            for k in list(h.keys()):
                kd = cd[cd['ts_code']==k]
                if kd.empty:
                    # 不在top里，尝试用当日收盘价卖出
                    kd_all = rd_all[rd_all['ts_code']==k]
                    if not kd_all.empty:
                        cash += h[k]['s'] * float(kd_all['close'].iloc[0])
                        del h[k]
            
            # 买入
            for _, r in cd.iterrows():
                if r['ts_code'] not in h:
                    sh = int(tgt / r['close'])
                    if sh > 0: h[r['ts_code']] = {'s': sh, 'p': r['close']}
        
        # 年末
        rd = sorted(yd['trade_date'].unique())[-1]
        rd_all = yd[yd['trade_date']==rd]
        fv = cash
        for k in h:
            kd = rd_all[rd_all['ts_code']==k]
            if not kd.empty:
                fv += h[k]['s'] * float(kd['close'].iloc[0])
        
        res.append({'year': y, 'ret': (fv-cap)/cap, 'final': fv})
    return res

# 测试
best, best_r = {'p':0.5,'s':0.15,'n':5}, None
best_avg = -999

for p in [0.3, 0.5, 0.7]:
    for s in [0.10, 0.15]:
        for n in [5, 8]:
            r = bt(p, s, n)
            avg = np.mean([x['ret'] for x in r])
            if avg > best_avg:
                best_avg, best, best_r = avg, {'p':p,'s':s,'n':n}, r

yearly = [f"{d['year']}: {d['ret']*100:+.1f}%" for d in best_r]
avg = np.mean([d['ret'] for d in best_r]) * 100

print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}%")

with open(f'{OUT}/v9_{datetime.now().strftime("%Y%m%d_%H%M")}.txt', 'w') as f:
    f.write(f"参数: {best}\n平均: {avg}%\n" + "\n".join(yearly))
print("✅")
