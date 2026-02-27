#!/usr/bin/env python3
"""
WFO v3 - 修复选股逻辑
"""
import sqlite3
import json
import random
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/wfo/results'


def get_factors(conn, ts_code, trade_date):
    row = conn.execute('''
        SELECT ret_20, ret_60, vol_20, price_pos_20 FROM stock_factors 
        WHERE ts_code = ? AND trade_date = ?
    ''', [ts_code, trade_date]).fetchone()
    
    if row:
        return {'ret_20': row[0], 'ret_60': row[1], 'vol_20': row[2], 'price_pos_20': row[3]}
    return {}


def score(factors, weights):
    if not factors:
        return -999
    
    s = 0
    w = 0
    
    if 'ret_20' in factors and 'ret_20' in weights:
        s += weights['ret_20'] * (factors['ret_20'] or 0) * 100
        w += abs(weights['ret_20'])
    
    if 'ret_60' in factors and 'ret_60' in weights:
        s += weights['ret_60'] * (factors['ret_60'] or 0) * 100
        w += abs(weights['ret_60'])
    
    if 'vol_20' in factors and 'vol_20' in weights:
        s += weights['vol_20'] * (-(factors['vol_20'] or 0) * 50)
        w += abs(weights['vol_20'])
    
    return s / w if w > 0 else -999


print("="*70)
print("🚀 WFO v3 - 修复版")
print("="*70)

# WFO窗口
windows = [
    ('20180101', '20181231', '20190101', '20191231'),
    ('20190101', '20191231', '20200101', '20201231'),
    ('20200101', '20201231', '20210101', '20211231'),
]

results = []

for i, (ts, te, tts, tte) in enumerate(windows, 1):
    print(f"\n周期 {i}: 训练[{ts}-{te}] -> 测试[{tts}-{tte}]")
    
    conn = sqlite3.connect(DB)
    
    # 训练期优化
    train_dates = [r[0] for r in conn.execute('''
        SELECT trade_date FROM stock_factors
        WHERE trade_date BETWEEN ? AND ?
        GROUP BY trade_date
    ''', [ts, te]).fetchall()]
    
    if not train_dates:
        continue
    
    test_date = train_dates[-1]
    
    # 获取样本股票
    samples = conn.execute('''
        SELECT sf.ts_code, dp.close FROM stock_factors sf
        JOIN daily_price dp ON sf.ts_code = dp.ts_code
        WHERE sf.trade_date = ? AND dp.trade_date = ?
        AND dp.close >= 10
        LIMIT 100
    ''', [test_date, test_date]).fetchall()
    
    print(f"   样本股票: {len(samples)}只")
    
    # 优化权重
    best_w = {'ret_20': 1.0}
    best_score = -999
    
    for _ in range(30):
        w = {
            'ret_20': random.uniform(0.5, 1.5),
            'ret_60': random.uniform(0.3, 1.0),
            'vol_20': random.uniform(-1.0, -0.3)
        }
        
        scores = []
        for (code, price) in samples[:30]:
            f = get_factors(conn, code, test_date)
            if f:
                s = score(f, w)
                if s > -50:
                    scores.append(s)
        
        if len(scores) >= 5:
            avg = np.mean(sorted(scores, reverse=True)[:5])
            if avg > best_score:
                best_score = avg
                best_w = w
    
    print(f"   最优权重: {best_w}, 得分: {best_score:.2f}")
    
    # 回测
    test_dates = [r[0] for r in conn.execute('''
        SELECT trade_date FROM stock_factors
        WHERE trade_date BETWEEN ? AND ?
        GROUP BY trade_date
    ''', [tts, tte]).fetchall()]
    
    rebal = test_dates[::15]
    print(f"   回测期: {len(rebal)}次调仓")
    
    capital = 1000000
    positions = {}
    
    for rd in rebal:
        # 清仓
        for code in list(positions.keys()):
            p = conn.execute(
                'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                [code, rd]
            ).fetchone()
            if p:
                capital += positions[code]
        positions = {}
        
        # 选股
        stocks = conn.execute('''
            SELECT sf.ts_code, dp.close FROM stock_factors sf
            JOIN daily_price dp ON sf.ts_code = dp.ts_code
            WHERE sf.trade_date = ? AND dp.trade_date = ?
            AND dp.close >= 10
            LIMIT 200
        ''', [rd, rd]).fetchall()
        
        scored = []
        for (code, close) in stocks:
            f = get_factors(conn, code, rd)
            if f:
                s = score(f, best_w)
                scored.append((code, close, s))
        
        scored.sort(key=lambda x: x[2], reverse=True)
        selected = scored[:5]
        
        # 建仓
        if selected and capital > 0:
            pos_val = capital * 0.7 / len(selected)
            for code, price, _ in selected:
                if price > 0:
                    val = int(pos_val / price / 100) * 100 * price
                    if val > 1000:
                        capital -= val
                        positions[code] = val
        
        # 净值
        total = capital + sum(positions.values())
        ret = (total - 1000000) / 1000000 * 100
        print(f"      {rd}: ¥{total:,.0f} ({ret:+.1f}%) 持仓{len(positions)}")
    
    # 统计
    final = capital + sum(positions.values())
    total_ret = (final - 1000000) / 1000000
    
    print(f"\n   结果: 总收益 {total_ret*100:+.2f}%")
    
    results.append({
        'period': i,
        'result': total_ret
    })
    
    conn.close()

# 汇总
print(f"\n{'='*70}")
print("📊 WFO汇总")
print(f"{'='*70}")

total = 1.0
for r in results:
    ret = r['result']
    total *= (1 + ret)
    print(f"周期{r['period']}: {ret*100:+.2f}%")

cagr = (total ** (1/len(results)) - 1) if results else 0
print(f"\n累计: {(total-1)*100:+.2f}%")
print(f"年化: {cagr*100:+.2f}%")

# 保存
with open(f'{OUT}/wfo_v3.json', 'w') as f:
    json.dump({'results': results, 'cagr': cagr}, f, indent=2)

print(f"\n✅ 完成!")
