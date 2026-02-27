#!/usr/bin/env python3
"""
完整WFO回测系统 v3 - 修复版
修复: 清仓逻辑错误、持仓计算错误
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


class FullWFOV3:
    """完整WFO回测 - 修复版"""
    
    def get_factors(self, conn, ts_code: str, trade_date: str) -> Dict:
        """获取因子"""
        row = conn.execute('''
            SELECT ret_20, ret_60, vol_20, price_pos_20, price_pos_60, price_pos_high,
                   mom_accel, rel_strength
            FROM stock_factors 
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        factors = {}
        if row:
            names = ['ret_20', 'ret_60', 'vol_20', 'price_pos_20', 'price_pos_60', 'price_pos_high',
                     'mom_accel', 'rel_strength']
            for i, name in enumerate(names):
                if row[i] is not None:
                    factors[name] = row[i]
        return factors
    
    def score_stock(self, factors: Dict, weights: Dict) -> float:
        """评分 - 修复版"""
        if len(factors) < 2:
            return -999
        
        score = 0
        total = 0
        
        for f, v in factors.items():
            if f in weights and v is not None:
                w = weights[f]
                if f.startswith('ret_') and f != 'ret_120':
                    score += w * v * 100
                elif f == 'vol_20':
                    score += w * (-v * 50)
                elif f.startswith('price_pos_'):
                    score += w * (-abs(v - 0.5) * 100)
                elif f == 'mom_accel':
                    score += w * v * 50
                total += abs(w)
        
        return score / total if total > 0 else -999
    
    def run_wfo(self):
        print("="*70)
        print("🚀 WFO v3 - 修复版 (修复清仓逻辑)")
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
                best_w = {'ret_20': 1.0, 'vol_20': -0.5, 'price_pos_20': 0.3, 'mom_accel': 0.2}
                best_score = -999
                
                for _ in range(30):  # 增加搜索次数
                    w = {
                        'ret_20': random.uniform(0.5, 1.5),
                        'ret_60': random.uniform(0.3, 1.0),
                        'vol_20': random.uniform(-1.0, -0.3),
                        'price_pos_20': random.uniform(0.2, 0.8),
                        'mom_accel': random.uniform(0.1, 0.5)
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
                
                print(f"   ✅ 最优权重: {best_w}")
                print(f"   ✅ 最优得分: {best_score:.2f}")
                
                # 回测 - 修复版
                print("   📈 回测...")
                test_dates = [r[0] for r in conn.execute('''
                    SELECT trade_date FROM stock_factors
                    WHERE trade_date BETWEEN ? AND ?
                    GROUP BY trade_date
                ''', [tts, tte]).fetchall()]
                
                rebal = test_dates[::10]  # 每10天调仓（更灵活）
                
                capital = 1000000
                positions = {}  # code -> shares (股数)
                trade_log = []
                
                for j, rd in enumerate(rebal):
                    # ===== 修复: 正确的清仓逻辑 =====
                    if positions:
                        sold_value = 0
                        for code, shares in list(positions.items()):
                            p = conn.execute(
                                'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                                [code, rd]
                            ).fetchone()
                            if p and p[0]:
                                sell_value = shares * p[0]
                                sold_value += sell_value
                                trade_log.append(f"卖出 {code}: {shares}股 × {p[0]} = {sell_value:,.0f}")
                        capital += sold_value
                        positions = {}
                    
                    # ===== 选股 =====
                    stocks = conn.execute('''
                        SELECT sf.ts_code, dp.close FROM stock_factors sf
                        JOIN daily_price dp ON sf.ts_code = dp.ts_code
                        WHERE sf.trade_date = ? AND dp.trade_date = ?
                        AND dp.close >= 5
                        LIMIT 150
                    ''', [rd, rd]).fetchall()
                    
                    scored = []
                    for (code, close) in stocks:
                        f = self.get_factors(conn, code, rd)
                        if f:
                            s = self.score_stock(f, best_w)
                            if s > -20:  # 降低门槛
                                scored.append((code, close, s))
                    
                    scored.sort(key=lambda x: x[2], reverse=True)
                    selected = scored[:5]  # 选5只
                    
                    # ===== 修复: 正确的建仓逻辑 =====
                    if selected and capital > 10000:
                        pos_val = capital * 0.9 / len(selected)  # 90%仓位
                        for code, price, score in selected:
                            if price > 0 and pos_val > 10000:
                                shares = int(pos_val / price / 100) * 100  # 100股整数
                                if shares >= 100:
                                    buy_value = shares * price
                                    if buy_value <= capital:
                                        capital -= buy_value
                                        positions[code] = shares
                                        trade_log.append(f"买入 {code}: {shares}股 × {price} = {buy_value:,.0f} (得分{score:.1f})")
                    
                    # 计算净值
                    holdings_value = 0
                    for code, shares in positions.items():
                        p = conn.execute(
                            'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                            [code, rd]
                        ).fetchone()
                        if p and p[0]:
                            holdings_value += shares * p[0]
                    
                    total = capital + holdings_value
                    ret = (total - 1000000) / 1000000
                    
                    if (j+1) % 5 == 0 or j == len(rebal)-1:
                        print(f"      [{j+1}/{len(rebal)}] {rd}: ¥{total:,.0f} ({ret*100:+.1f}%) 持仓{len(positions)}只")
                
                # ===== 最终结果 =====
                # 清仓计算最终价值
                final_value = capital
                for code, shares in positions.items():
                    p = conn.execute(
                        'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                        [code, rebal[-1]]
                    ).fetchone()
                    if p and p[0]:
                        final_value += shares * p[0]
                
                total_ret = (final_value - 1000000) / 1000000
                years = (len(test_dates) + 1) / 252
                ann_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
                
                print(f"\n   📊 结果: 年化{ann_ret*100:+.2f}%, 总收益{total_ret*100:+.2f}%")
                print(f"   💰 期末资产: ¥{final_value:,.0f}")
                
                results.append({
                    'period': i,
                    'train': f'{ts}-{te}',
                    'test': f'{tts}-{tte}',
                    'result': {'annual': ann_ret, 'total': total_ret},
                    'weights': best_w
                })
        
        # 汇总
        print(f"\n{'='*70}")
        print("📊 WFO v3 汇总")
        
        total_ret = 1.0
        for r in results:
            ret = r['result']['total']
            total_ret *= (1 + ret)
            print(f"  周期{r['period']}: {r['test'][:4]}年 {ret*100:+.2f}%")
        
        cagr = (total_ret ** (1/len(results)) - 1) if results else 0
        print(f"\n  累计收益: {(total_ret-1)*100:+.2f}%")
        print(f"  年化收益: {cagr*100:+.2f}%")
        
        # 保存
        output_file = f'{OUT_DIR}/wfo_v3_fixed_result.json'
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': results,
                'summary': {'cagr': cagr, 'total_return': total_ret - 1}
            }, f, indent=2)
        
        print(f"\n💾 保存: {output_file}")
        print(f"{'='*70}")


if __name__ == '__main__':
    FullWFOV3().run_wfo()
    print("\n✅ WFO v3 修复版完成!")
