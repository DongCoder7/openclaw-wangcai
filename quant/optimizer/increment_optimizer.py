#!/usr/bin/env python3
"""
增量优化器 - 基于历史结果继续优化
读取上一次的最优参数，在其周围搜索更优解
"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime
import json
import re

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

def load_last_best():
    """读取上一次的最优参数"""
    try:
        with open(f'{OUT}/best_params.json', 'r') as f:
            return json.load(f)
    except:
        return None

def parse_last_report():
    """从latest_report.txt解析参数"""
    try:
        with open(f'{OUT}/latest_report.txt', 'r') as f:
            content = f.read()
        
        # 解析: 仓位: 100% | 止损: 5% | 持仓: 3只
        p_match = re.search(r'仓位:\s*(\d+)%', content)
        s_match = re.search(r'止损:\s*(\d+)%', content)
        n_match = re.search(r'持仓:\s*(\d+)', content)
        
        if p_match and s_match and n_match:
            return {
                'p': int(p_match.group(1)) / 100,
                's': int(s_match.group(1)) / 100,
                'n': int(n_match.group(1))
            }
    except Exception as e:
        print(f"解析报告失败: {e}")
    return None

print("="*60)
print("v23 增量优化器")
print("="*60)

# 加载上一次的最优参数
last_best = load_last_best() or parse_last_report()

if last_best:
    print(f"上一次最优参数: 仓位{last_best['p']*100:.0f}% 止损{last_best['s']*100:.0f}% 持仓{last_best['n']}只")
    # 在上次参数周围小范围搜索
    p_range = [max(0.3, last_best['p'] - 0.2), last_best['p'], min(1.0, last_best['p'] + 0.2)]
    s_range = [max(0.05, last_best['s'] - 0.05), last_best['s'], min(0.20, last_best['s'] + 0.05)]
    n_range = [max(3, last_best['n'] - 2), last_best['n'], min(10, last_best['n'] + 2)]
else:
    print("未找到历史参数，使用默认范围")
    p_range = [0.5, 0.7, 1.0]
    s_range = [0.05, 0.08, 0.10]
    n_range = [3, 5, 8]

# 去重
p_range = sorted(list(set([round(x, 2) for x in p_range])))
s_range = sorted(list(set([round(x, 2) for x in s_range])))
n_range = sorted(list(set([int(x) for x in n_range])))

print(f"搜索范围: 仓位{p_range} | 止损{s_range} | 持仓{n_range}")

# 加载数据（复用v23逻辑）
conn = sqlite3.connect(DB)
df = pd.read_sql("""
    SELECT e.ts_code, e.trade_date, e.close, e.volume, e.amount,
           f.ret_20, f.ret_60, f.ret_120, f.vol_20, f.vol_ratio, f.ma_20, f.ma_60,
           f.money_flow, f.rel_strength, f.mom_accel, f.price_pos_20, f.price_pos_60
    FROM stock_efinance e
    LEFT JOIN stock_factors f ON e.ts_code = f.ts_code AND e.trade_date = f.trade_date
    WHERE e.trade_date BETWEEN '20180101' AND '20211231'
    AND e.ts_code IN (SELECT DISTINCT ts_code FROM stock_efinance GROUP BY ts_code HAVING COUNT(*) > 900)
""", conn)
conn.close()

df = df[df['ret_20'].notna()]

# 因子
df['score'] = (
    df['ret_20'].rank(pct=True) * 0.20 +
    df['ret_60'].rank(pct=True) * 0.15 +
    df['mom_accel'].rank(pct=True) * 0.15 +
    (1 - df['vol_20'].rank(pct=True)) * 0.15 +
    df['money_flow'].rank(pct=True) * 0.15 +
    df['price_pos_20'].rank(pct=True) * 0.20
)

# 择时
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['trend'] = (idx['close'] > idx['ma20']).astype(int)
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
            
            for c in list(h.keys()):
                cd = rd_d[rd_d['ts_code']==c]
                if not cd.empty:
                    ret = (float(cd['close'].iloc[0]) - h[c]['p']) / h[c]['p']
                    if ret < -s:
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                        del h[c]
                    elif ret > 0.15:
                        cash += h[c]['s'] * float(cd['close'].iloc[0])
                        del h[c]
        
        rd = dates[-1]
        rd_d = yd[yd['trade_date']==rd]
        fv = cash + sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) 
                       for c in h if not rd_d[rd_d['ts_code']==c].empty)
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

print("[增量回测...]")
best, best_r, best_avg = last_best, None, -999

for p in p_range:
    for s in s_range:
        for n in n_range:
            for rebal in [10, 15]:
                r = bt(p, s, n, rebal)
                if not r: continue
                avg = np.mean([x['return'] for x in r])
                loss = sum(1 for x in r if x['return'] < 0)
                score = avg - loss * 0.1
                if score > best_avg:
                    best_avg = score
                    best = {'p':p,'s':s,'n':n,'rebal':rebal}
                    best_r = r

if best_r:
    yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
    avg = np.mean([d['return'] for d in best_r]) * 100
    
    print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
    print("📈 " + " | ".join(yearly))
    print(f"📊 平均: {avg:+.1f}%")
    
    # 保存最优参数
    with open(f'{OUT}/best_params.json', 'w') as f:
        json.dump(best, f)
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f'{OUT}/latest_report.txt', 'w') as f:
        f.write(f"📊 **v23增量优化** ({ts})\n\n仓位: {best['p']*100:.0f}% | 止损: {best['s']*100:.0f}% | 持仓: {best['n']}只\n📈 " + " | ".join(yearly) + f"\n📊 平均: {avg:+.1f}%\n⏰ 更新时间: {ts}")
    
    print("\n✅ 增量优化完成")
else:
    print("❌ 无有效结果")
