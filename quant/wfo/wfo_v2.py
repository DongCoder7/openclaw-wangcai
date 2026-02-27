#!/usr/bin/env python3
"""
完整WFO回测系统 v2 - 修复版
"""
import os
import sys
import sqlite3
import json
import random
import numpy as np
from datetime import datetime
from contextlib import contextmanager
from typing import Dict

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
OUT_DIR = '/root/.openclaw/workspace/quant/wfo/results'
os.makedirs(OUT_DIR, exist_ok=True)


@contextmanager
def get_db():
    """数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class FullWFOV2:
    """完整WFO回测"""
    
    def get_factors(self, conn, ts_code: str, trade_date: str) -> Dict:
        """获取因子"""
        row = conn.execute('''
            SELECT ret_20, ret_60, vol_20, price_pos_20, price_pos_60, price_pos_high
            FROM stock_factors 
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        factors = {}
        if row:
            for i, name in enumerate(['ret_20', 'ret_60', 'vol_20', 'price_pos_20', 'price_pos_60', 'price_pos_high']):
                if row[i] is not None:
                    factors[name] = row[i]
        return factors
    
    def score_stock(self, factors: Dict, weights: Dict) -> float:
        if len(factors) < 2:
            return -999
        
        score = 0
        total = 0
        
        for f, v in factors.items():
            if f in weights:
                w = weights[f]
                if f.startswith('ret_'):
                    score += w * v * 100
                elif f == 'vol_20':
                    score += w * (-v * 50)
                elif f.startswith('price_pos_'):
                    score += w * (-abs(v - 0.5) * 100)
                total += abs(w)
        
        return score / total if total > 0 else -999
    
    def run_wfo(self):
        print("="*70)
        print("🚀 WFO v2 - 使用2018-2021因子数据")
        print("="*70)
        
        windows = [
            ('20180101', '20181231', '20190101', '20191231'),
            ('20190101', '20191231', '20200101', '20201231'),
            ('20200101', '20201231', '20210101', '20211231'),
        ]
        
        results = []
        
        for i, (ts, te, tts, tte) in enumerate(windows, 1):
            print(f"\n{'='*70}")
            print(f"周期 {i}: 训练[{ts}-{te}] -> 测试[{tts}-{tte}]")
            
            with get_db() as conn:
                # 获取训练期数据
                train_dates = [r[0] for r in conn.execute('''
                    SELECT trade_date FROM stock_factors
                    WHERE trade_date BETWEEN ? AND ?
                    GROUP BY trade_date
                ''', [ts, te]).fetchall()]
                
                if len(train_dates) < 5:
                    print("   ⚠️ 训练数据不足")
                    continue
                
                # 优化权重
                print("   🔍 优化权重...")
                test_date = train_dates[-1]
                
                # 获取样本股票
                samples = conn.execute('''
                    SELECT sf.ts_code, dp.close FROM stock_factors sf
                    JOIN daily_price dp ON sf.ts_code = dp.ts_code
                    WHERE sf.trade_date = ? AND dp.trade_date = ?
                    AND dp.close >= 10
                    LIMIT 100
                ''', [test_date, test_date]).fetchall()
                
                # 随机搜索最优权重
                best_w = {'ret_20': 1.0, 'vol_20': -0.5, 'price_pos_20': 0.3}
                best_score = -999
                
                for _ in range(20):
                    w = {
                        'ret_20': random.uniform(0.5, 1.5),
                        'ret_60': random.uniform(0.3, 1.0),
                        'vol_20': random.uniform(-1.0, -0.3),
                        'price_pos_20': random.uniform(0.2, 0.8)
                    }
                    
                    scores = []
                    for (code, price) in samples[:50]:
                        f = self.get_factors(conn, code, test_date)
                        if f:
                            s = self.score_stock(f, w)
                            if s > -50:
                                scores.append(s)
                    
                    if len(scores) >= 5:
                        avg = np.mean(sorted(scores, reverse=True)[:5])
                        if avg > best_score:
                            best_score = avg
                            best_w = w
                
                print(f"   ✅ 最优: 得分={best_score:.2f}")
                
                # 回测
                print("   📈 回测...")
                test_dates = [r[0] for r in conn.execute('''
                    SELECT trade_date FROM stock_factors
                    WHERE trade_date BETWEEN ? AND ?
                    GROUP BY trade_date
                ''', [tts, tte]).fetchall()]
                
                rebal = test_dates[::15]  # 每15天
                
                capital = 1000000
                positions = {}
                
                for j, rd in enumerate(rebal):
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
                        LIMIT 100
                    ''', [rd, rd]).fetchall()
                    
                    scored = []
                    for (code, close) in stocks:
                        f = self.get_factors(conn, code, rd)
                        if f:
                            s = self.score_stock(f, best_w)
                            if s > -30:
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
                    if (j+1) % 3 == 0 or j == len(rebal)-1:
                        ret = (total - 1000000) / 1000000 * 100
                        print(f"      [{j+1}/{len(rebal)}] {rd}: ¥{total:,.0f} ({ret:+.1f}%)")
                
                # 结果
                final = capital + sum(positions.values())
                total_ret = (final - 1000000) / 1000000
                years = len(rebal) / 252
                ann_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
                
                print(f"\n   📊 结果: 年化{ann_ret*100:+.2f}%, 总收益{total_ret*100:+.2f}%")
                
                results.append({
                    'period': i,
                    'train': f'{ts}-{te}',
                    'test': f'{tts}-{tte}',
                    'result': {'annual': ann_ret, 'total': total_ret}
                })
        
        # 汇总
        print(f"\n{'='*70}")
        print("📊 WFO汇总")
        
        total_ret = 1.0
        for r in results:
            ret = r['result']['total']
            total_ret *= (1 + ret)
            print(f"  周期{r['period']}: {r['test'][:4]}年 {ret*100:+.2f}%")
        
        cagr = (total_ret ** (1/len(results)) - 1) if results else 0
        print(f"\n  累计: {(total_ret-1)*100:+.2f}%")
        print(f"  年化: {cagr*100:+.2f}%")
        
        # 保存
        with open(f'{OUT_DIR}/wfo_v2_result.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': results,
                'summary': {'cagr': cagr}
            }, f, indent=2)
        
        print(f"\n💾 保存: wfo_v2_result.json")
        print(f"{'='*70}")


if __name__ == '__main__':
    FullWFOV2().run_wfo()
    print("\n✅ 完成!")
