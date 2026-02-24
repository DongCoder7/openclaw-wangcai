#!/usr/bin/env python3
"""智能优化器 v11 - 调优版"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*40)
print("v11 调优版...")

# 取500只
df = pd.read_sql("""
    SELECT ts_code, trade_date, close FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*) > 200 LIMIT 500)
""", sqlite3.connect(DB))

df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ret60'] = df.groupby('ts_code')['close'].pct_change(60)

# 大盘
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['ma60'] = idx['close'].rolling(60).mean()
idx_dict = dict(zip(idx['trade_date'], (idx['close'] > idx['ma20']).astype(int)))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n):
    years = ['2018','2019','2020','2021']
    res = []
    
    for y in years:
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
            
            # 市值
            hv = 0.0
            for code, pos in holdings.items():
                prc = rd_data[rd_data['ts_code'] == code]
                if not prc.empty:
                    hv += pos['shares'] * float(prc['close'].iloc[0])
            total = cash + hv
            
            # 择时
            mkt = idx_dict.get(rd, 1)
            if mkt == 0:
                for code in list(holdings.keys()):
                    prc = rd_data[rd_data['ts_code'] == code]
                    if not prc.empty:
                        cash += holdings[code]['shares'] * float(prc['close'].iloc[0])
                holdings = {}
                continue
            
            # 选股：动量+趋势
            cand = rd_data[rd_data['ret20'].notna() & (rd_data['ret20'] > 0)]
            cand = cand.nlargest(n, 'ret20')
            if cand.empty: continue
            
            tgt = total * p / len(cand)
            
            # 卖出
            for code in list(holdings.keys()):
                if code not in cand['ts_code'].values:
                    prc = rd_data[rd_data['ts_code'] == code]
                    if not prc.empty:
                        cash += holdings[code]['shares'] * float(prc['close'].iloc[0])
                        del holdings[code]
            
            # 买入
            for _, row in cand.iterrows():
                if row['ts_code'] in holdings: continue
                price = float(row['close'])
                shares = int(tgt / price)
                if shares > 0:
                    holdings[row['ts_code']] = {'shares': shares, 'cost': price}
                    cash -= shares * price
            
            # 止损
            for code in list(holdings.keys()):
                prc = rd_data[rd_data['ts_code'] == code]
                if not prc.empty:
                    cur = float(prc['close'].iloc[0])
                    if (cur - holdings[code]['cost']) / holdings[code]['cost'] < -s:
                        cash += holdings[code]['shares'] * cur
                        del holdings[code]
        
        # 年末
        rd = dates[-1]
        rd_data = yd[yd['trade_date'] == rd]
        fv = cash
        for code, pos in holdings.items():
            prc = rd_data[rd_data['ts_code'] == code]
            if not prc.empty:
                fv += pos['shares'] * float(prc['close'].iloc[0])
        
        res.append({'year': y, 'return': (fv - init) / init, 'final': fv})
    
    return res

# 测试更多参数
print("\n优化...")
best = {'p': 0.5, 's': 0.1, 'n': 5}
best_r = None
best_avg = -999

for p in [0.3, 0.5, 0.7, 1.0]:
    for s in [0.08, 0.10, 0.15, 0.20]:
        for n in [3, 5, 8, 10]:
            r = bt(p, s, n)
            avg = np.mean([x['return'] for x in r])
            # 惩罚亏损年份
            loss_years = sum(1 for x in r if x['return'] < 0)
            score = avg - loss_years * 0.05
            if score > best_avg:
                best_avg = score
                best = {'p': p, 's': s, 'n': n}
                best_r = r

yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
avg = np.mean([d['return'] for d in best_r]) * 100
loss = sum(1 for d in best_r if d['return'] < 0)

print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}% | 亏损年份: {loss}年")

fn = f'{OUT}/v11_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
with open(fn, 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n平均: {avg:+.1f}%\n" + "\n".join(yearly))
print("✅")
