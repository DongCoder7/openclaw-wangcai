#!/usr/bin/env python3
"""智能优化器 v15 - 多Skill融合版"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("v15 多Skill融合版")
print("="*50)

# 取数据
df = pd.read_sql("""
    SELECT ts_code, trade_date, close, volume FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*) > 200 LIMIT 400)
""", sqlite3.connect(DB))

# ============ 计算各种因子 ============
print("计算因子...")

# 1. 动量因子 (Momentum)
df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ret60'] = df.groupby('ts_code')['close'].pct_change(60)
df['ret120'] = df.groupby('ts_code')['close'].pct_change(120)

# 2. 波动率因子 (Volatility) - 用于质量评估
df['vol20'] = df.groupby('ts_code')['close'].rolling(20).std().reset_index(level=0, drop=True)
df['vol60'] = df.groupby('ts_code')['close'].rolling(60).std().reset_index(level=0, drop=True)
df['vol_ratio'] = df['vol20'] / df['vol60']  # 波动率趋势

# 3. 成交量因子 (Volume)
df['vol_ma20'] = df.groupby('ts_code')['volume'].rolling(20).mean().reset_index(level=0, drop=True)
df['vol_ratio'] = df['volume'] / df['vol_ma20']

# 4. 趋势因子 (Trend) - a-sector-analysis需要
df['ma20'] = df.groupby('ts_code')['close'].rolling(20).mean().reset_index(level=0, drop=True)
df['ma60'] = df.groupby('ts_code')['close'].rolling(60).mean().reset_index(level=0, drop=True)
df['above_ma20'] = (df['close'] > df['ma20']).astype(int)
df['above_ma60'] = (df['close'] > df['ma60']).astype(int)

# 5. 相对强弱 (Relative Strength)
df['rs'] = df['ret20'] / df['vol20']  # 单位波动率的收益

# ============ 大盘择时 ============
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['ma60'] = idx['close'].rolling(60).mean()
# 多重择时：趋势确认+动量确认
idx['trend'] = ((idx['close'] > idx['ma20']) & (idx['close'] > idx['ma60'])).astype(int)
idx['momentum'] = (idx['close'].pct_change(10) > 0).astype(int)
idx['signal'] = idx['trend'] * idx['momentum']  # 双重确认
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
            hv = sum(holdings[c]['shares'] * float(rd_data[rd_data['ts_code']==c]['close'].iloc[0]) 
                    for c in holdings if not rd_data[rd_data['ts_code']==c].empty)
            total = cash + hv
            
            # 择时
            signal = idx_dict.get(rd, 1)
            if signal == 0:  # 空仓信号
                for c in list(holdings.keys()):
                    prc = rd_data[rd_data['ts_code']==c]
                    if not prc.empty:
                        cash += holdings[c]['shares'] * float(prc['close'].iloc[0])
                holdings = {}
                continue
            
            # 选股 - 不同模式
            cand = rd_data[rd_data['ret20'].notna()].copy()
            
            if mode == 'momentum':
                # 纯动量
                cand = cand.nlargest(n, 'ret20')
            elif mode == 'quality':
                # 质量优先（低波动）
                cand = cand[cand['vol20'] < cand['vol20'].quantile(0.5)]
                cand = cand.nlargest(n, 'ret20')
            elif mode == 'trend':
                # 趋势确认
                cand = cand[(cand['above_ma20']==1) & (cand['above_ma60']==1)]
                cand = cand.nlargest(n, 'ret20')
            elif mode == 'rs':
                # 相对强弱
                cand = cand.nlargest(n, 'rs')
            elif mode == 'combo':
                # 综合评分 (VQM模拟)
                cand['score'] = (
                    cand['ret20'].rank(pct=0.4) * 0.3 +  # 动量
                    (1 - cand['vol20'].rank(pct=0.4)).fillna(0) * 0.3 +  # 质量(低波动)
                    cand['above_ma20'] * 0.2 +  # 趋势
                    cand['rs'].rank(pct=0.4).fillna(0) * 0.2  # 相对强弱
                )
                cand = cand.nlargest(n, 'score')
            
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

# 测试不同模式
print("\n测试多模式...")
modes = ['momentum', 'quality', 'trend', 'rs', 'combo']
configs = [
    {'p': 0.5, 's': 0.08, 'n': 10, 'mode': 'combo'},
    {'p': 0.7, 's': 0.08, 'n': 10, 'mode': 'combo'},
    {'p': 1.0, 's': 0.08, 'n': 10, 'mode': 'combo'},
    {'p': 0.5, 's': 0.10, 'n': 10, 'mode': 'trend'},
    {'p': 0.7, 's': 0.10, 'n': 10, 'mode': 'trend'},
    {'p': 1.0, 's': 0.10, 'n': 10, 'mode': 'rs'},
]

best = None
best_r = None
best_avg = -999

for cfg in configs:
    r = bt(cfg['p'], cfg['s'], cfg['n'], cfg['mode'])
    avg = np.mean([x['return'] for x in r])
    loss = sum(1 for x in r if x['return'] < 0)
    score = avg - loss * 0.15  # 加重亏损惩罚
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
fn = f'{OUT}/v15_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
with open(fn, 'w') as f:
    f.write(f"仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只\n")
    f.write(f"模式: {best['mode']}\n")
    f.write(f"平均: {avg:+.1f}%\n" + "\n".join(yearly))

print(f"\n✅ 已保存 {fn}")
