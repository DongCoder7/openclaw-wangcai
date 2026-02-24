#!/usr/bin/env python3
"""极速优化器 - 简化版"""
import sqlite3, pandas as pd, numpy as np, json, random
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("加载数据...")
df = pd.read_sql("""
    SELECT ts_code, trade_date, close 
    FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*)>150)
""", sqlite3.connect(DB))
df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
print(f"股票: {df['ts_code'].nunique()}")

def bt(params):
    yearly = []
    for y in ['2018','2019','2020','2021']:
        ydf = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dts = sorted(ydf['trade_date'].unique())
        if len(dts) < 100: continue
        cap, cash, holdings = 1000000, 1000000*(1-params['p']), {}
        init = ydf[ydf['trade_date']==dts[20]]
        for _,r in init.nlargest(6,'ret20').iterrows():
            if r['close']>0: holdings[r['ts_code']]={'s':int(cap*params['p']/6/r['close']),'c':r['close']}
        for m in range(2,13):
            md = [d for d in dts if d.startswith(f'{y}{m:02d}')]
            if not md: continue
            cd = ydf[ydf['trade_date']==md[0]]
            for c in list(holdings.keys()):
                d = cd[cd['ts_code']==c]
                if not d.empty and (d['close'].iloc[0]-holdings[c]['c'])/holdings[c]['c'] < -params['s']:
                    cash += holdings[c]['s']*d['close'].iloc[0]
                    del holdings[c]
        fv = cash + sum(h['s']*cd[cd['ts_code']==c]['close'].iloc[0] for c,h in holdings.items() if not cd[cd['ts_code']==c].empty)
        yearly.append((fv-cap)/cap)
    return sum(yearly)/4 if yearly else -1

print("优化中...")
best = {'p':0.6,'s':0.15}
best_ret = bt(best)

for i in range(100):
    p = random.choice([0.5,0.6,0.7,0.8])
    s = random.choice([0.10,0.15,0.20,0.25])
    r = bt({'p':p,'s':s})
    if r > best_ret:
        best_ret, best = r, {'p':p,'s':s}

print(f"\n🏆 最优: 仓位{best['p']*100:.0f}%, 止损{best['s']*100:.0f}% = {best_ret*100:+.1f}%")

# 发送结果汇报
import subprocess
msg = f"📊 策略优化完成\n\n🏆 最优: 仓位{best['p']*100:.0f}%, 止损{best['s']*100:.0f}%\n📈 收益: {best_ret*100:+.2f}%"
subprocess.run(['curl', '-s', '-X', 'POST', 
    'http://localhost:8000/message/send', 
    '-H', 'Content-Type: application/json',
    '-d', json.dumps({
        "to": "ou_efbad805767f4572e8f93ebafa8d5402",
        "message": msg
    })], capture_output=True)

with open(f'{OUT}/best_params.json','w') as f:
    json.dump({'params':best,'return':best_ret,'time':str(datetime.now())},f)
print("✅ 完成")
