#!/usr/bin/env python3
"""v22 - 多因子优化器 (简化版)"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*60)
print("v22 多因子优化器")
print("="*60)

conn = sqlite3.connect(DB)

# 加载价格和因子
df = pd.read_sql("""
    SELECT e.ts_code, e.trade_date, e.close, e.volume, e.amount,
           f.ret_20, f.ret_60, f.ret_120, f.vol_20, f.ma_20, f.ma_60,
           f.money_flow, f.rel_strength, f.mom_accel
    FROM stock_efinance e
    LEFT JOIN stock_factors f ON e.ts_code = f.ts_code AND e.trade_date = f.trade_date
    WHERE e.trade_date BETWEEN '20180101' AND '20211231'
    AND e.ts_code IN (SELECT DISTINCT ts_code FROM stock_efinance GROUP BY ts_code HAVING COUNT(*) > 900)
""", conn)

conn.close()

print(f"股票数: {df['ts_code'].nunique()}")

# 清洗数据
df = df[df['ret_20'].notna()]

# 计算综合因子
df['trend'] = (df['close'] - df['ma_20']) / df['ma_20']
df['score'] = (
    df['ret_20'].rank(pct=True) * 0.25 +
    df['ret_60'].rank(pct=True) * 0.20 +
    (1 - df['vol_20'].rank(pct=True)) * 0.15 +  # 低波动更好
    df['money_flow'].rank(pct=True) * 0.20 +
    df['mom_accel'].rank(pct=True) * 0.20
)

# 大盘择时
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['signal'] = (idx['close'] > idx['ma20']).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['signal']))

print("[回测...]")

def bt(p, s, n):
    res = []
    for y in ['2018','2019','2020','2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dates = sorted(yd['trade_date'].unique())
        if len(dates) < 10: continue
        
        init = 1000000.0
        cash = init
        h = {}
        
        for rd in dates[::15]:
            rd_d = yd[yd['trade_date']==rd]
            
            # 权益
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
            cand = rd_d[rd_d['score'].notna()].nlargest(n, 'score')
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
        
        rd = dates[-1]
        rd_d = yd[yd['trade_date']==rd]
        fv = cash + sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) 
                       for c in h if not rd_d[rd_d['ts_code']==c].empty)
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

# 测试
best, best_r = None, None
best_avg = -999

for p in [0.5, 0.7, 1.0]:
    for s in [0.05, 0.08, 0.10, 0.15]:
        for n in [5, 8, 10]:
            r = bt(p, s, n)
            if not r: continue
            avg = np.mean([x['return'] for x in r])
            loss = sum(1 for x in r if x['return'] < 0)
            score = avg - loss * 0.1
            if score > best_avg:
                best_avg = score
                best = {'p':p, 's':s, 'n':n}
                best_r = r

if best_r:
    yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
    avg = np.mean([d['return'] for d in best_r]) * 100
    
    print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
    print("📈 " + " | ".join(yearly))
    print(f"📊 平均: {avg:+.1f}%")
    
    # 保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    result = f"v22 多因子优化\n仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n平均: {avg:+.1f}%\n" + "\n".join(yearly)
    
    with open(f'{OUT}/v22_{ts}.txt', 'w') as f:
        f.write(result)
    
    report = f"📊 **v22 优化汇报** ({ts})\n\n" + \
             f"仓位: {best['p']*100:.0f}% | 止损: {best['s']*100:.0f}% | 持仓: {best['n']}只\n" + \
             "📈 " + " | ".join(yearly) + f"\n📊 平均: {avg:+.1f}%"
    
    with open(f'{OUT}/latest_report.txt', 'w') as f:
        f.write(report)
    
    print("\n✅ 完成")
else:
    print("❌ 失败")
