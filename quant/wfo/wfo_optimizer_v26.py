#!/usr/bin/env python3
"""
WFO v26 优化器整合版
完整流程: 训练期优化因子权重 -> 测试期验证 -> 滚动执行
"""
import os
import sys
import sqlite3
import json
import random
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass

sys.path.insert(0, '/root/.openclaw/workspace/quant/wfo')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
OUT_DIR = '/root/.openclaw/workspace/quant/wfo/results'
os.makedirs(OUT_DIR, exist_ok=True)


@dataclass
class FactorWeight:
    """因子权重配置"""
    name: str
    weight: float


class WFOOptimizerV26:
    """v26 WFO优化器"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        
        # 可用因子池 (根据表结构)
        self.factor_pool = [
            'ret_20', 'ret_60', 'ret_120',
            'vol_20', 'vol_ratio',
            'price_pos_20', 'price_pos_60', 'price_pos_high',
            'mom_accel', 'rel_strength', 'money_flow'
        ]
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_factor_data(self, ts_code: str, trade_date: str, factors: List[str]) -> Dict[str, float]:
        """获取指定因子数据"""
        result = {}
        
        # 技术因子
        tech_factors = [f for f in factors if f.startswith(('ret_', 'vol_', 'price_pos_'))]
        if tech_factors:
            cols = ', '.join(tech_factors)
            row = self.conn.execute(f'''
                SELECT {cols} FROM stock_factors 
                WHERE ts_code = ? AND trade_date = ?
            ''', [ts_code, trade_date]).fetchone()
            
            if row:
                for i, col in enumerate(tech_factors):
                    if row[i] is not None:
                        result[col] = float(row[i])
        
        # 防御因子
        def_factors = [f for f in factors if f in ['sharpe_like', 'max_drawdown_120']]
        if def_factors:
            cols = ', '.join(def_factors)
            row = self.conn.execute(f'''
                SELECT {cols} FROM stock_defensive_factors 
                WHERE ts_code = ? AND trade_date = ?
            ''', [ts_code, trade_date]).fetchone()
            
            if row:
                for i, col in enumerate(def_factors):
                    if row[i] is not None:
                        result[col] = float(row[i])
        
        return result
    
    def calculate_stock_score(self, ts_code: str, trade_date: str, 
                             weights: Dict[str, float]) -> float:
        """计算股票评分"""
        factors = self.get_factor_data(ts_code, trade_date, list(weights.keys()))
        
        if len(factors) < 3:
            return -999
        
        score = 0
        total_weight = 0
        
        for factor, weight in weights.items():
            if factor in factors:
                value = factors[factor]
                
                # 标准化处理
                if factor.startswith('ret_'):
                    normalized = value * 100
                elif factor.startswith('vol_'):
                    normalized = -value * 50  # 波动率反转
                elif factor.startswith('price_pos_'):
                    normalized = -(abs(value - 0.5) * 100)
                elif factor == 'sharpe_like':
                    normalized = value * 20
                elif factor == 'max_drawdown_120':
                    normalized = value * 100
                else:
                    normalized = value
                
                score += weight * normalized
                total_weight += abs(weight)
        
        return score / total_weight if total_weight > 0 else -999
    
    def optimize_weights_train(self, start_date: str, end_date: str) -> Dict[str, float]:
        """
        训练期: 优化因子权重
        使用遗传算法/随机搜索
        """
        print(f"\n   🔍 训练期权重优化 [{start_date} - {end_date}]...")
        
        # 获取交易日
        dates = [r[0] for r in self.conn.execute('''
            SELECT DISTINCT trade_date FROM stock_factors
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        ''', [start_date, end_date]).fetchall()]
        
        if len(dates) < 5:
            print(f"   ⚠️ 训练期数据不足，使用默认权重")
            return {f: 1.0 for f in self.factor_pool[:5]}
        
        # 随机搜索权重组合
        best_weights = None
        best_score = -999
        
        for i in range(50):  # 50次迭代
            # 随机选择5-10个因子
            num_factors = random.randint(5, min(10, len(self.factor_pool)))
            selected_factors = random.sample(self.factor_pool, num_factors)
            
            # 随机权重
            weights = {f: random.uniform(-2, 2) for f in selected_factors}
            
            # 快速评估: 在训练期末日选股评分
            sample_date = dates[-1]
            
            # 获取股票
            stocks = self.conn.execute('''
                SELECT DISTINCT sf.ts_code
                FROM stock_factors sf
                JOIN daily_price dp ON sf.ts_code = dp.ts_code
                WHERE sf.trade_date = ? AND dp.trade_date = ?
                AND dp.close >= 10
                LIMIT 100
            ''', [sample_date, sample_date]).fetchall()
            
            scores = []
            for (ts_code,) in stocks:
                score = self.calculate_stock_score(ts_code, sample_date, weights)
                if score > -100:
                    scores.append(score)
            
            if len(scores) > 10:
                avg_score = np.mean(sorted(scores, reverse=True)[:10])
                
                if avg_score > best_score:
                    best_score = avg_score
                    best_weights = weights.copy()
        
        if best_weights is None:
            best_weights = {f: 1.0 for f in self.factor_pool[:5]}
        
        print(f"   ✅ 最优权重 (得分{best_score:.2f}):")
        for f, w in list(best_weights.items())[:5]:
            print(f"      {f}: {w:.2f}")
        
        return best_weights
    
    def run_backtest_test(self, start_date: str, end_date: str,
                         weights: Dict[str, float]) -> Dict:
        """测试期: 回测验证"""
        print(f"\n   📈 测试期回测 [{start_date} - {end_date}]...")
        
        # 获取交易日
        dates = [r[0] for r in self.conn.execute('''
            SELECT DISTINCT trade_date FROM stock_factors
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        ''', [start_date, end_date]).fetchall()]
        
        rebalance_dates = dates[::10]  # 每10天调仓
        
        if len(rebalance_dates) < 2:
            return {'annual_return': 0, 'max_drawdown': 0, 'total_return': 0}
        
        capital = 1000000
        positions = {}
        
        for i, rd in enumerate(rebalance_dates):
            # 清仓
            for code in list(positions.keys()):
                price = self.conn.execute('''
                    SELECT close FROM daily_price
                    WHERE ts_code = ? AND trade_date = ?
                ''', [code, rd]).fetchone()
                
                if price:
                    capital += positions[code]
            
            positions = {}
            
            # 选股
            stocks = []
            for row in self.conn.execute('''
                SELECT DISTINCT sf.ts_code, dp.close
                FROM stock_factors sf
                JOIN daily_price dp ON sf.ts_code = dp.ts_code
                WHERE sf.trade_date = ? AND dp.trade_date = ?
                AND dp.close >= 10
                LIMIT 200
            ''', [rd, rd]).fetchall():
                
                ts_code, close = row
                score = self.calculate_stock_score(ts_code, rd, weights)
                
                if score > -50:
                    stocks.append((ts_code, close, score))
            
            # 排序选前5
            stocks.sort(key=lambda x: x[2], reverse=True)
            stocks = stocks[:5]
            
            # 建仓
            if stocks and capital > 0:
                pos_val = capital * 0.7 / len(stocks)
                for code, price, _ in stocks:
                    if price > 0:
                        val = int(pos_val / price / 100) * 100 * price
                        if val > 1000:
                            capital -= val
                            positions[code] = val
            
            if (i + 1) % 3 == 0 or i == len(rebalance_dates) - 1:
                total = capital + sum(positions.values())
                ret = (total - 1000000) / 1000000 * 100
                print(f"      [{i+1}/{len(rebalance_dates)}] {rd}: ¥{total:,.0f} ({ret:+.1f}%)")
        
        # 统计
        final = capital + sum(positions.values())
        total_ret = (final - 1000000) / 1000000
        
        years = len(rebalance_dates) / 252
        ann_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
        
        return {
            'annual_return': ann_ret,
            'total_return': total_ret,
            'max_drawdown': 0  # 简化版不计算回撤
        }
    
    def run_wfo_period(self, train_start: str, train_end: str,
                       test_start: str, test_end: str,
                       period_num: int) -> Dict:
        """执行单个WFO周期"""
        print(f"\n{'='*70}")
        print(f"🚀 WFO周期 {period_num}")
        print(f"{'='*70}")
        print(f"训练: {train_start} ~ {train_end}")
        print(f"测试: {test_start} ~ {test_end}")
        
        # 步骤1: 训练期优化
        optimal_weights = self.optimize_weights_train(train_start, train_end)
        
        # 步骤2: 测试期验证
        test_result = self.run_backtest_test(test_start, test_end, optimal_weights)
        
        return {
            'period': period_num,
            'train': {'start': train_start, 'end': train_end},
            'test': {'start': test_start, 'end': test_end},
            'optimal_weights': optimal_weights,
            'test_result': test_result
        }
    
    def run_full_wfo(self):
        """执行完整WFO"""
        print("="*70)
        print("🚀 WFO v26 优化器整合版")
        print("="*70)
        print("流程: 训练期优化权重 -> 测试期验证 -> 滚动执行")
        print("="*70)
        
        # WFO窗口 (基于实际数据可用性)
        windows = [
            # 近期窗口 (有完整因子数据)
            ('20251201', '20260131', '20260201', '20260213'),
        ]
        
        results = []
        for i, (ts, te, tts, tte) in enumerate(windows, 1):
            result = self.run_wfo_period(ts, te, tts, tte, i)
            results.append(result)
        
        # 生成报告
        self._generate_report(results)
        return results
    
    def _generate_report(self, results: List[Dict]):
        """生成报告"""
        print(f"\n{'='*70}")
        print("📊 WFO优化器报告")
        print(f"{'='*70}")
        
        total_return = 1.0
        for r in results:
            ret = r['test_result']['total_return']
            total_return *= (1 + ret)
            
            print(f"\n周期 {r['period']}:")
            print(f"  训练: {r['train']['start']}~{r['train']['end']}")
            print(f"  测试: {r['test']['start']}~{r['test']['end']}")
            print(f"  最优因子: {len(r['optimal_weights'])}个")
            print(f"  OOS收益: {ret*100:+.2f}%")
        
        cagr = (total_return ** (1/len(results)) - 1) if results else 0
        
        print(f"\n【汇总】")
        print(f"  累计收益: {(total_return-1)*100:+.2f}%")
        print(f"  年化CAGR: {cagr*100:+.2f}%")
        
        # 保存
        with open(f'{OUT_DIR}/wfo_optimizer_v26.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': results
            }, f, indent=2, default=str)
        
        print(f"\n💾 保存: wfo_optimizer_v26.json")
        print(f"{'='*70}")


if __name__ == '__main__':
    optimizer = WFOOptimizerV26()
    optimizer.run_full_wfo()
    print("\n✅ WFO优化器执行完毕!")
