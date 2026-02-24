#!/usr/bin/env python3
"""智能优化器 v14 - VQM+AlphaBeta模型"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("v14 VQM+AlphaBeta模型")
print("="*50)

# 取数据
df = pd.read_sql("""
    SELECT ts_code, trade_date, close, volume FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*) > 200 LIMIT 300)
""", sqlite3.connect(DB))

# 计算VQM指标
print("计算VQM指标...")
df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)   # 动量
df['ret60'] = df.groupby('ts_code')['close'].pct_change(60)   # 中期动量
df['vol20_std'] = df.groupby('ts_code')['close'].transform(lambda x: x.rolling(20).std())  # 波动率

# 用ret20的倒数近似"估值"（跌多的可能估值低）
df['val_score'] = -df['ret20']  # 跌得多的得分高（假设超跌反弹）

# 质量用波动率（波动小的质量好）
df['qual_score'] = -df['vol20_std'] / df.groupby('ts_code')['vol20_std'].transform(lambda x: x.rolling(60).mean())

# 动量
df['mom_score'] = df['ret20']

# 合成VQM分数
df['vqm'] = df['val_score'] * 0.4 + df['qual_score'] * 0.4 + df['mom_score'] * 0.2

# 大盘（用于Beta）
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ret20'] = idx['close'].pct_change(20)
idx['ma20'] = idx['close'].rolling(20).mean()
idx['trend'] = (idx['close'] > idx['ma20']).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['trend']))
# 计算Alpha（相对于大盘的超额收益）
idx['alpha'] = 0  # 先设为0，后续用持仓相对于大盘计算

print(f"股票: {df['ts_code'].nunique()}")

def bt(p, s, n, use_vqm):
    """VQM+择时回测"""
    res = []
    for y in ['2018','2019','2020','2021']:
        yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
        dates = sorted(yd['trade_date'].unique())
        
        init = 1000000.0
        cash = init
        holdings = {}
        
        # 记录每日收益用于计算alpha
        daily_rets = []
        
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
            if trend == 0:  # 大盘下跌时空仓
                for c in list(holdings.keys()):
                    prc = rd_data[rd_data['ts_code']==c]
                    if not prc.empty:
                        cash += holdings[c]['shares'] * float(prc['close'].iloc[0])
                holdings = {}
                continue
            
            # 选股
            cand = rd_data[rd_data['vqm'].notna()].copy()
            if use_vqm:
                cand = cand[cand['vqm'] > cand['vqm'].quantile(0.3)]  # VQM前70%
            cand = cand.nlargest(n, 'vqm')
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
    {'p': 0.3, 's': 0.08, 'n': 5, 'use_vqm': True},
    {'p': 0.5, 's': 0.08, 'n': 5, 'use_vqm': True},
    {'p': 0.7, 's': 0.08, 'n': 5, 'use_vqm': True},
    {'p': 1.0, 's': 0.08, 'n': 5, 'use_vqm': True},
    {'p': 0.5, 's': 0.10, 'n': 10, 'use_vqm': True},
    {'p': 1.0, 's': 0.10, 'n': 10, 'use_vqm': True},
]

best = None
best_r = None
best_avg = -999

for cfg in configs:
    r = bt(cfg['p'], cfg['s'], cfg['n'], cfg['use_vqm'])
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
print(f"   VQM选股: {'是' if best['use_vqm'] else '否'}")
print("📈 " + " | ".join(yearly))
print(f"📊 平均: {avg:+.1f}% | 亏损: {loss_years}年")

# 保存
fn = f'{OUT}/v14_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
with open(fn, 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n")
    f.write(f"VQM选股: {'是' if best['use_vqm'] else '否'}\n")
    f.write(f"平均: {avg:+.1f}%\n" + "\n".join(yearly))

print(f"\n✅ 已保存 {fn}")
