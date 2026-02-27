#!/usr/bin/env python3
"""
完整WFO回测系统 - 使用补充后的历史因子数据
"""
import os
import sys
import sqlite3
import json
import random
import numpy as np
from datetime import datetime
from typing import Dict, List

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
OUT_DIR = '/root/.openclaw/workspace/quant/wfo/results'
os.makedirs(OUT_DIR, exist_ok=True)


class FullWFO:
    """完整WFO回测"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_factors(self, ts_code: str, trade_date: str) -> Dict:
        """获取因子数据"""
        factors = {}
        
        # stock_factors
        row = self.conn.execute('''
            SELECT ret_20, ret_60, ret_120, vol_20, vol_ratio,
                   price_pos_20, price_pos_60, price_pos_high, mom_accel
            FROM stock_factors 
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        if row:
            names = ['ret_20', 'ret_60', 'ret_120', 'vol_20', 'vol_ratio',
                    'price_pos_20', 'price_pos_60', 'price_pos_high', 'mom_accel']
            for i, name in enumerate(names):
                if row[i] is not None:
                    factors[name] = row[i]
        
        return factors
    
    def calculate_score(self, factors: Dict, weights: Dict) -> float:
        """计算评分"""
        if len(factors) < 3:
            return -999
        
        score = 0
        total = 0
        
        for factor, value in factors.items():
            if factor in weights:
                w = weights[factor]
                
                if factor.startswith('ret_'):
                    score += w * value * 100
                elif factor == 'vol_20':
                    score += w * (-value * 50)
                elif factor.startswith('price_pos_'):
                    score += w * (-abs(value - 0.5) * 100)
                elif factor == 'mom_accel':
                    score += w * value * 50
                else:
                    score += w * value
                
                total += abs(w)
        
        return score / total if total > 0 else -999
    
    def optimize_train(self, train_start: str, train_end: str) -> Dict:
        """训练期优化"""
        print(f"\n   🔍 训练期优化 [{train_start} - {train_end}]...")
        
        # 获取交易日
        dates = [r[0] for r in self.conn.execute('''
            SELECT trade_date FROM stock_factors
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY trade_date ORDER BY trade_date
        ''', [train_start, train_end]).fetchall()]
        
        if len(dates) < 10:
            # 用默认权重
            return {'ret_20': 1.0, 'vol_20': -0.8, 'price_pos_20': 0.5, 'mom_accel': 0.3}
        
        # 随机搜索
        best_weights = None
        best_score = -999
        
        for _ in range(30):
            # 随机权重
            weights = {
                'ret_20': random.uniform(0.5, 1.5),
                'ret_60': random.uniform(0.3, 1.0),
                'vol_20': random.uniform(-1.2, -0.4),
                'price_pos_20': random.uniform(0.2, 0.8),
                'mom_accel': random.uniform(0.2, 0.6)
            }
            
            # 评估
            test_date = dates[-1]
            stocks = self.conn.execute('''
                SELECT sf.ts_code FROM stock_factors sf
                JOIN daily_price dp ON sf.ts_code = dp.ts_code
                WHERE sf.trade_date = ? AND dp.trade_date = ?
                AND dp.close >= 10
                LIMIT 50
            ''', [test_date, test_date]).fetchall()
            
            scores = []
            for (ts_code,) in stocks:
                factors = self.get_factors(ts_code, test_date)
                if factors:
                    s = self.calculate_score(factors, weights)
                    if s > -100:
                        scores.append(s)
            
            if len(scores) >= 10:
                avg = np.mean(sorted(scores, reverse=True)[:10])
                if avg > best_score:
                    best_score = avg
                    best_weights = weights
        
        if best_weights is None:
            best_weights = {'ret_20': 1.0, 'vol_20': -0.8, 'price_pos_20': 0.5}
        
        print(f"   ✅ 最优权重 (得分: {best_score:.2f})")
        return best_weights
    
    def run_backtest(self, start_date: str, end_date: str, weights: Dict) -> Dict:
        """回测"""
        # 获取交易日
        dates = [r[0] for r in self.conn.execute('''
            SELECT trade_date FROM stock_factors
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY trade_date ORDER BY trade_date
        ''', [start_date, end_date]).fetchall()]
        
        rebal_dates = dates[::20]  # 每20天
        
        if len(rebal_dates) < 2:
            return {'annual_return': 0, 'total_return': 0, 'max_drawdown': 0}
        
        capital = 1000000
        positions = {}
        
        for i, rd in enumerate(rebal_dates):
            # 清仓
            for code in list(positions.keys()):
                p = self.conn.execute(
                    'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                    [code, rd]
                ).fetchone()
                if p:
                    capital += positions[code]
            positions = {}
            
            # 选股
            stocks = self.conn.execute('''
                SELECT sf.ts_code, dp.close FROM stock_factors sf
                JOIN daily_price dp ON sf.ts_code = dp.ts_code
                WHERE sf.trade_date = ? AND dp.trade_date = ?
                AND dp.close >= 10
                LIMIT 100
            ''', [rd, rd]).fetchall()
            
            scored = []
            for ts_code, close in stocks:
                factors = self.get_factors(ts_code, rd)
                if factors:
                    score = self.calculate_score(factors, weights)
                    if score > -50:
                        scored.append((ts_code, close, score))
            
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
            
            if (i + 1) % 3 == 0 or i == len(rebal_dates) - 1:
                ret = (total - 1000000) / 1000000 * 100
                print(f"      [{i+1}/{len(rebal_dates)}] {rd}: ¥{total:,.0f} ({ret:+.1f}%)")
        
        # 统计
        final = capital + sum(positions.values())
        total_ret = (final - 1000000) / 1000000
        years = len(rebal_dates) / 252
        ann_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
        
        return {
            'annual_return': ann_ret,
            'total_return': total_ret,
            'max_drawdown': 0
        }
    
    def run_wfo(self):
        """运行WFO"""
        print("="*70)
        print("🚀 完整WFO回测系统")
        print("="*70)
        print("数据: 2018-2021年补充因子数据 (每日800+只)")
        print("="*70)
        
        # WFO窗口
        windows = [
            ('20180101', '20181231', '20190101', '20191231'),  # 2019测试
            ('20190101', '20191231', '20200101', '20201231'),  # 2020测试
            ('20200101', '20201231', '20210101', '20211231'),  # 2021测试
        ]
        
        results = []
        
        for i, (ts, te, tts, tte) in enumerate(windows, 1):
            print(f"\n{'='*70}")
            print(f"🚀 WFO周期 {i}")
            print(f"{'='*70}")
            print(f"训练: {ts}-{te}")
            print(f"测试: {tts}-{tte}")
            
            # 训练优化
            weights = self.optimize_train(ts, te)
            
            # 测试验证
            result = self.run_backtest(tts, tte, weights)
            
            print(f"\n   📊 测试结果:")
            print(f"      年化: {result['annual_return']*100:+.2f}%")
            print(f"      总收益: {result['total_return']*100:+.2f}%")
            
            results.append({
                'period': i,
                'train': f'{ts}-{te}',
                'test': f'{tts}-{tte}',
                'weights': weights,
                'result': result
            })
        
        # 汇总
        print(f"\n{'='*70}")
        print("📊 WFO汇总")
        print(f"{'='*70}")
        
        total_ret = 1.0
        for r in results:
            ret = r['result']['total_return']
            total_ret *= (1 + ret)
            print(f"周期{r['period']}: {r['test'][:4]}年 收益 {ret*100:+.2f}%")
        
        cagr = (total_ret ** (1/len(results)) - 1) if results else 0
        print(f"\n累计收益: {(total_ret-1)*100:+.2f}%")
        print(f"年化CAGR: {cagr*100:+.2f}%")
        
        # 保存
        with open(f'{OUT_DIR}/wfo_full_result.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': results,
                'summary': {'cagr': cagr, 'total': total_ret-1}
            }, f, indent=2, default=str)
        
        print(f"\n💾 保存: wfo_full_result.json")
        print(f"{'='*70}")


if __name__ == '__main__':
    wfo = FullWFO()
    wfo.run_wfo()
    print("\n✅ WFO完成!")
