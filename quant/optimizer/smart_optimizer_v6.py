#!/usr/bin/env python3
"""智能优化器 v6 - 修复资金计算bug"""
import sqlite3, pandas as pd, numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

print("="*50)
print("📊 智能优化器 v6 - 修复版")
print("="*50)

# 加载数据
df = pd.read_sql("""
    SELECT ts_code, trade_date, close 
    FROM daily_price 
    WHERE trade_date BETWEEN '20180101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*)>150)
""", sqlite3.connect(DB))

df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ma60'] = df.groupby('ts_code')['close'].rolling(60).mean().reset_index(level=0, drop=True)

# 大盘择时
idx = df.groupby('trade_date')['close'].median().reset_index()
idx['ma20'] = idx['close'].rolling(20).mean()
idx['signal'] = (idx['close'] > idx['ma20']).astype(int)
idx_dict = dict(zip(idx['trade_date'], idx['signal']))

print(f"股票: {df['ts_code'].nunique()}")

def run_backtest(p, s, n):
    """回测 - 修复资金计算"""
    years = ['2018', '2019', '2020', '2021']
    results = []
    
    for y in years:
        ydf = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')].copy()
        dts = sorted(ydf['trade_date'].unique())
        if len(dts) < 50:
            continue
        
        # 初始资金
        init_cap = 1000000
        cash = init_cap
        holdings = {}
        
        for rd in dts[::20]:  # 每20天调仓
            mkt = idx_dict.get(rd, 1)
            
            # 当前总权益
            holdings_value = 0
            for h in holdings:
                hdf = ydf[(ydf['trade_date']==rd) & (ydf['ts_code']==h)]
                if not hdf.empty:
                    holdings_value += holdings[h]['s'] * float(hdf['close'].iloc[0])
            total_equity = cash + holdings_value
            
            if mkt == 0:  # 空仓
                for h in list(holdings.keys()):
                    hdf = ydf[(ydf['trade_date']==rd) & (ydf['ts_code']==h)]
                    if not hdf.empty:
                        cash += holdings[h]['s'] * float(hdf['close'].iloc[0])
                holdings = {}
                continue
            
            cd = ydf[ydf['trade_date']==rd]
            cd = cd[cd['ret20'].notna() & (cd['close'] > cd['ma60']) & (cd['ret20'] > 0)]
            if cd.empty:
                continue
            
            top = cd.nlargest(n, 'ret20')
            
            # 用当前权益计算仓位
            position_value = total_equity * p
            target = position_value / len(top) if len(top) > 0 else 0
            
            # 卖出
            for h in list(holdings.keys()):
                if h not in top['ts_code'].values:
                    hdf = cd[cd['ts_code']==h]
                    if not hdf.empty:
                        cash += holdings[h]['s'] * float(hdf['close'].iloc[0])
                        del holdings[h]
            
            # 止损
            for h in list(holdings.keys()):
                hdf = cd[cd['ts_code']==h]
                if not hdf.empty:
                    pr = float(hdf['close'].iloc[0])
                    if (pr - holdings[h]['p']) / holdings[h]['p'] < -s:
                        cash += holdings[h]['s'] * pr
                        del holdings[h]
            
            # 买入
            for _, r in top.iterrows():
                if r['ts_code'] in holdings:
                    continue
                sh = int(target / r['close'])
                if sh > 0:
                    holdings[r['ts_code']] = {'s': sh, 'p': float(r['close'])}
        
        # 年末结算
        rd = dts[-1]
        fd = ydf[ydf['trade_date']==rd]
        fv = cash
        for h in holdings:
            hdf = fd[fd['ts_code']==h]
            if not hdf.empty:
                fv += holdings[h]['s'] * float(hdf['close'].iloc[0])
        
        ret = (fv - init_cap) / init_cap
        results.append({'year': y, 'return': ret, 'final': fv})
    
    return results

# 优化
print("\n优化中...")
best = {'p': 0.5, 's': 0.15, 'n': 5}
best_ret = -999

for p in [0.3, 0.5, 0.7]:
    for s in [0.08, 0.10, 0.15]:
        for n in [5, 8]:
            r = run_backtest(p, s, n)
            if not r:
                continue
            avg = np.mean([x['return'] for x in r])
            if avg > best_ret:
                best_ret = avg
                best = {'p': p, 's': s, 'n': n}
                best_result = r

# 输出
yearly = []
for d in best_result:
    yearly.append(f"📊 {d['year']}: {d['return']*100:+.2f}% | ¥{d['final']:,.0f}")

avg_ret = np.mean([d['return'] for d in best_result]) * 100

print(f"\n🏆 参数: 仓位{best['p']*100:.0f}% | 止损{best['s']*100:.0f}% | 持仓{best['n']}只")
print(f"\n📈 年度")
for y in yearly:
    print(y)
print(f"\n📊 平均: {avg_ret:+.2f}%")

report = f"""
╔═══════════════════════════════════════╗
║   📈 智能优化 v6 - 修复版           ║
║   {datetime.now().strftime('%Y-%m-%d %H:%M')}                         ║
╚═══════════════════════════════════════╝

🏆 参数: 仓位{best['p']*100:.0f}% | 止损{best['s']*100:.0f}% | 持仓{best['n']}只

📈 年度
{chr(10).join(yearly)}

📊 平均: {avg_ret:+.2f}%

💡 优化:
1. 大盘择时 - 20日均线下方空仓
2. 趋势确认 - 60日线上
3. 动量过滤 - 20日涨
4. 止损{best['s']*100:.0f}%
5. 资金滚动 - 用当前权益计算仓位
"""

with open(f'{OUT}/v6_report_{datetime.now().strftime("%Y%m%d_%H%M")}.txt', 'w') as f:
    f.write(report)

print("\n✅ 完成!")
