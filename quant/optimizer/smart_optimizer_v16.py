#!/usr/bin/env python3
"""v16 - 使用补齐的因子数据优化"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("v16 因子优化版")
print("="*50)

# 加载因子数据
print("\n[1] 加载因子数据...")
df = pd.read_sql("""
    SELECT ts_code, trade_date, ret_20, ret_60, ret_120, 
           vol_20, vol_ratio, ma_20, ma_60,
           price_pos_20, price_pos_60, price_pos_high,
           vol_ratio_amt, money_flow, rel_strength, mom_accel, profit_mom
    FROM stock_factors
    WHERE trade_date BETWEEN '20180101' AND '20211231'
""", sqlite3.connect(DB))
print(f"因子数据: {len(df)} 条")

# 大盘择时
print("\n[2] 计算大盘信号...")
idx = df.groupby('trade_date')['ret_20'].median().reset_index()
idx['ma5'] = idx['ret_20'].rolling(5).mean()
idx['signal'] = (idx['ma5'] > 0).astype(int)  # 动量正时做多
idx_dict = dict(zip(idx['trade_date'], idx['signal']))

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n, mode):
    """多模式回测"""
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
            hv = sum(holdings[c]['shares'] * float(rd_data[rd_data['ts_code']==c]['ret_20'].iloc[0]) 
                    for c in holdings if not rd_data[rd_data['ts_code']==c].empty) * 0  # 简化
            # 重新计算
            holdings_val = 0
            for c in holdings:
                cd = rd_data[rd_data['ts_code']==c]
                if not cd.empty:
                    # 用价格计算需要回查，这里简化用ret_20估算
                    holdings_val += holdings[c]['shares'] * (1 + holdings[c]['cost_ret'])
            total = cash + holdings_val
            
            # 择时
            signal = idx_dict.get(rd, 1)
            if signal == 0:
                cash += holdings_val
                holdings = {}
                continue
            
            # 选股 - 不同因子组合
            cand = rd_data[rd_data['ret_20'].notna()].copy()
            
            if mode == 'alpha':
                # Alpha优先 (相对强弱)
                cand = cand.nlargest(n, 'rel_strength')
            elif mode == 'momentum':
                # 动量
                cand = cand.nlargest(n, 'ret_20')
            elif mode == 'quality':
                # 质量 (低波动)
                cand = cand[cand['vol_ratio'] < cand['vol_ratio'].quantile(0.5)]
                cand = cand.nlargest(n, 'rel_strength')
            elif mode == 'trend':
                # 趋势 (价格在均线上)
                cand = cand[cand['price_pos_20'] > 1.0]
                cand = cand.nlargest(n, 'ret_20')
            elif mode == 'combo':
                # 综合评分
                cand['score'] = (
                    cand['rel_strength'].rank(pct=0.4) * 0.3 +
                    (1 - cand['vol_ratio'].rank(pct=0.4)).fillna(0.5) * 0.2 +
                    cand['ret_20'].rank(pct=0.4) * 0.2 +
                    cand['mom_accel'].rank(pct=0.4).fillna(0.5) * 0.15 +
                    cand['price_pos_high'].rank(pct=0.4).fillna(0.5) * 0.15
                )
                cand = cand.nlargest(n, 'score')
            
            if cand.empty: continue
            
            # 用ret_20估算当前价格
            base_prices = rd_data[['ts_code', 'ret_20']].dropna()
            tgt = total * p / len(cand)
            
            # 卖出
            for c in list(holdings.keys()):
                if c not in cand['ts_code'].values:
                    ret_row = base_prices[base_prices['ts_code']==c]
                    if not ret_row.empty:
                        proceeds = holdings[c]['shares'] * (1 + ret_row['ret_20'].iloc[0])
                        cash += proceeds
                        del holdings[c]
            
            # 买入
            for _, r in cand.iterrows():
                if r['ts_code'] in holdings: continue
                price_est = 1 + r['ret_20']  # 简化
                sh = int(tgt / price_est)
                if sh > 0:
                    holdings[r['ts_code']] = {'shares': sh, 'cost_ret': r['ret_20']}
                    cash -= sh * price_est
            
            # 止损
            for c in list(holdings.keys()):
                ret_row = base_prices[base_prices['ts_code']==c]
                if not ret_row.empty:
                    cur_ret = ret_row['ret_20'].iloc[0]
                    if cur_ret - holdings[c]['cost_ret'] < -s:
                        proceeds = holdings[c]['shares'] * (1 + cur_ret)
                        cash += proceeds
                        del holdings[c]
        
        # 年末
        rd = dates[-1]
        rd_data = yd[yd['trade_date']==rd]
        base = rd_data[['ts_code', 'ret_20']].dropna()
        fv = cash
        for c in holdings:
            br = base[base['ts_code']==c]
            if not br.empty:
                fv += holdings[c]['shares'] * (1 + br['ret_20'].iloc[0])
        
        res.append({'year': y, 'return': (fv - init) / init})
    
    return res

# 测试
print("\n[3] 测试多模式...")
modes = ['alpha', 'momentum', 'quality', 'trend', 'combo']
configs = [
    {'p': 0.5, 's': 0.08, 'n': 10, 'mode': 'alpha'},
    {'p': 0.7, 's': 0.08, 'n': 10, 'mode': 'alpha'},
    {'p': 1.0, 's': 0.08, 'n': 10, 'mode': 'combo'},
    {'p': 0.5, 's': 0.10, 'n': 10, 'mode': 'combo'},
    {'p': 0.7, 's': 0.10, 'n': 10, 'mode': 'combo'},
    {'p': 1.0, 's': 0.10, 'n': 10, 'mode': 'combo'},
]

best = None
best_r = None
best_avg = -999

for cfg in configs:
    r = bt(cfg['p'], cfg['s'], cfg['n'], cfg['mode'])
    avg = np.mean([x['return'] for x in r])
    loss = sum(1 for x in r if x['return'] < 0)
    score = avg - loss * 0.15
    if score > best_avg:
        best_avg = score
        best = cfg
        best_r = r

yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
avg = np.mean([d['return'] for d in best_r]) * 100
loss_years = sum(1 for d in best_r if d['return'] < 0)

print(f"\n🏆 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只")
print(f"   模式: {best['mode']}")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}% | 亏损: {loss_years}年")

# 保存
fn = f'{OUT}/v16_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
with open(fn, 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n")
    f.write(f"模式: {best['mode']}\n")
    f.write(f"平均: {avg:+.1f}%\n" + "\n".join(yearly))

print(f"\n✅ 已保存 {fn}")
