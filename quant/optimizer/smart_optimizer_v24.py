#!/usr/bin/env python3
"""v24 - 终极多因子版"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*60)
print("v24 终极多因子版")
print("="*60)

conn = sqlite3.connect(DB)
df = pd.read_sql("""
    SELECT e.ts_code, e.trade_date, e.close, e.volume, e.amount,
           f.ret_20, f.ret_60, f.ret_120, f.vol_20, f.vol_ratio, f.vol_ratio_amt,
           f.ma_20, f.ma_60, f.price_pos_20, f.price_pos_60, f.price_pos_high,
           f.money_flow, f.rel_strength, f.mom_accel, f.profit_mom
    FROM stock_efinance e
    LEFT JOIN stock_factors f ON e.ts_code = f.ts_code AND e.trade_date = f.trade_date
    WHERE e.trade_date BETWEEN '20180101' AND '20211231'
    AND e.ts_code IN (SELECT DISTINCT ts_code FROM stock_efinance GROUP BY ts_code HAVING COUNT(*) > 900)
""", conn)
conn.close()

print(f"股票数: {df['ts_code'].nunique()}")
df = df[df['ret_20'].notna()]

# ============ 增强因子 ============
# 动量因子
df['mom_20_60'] = df['ret_20'] - df['ret_60']  # 动量加速
df['mom_60_120'] = df['ret_60'] - df['ret_120']  # 中期动量
df['mom_trend'] = (df['ret_20'] > df['ret_60']).astype(float)  # 趋势确认

# 质量因子
df['price_strength'] = df['price_pos_20'] * df['ret_20']  # 强度
df['fund_quality'] = df['money_flow'] * df['rel_strength']  # 资金质量
df['profit_momentum'] = df['profit_mom'].fillna(0) * df['ret_20']  # 盈利动量

# 趋势位置因子
df['high_pos_score'] = df['price_pos_high'].fillna(0.5)  # 年内高位
df['break_high'] = (df['price_pos_20'] > 0.8).astype(float)  # 突破新高

# 波动性因子
df['low_vol_quality'] = (1 / (df['vol_20'] + 0.01)) * df['rel_strength']  # 低波动优质

# 综合评分 (更多因子)
df['score'] = (
    df['ret_20'].rank(pct=True) * 0.12 +
    df['ret_60'].rank(pct=True) * 0.08 +
    df['mom_accel'].rank(pct=True) * 0.10 +
    (1 - df['vol_20'].rank(pct=True)) * 0.08 +  # 低波动
    df['money_flow'].rank(pct=True) * 0.10 +
    df['price_pos_20'].rank(pct=True) * 0.10 +  # 趋势位置
    df['price_pos_high'].rank(pct=True) * 0.08 +  # 年内高位
    df['profit_mom'].rank(pct=True) * 0.10 +  # 盈利动量
    df['rel_strength'].rank(pct=True) * 0.08 +  # 相对强度
    df['mom_trend'].rank(pct=True) * 0.08 +  # 趋势确认
    df['break_high'].rank(pct=True) * 0.08  # 突破新高
)

# 择时 (更严格)
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['ma60'] = idx['close'].rolling(60).mean()
idx['trend'] = ((idx['close'] > idx['ma20']) & (idx['ma20'] > idx['ma60'])).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['trend']))

def bt(p, s, n, rebal=10):
    res = []
    for y in ['2018','2019','2020','2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dates = sorted(yd['trade_date'].unique())
        if len(dates) < 20: continue
        
        init = 1000000.0
        cash = init
        h = {}
        
        for rd in dates[::rebal]:
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
            
            cand = rd_d[rd_d['score'].notna()].nlargest(n, 'score')
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
            
            # 止损/止盈
            for c in list(h.keys()):
                cd = rd_d[rd_d['ts_code']==c]
                if not cd.empty:
                    ret = (float(cd['close'].iloc[0]) - h[c]['p']) / h[c]['p']
                    if ret < -s:  # 止损
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                        del h[c]
                    elif ret > 0.20:  # 止盈20%
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                        del h[c]
        
        rd = dates[-1]
        rd_d = yd[yd['trade_date']==rd]
        fv = cash + sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) 
                       for c in h if not rd_d[rd_d['ts_code']==c].empty)
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

print("[回测...]")
best, best_r, best_avg = None, None, -999

# 扩大搜索范围
for p in [0.3, 0.5, 0.7, 1.0]:
    for s in [0.05, 0.08, 0.10, 0.15, 0.20]:
        for n in [3, 5, 8, 10]:
            for rebal in [5, 10, 15, 20]:
                r = bt(p, s, n, rebal)
                if not r: continue
                avg = np.mean([x['return'] for x in r])
                loss = sum(1 for x in r if x['return'] < 0)
                score = avg - loss * 0.15  # 惩罚亏损年份
                if score > best_avg:
                    best_avg = score
                    best = {'p':p,'s':s,'n':n,'rebal':rebal}
                    best_r = r

if best_r:
    yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
    avg = np.mean([d['return'] for d in best_r]) * 100
    
    print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只 调仓{best['rebal']}天")
    print("📈 " + " | ".join(yearly))
    print(f"📊 平均: {avg:+.1f}%")
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f'{OUT}/latest_report.txt', 'w') as f:
        f.write(f"📊 **v24 优化汇报** ({ts})\n\n仓位: {best['p']*100:.0f}% | 止损: {best['s']*100:.0f}% | 持仓: {best['n']}只\n📈 " + " | ".join(yearly) + f"\n📊 平均: {avg:+.1f}%")
    
    with open(f'{OUT}/v24_{ts}.txt', 'w') as f:
        f.write(f"v24 终极多因子\n仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n" + " | ".join(yearly) + f"\n平均: {avg:+.1f}%")
    
    print("\n✅ 完成")
else:
    print("❌ 无有效结果")
