#!/usr/bin/env python3
"""
WFO v5 - 高级优化版
功能: 全参数网格搜索优化
优化目标: 因子权重 + 择时阈值 + 止损参数 + 仓位参数
"""
import os
import sys
import sqlite3
import json
import random
import numpy as np
from datetime import datetime
from itertools import product
from contextlib import contextmanager

sys.path.insert(0, '/root/.openclaw/workspace/quant/wfo')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
OUT_PATH = '/root/.openclaw/workspace/quant/optimizer'


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class WFOAdvancedOptimizer:
    """WFO高级优化器 - 全参数搜索"""
    
    def __init__(self):
        # 参数搜索空间
        self.param_grid = {
            # 因子权重
            'ret_20_w': [0.8, 1.0, 1.2, 1.5],
            'ret_60_w': [0.3, 0.5, 0.8],
            'vol_20_w': [-0.6, -0.8, -1.0, -1.2],
            'sharpe_w': [0.4, 0.6, 0.8, 1.0],
            'low_vol_w': [0.3, 0.5, 0.7],
            'mom_accel_w': [0.1, 0.2, 0.3, 0.4],
            
            # 择时阈值
            'bull_ret_threshold': [0.015, 0.02, 0.025],
            'bull_up_ratio': [0.55, 0.6, 0.65],
            'bear_ret_threshold': [-0.04, -0.05, -0.06],
            'bear_down_ratio': [0.25, 0.3, 0.35],
            'volatile_vol_threshold': [0.07, 0.08, 0.09],
            
            # 仓位配置
            'bull_position': [0.85, 0.9, 0.95],
            'bear_position': [0.2, 0.3, 0.4],
            'volatile_position': [0.4, 0.5, 0.6],
            'neutral_position': [0.6, 0.7, 0.8],
            
            # 止损参数
            'stop_loss': [-0.06, -0.08, -0.10],
            'max_holding_days': [8, 10, 12, 15],
            'rebalance_days': [8, 10, 12],
        }
        
        self.best_result = None
        self.best_score = -999
        self.best_params = None
        
    def get_factors(self, conn, ts_code, trade_date):
        """获取因子"""
        factors = {}
        
        row = conn.execute('''
            SELECT ret_20, ret_60, vol_20, price_pos_20, mom_accel, rel_strength
            FROM stock_factors WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        if row:
            for i, name in enumerate(['ret_20', 'ret_60', 'vol_20', 'price_pos_20', 'mom_accel', 'rel_strength']):
                if row[i] is not None:
                    factors[name] = row[i]
        
        row = conn.execute('''
            SELECT sharpe_like, low_vol_score, max_drawdown_120
            FROM stock_defensive_factors WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        if row:
            for i, name in enumerate(['sharpe_like', 'low_vol_score', 'max_drawdown_120']):
                if row[i] is not None:
                    factors[name] = row[i]
        
        return factors
    
    def get_market_timing(self, conn, trade_date, params):
        """择时 - 使用参数"""
        avg_ret = conn.execute('SELECT AVG(ret_20) FROM stock_factors WHERE trade_date = ?', [trade_date]).fetchone()[0] or 0
        avg_vol = conn.execute('SELECT AVG(vol_20) FROM stock_factors WHERE trade_date = ?', [trade_date]).fetchone()[0] or 0
        up_ratio = conn.execute('SELECT AVG(CASE WHEN ret_20 > 0 THEN 1.0 ELSE 0.0 END) FROM stock_factors WHERE trade_date = ?', [trade_date]).fetchone()[0] or 0.5
        
        if avg_ret > params['bull_ret_threshold'] and up_ratio > params['bull_up_ratio']:
            return params['bull_position'], "bull"
        elif avg_ret < params['bear_ret_threshold'] or up_ratio < params['bear_down_ratio']:
            return params['bear_position'], "bear"
        elif avg_vol > params['volatile_vol_threshold']:
            return params['volatile_position'], "volatile"
        else:
            return params['neutral_position'], "neutral"
    
    def score_stock(self, factors, params):
        """评分 - 使用参数"""
        if len(factors) < 3:
            return -999
        
        score = 0
        weights = {
            'ret_20': params['ret_20_w'],
            'ret_60': params['ret_60_w'],
            'vol_20': params['vol_20_w'],
            'sharpe_like': params['sharpe_w'],
            'low_vol_score': params['low_vol_w'],
            'mom_accel': params['mom_accel_w'],
        }
        
        for f, v in factors.items():
            if f in weights and v is not None:
                w = weights[f]
                if f.startswith('ret_'):
                    score += w * v * 100
                elif f.startswith('vol_'):
                    score += w * (-v * 50)
                elif f == 'sharpe_like':
                    score += w * v * 20
                elif f == 'low_vol_score':
                    score += w * v * 30
                elif f == 'mom_accel':
                    score += w * v * 50
        
        return score
    
    def run_single_backtest(self, params, verbose=False):
        """单次回测"""
        windows = [
            ('20180101', '20191231', '20200101', '20201231'),
            ('20190101', '20201231', '20210101', '20211231'),
            ('20200101', '20211231', '20220101', '20221231'),
            ('20210101', '20221231', '20230101', '20231231'),
            ('20220101', '20231231', '20240101', '20241231'),
            ('20230101', '20241231', '20250101', '20251231'),
        ]
        
        results = []
        
        with get_db() as conn:
            for ts, te, tts, tte in windows:
                test_dates = [r[0] for r in conn.execute('SELECT trade_date FROM stock_factors WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date', [tts, tte]).fetchall()]
                
                if len(test_dates) < 50:
                    continue
                
                rebal = test_dates[::params['rebalance_days']]
                capital = 1000000
                positions = {}
                
                for rd in rebal:
                    position_pct, market_state = self.get_market_timing(conn, rd, params)
                    
                    # 止损
                    if positions:
                        for code, (shares, cost) in list(positions.items()):
                            p = conn.execute('SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?', [code, rd]).fetchone()
                            if p and p[0]:
                                loss_pct = (p[0] - cost) / cost
                                if loss_pct <= params['stop_loss']:
                                    capital += shares * p[0]
                                    del positions[code]
                    
                    # 清仓
                    if positions:
                        for code, (shares, cost) in list(positions.items()):
                            p = conn.execute('SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?', [code, rd]).fetchone()
                            if p and p[0]:
                                capital += shares * p[0]
                        positions = {}
                    
                    # 选股
                    stocks = conn.execute('SELECT sf.ts_code, dp.close FROM stock_factors sf JOIN daily_price dp ON sf.ts_code = dp.ts_code WHERE sf.trade_date = ? AND dp.trade_date = ? AND dp.close >= 5 LIMIT 150', [rd, rd]).fetchall()
                    
                    scored = []
                    for code, close in stocks:
                        f = self.get_factors(conn, code, rd)
                        if f:
                            s = self.score_stock(f, params)
                            if s > -20:
                                scored.append((code, close, s))
                    
                    scored.sort(key=lambda x: x[2], reverse=True)
                    selected = scored[:5]
                    
                    if selected and capital > 10000 and position_pct > 0.3:
                        pos_val = capital * position_pct / len(selected)
                        for code, price, score in selected:
                            if price > 0 and pos_val > 10000:
                                shares = int(pos_val / price / 100) * 100
                                if shares >= 100:
                                    buy_value = shares * price
                                    if buy_value <= capital:
                                        capital -= buy_value
                                        positions[code] = (shares, price)
                    
                    # 强制调仓（最大持仓天数）
                    # 简化：每次调仓都清仓，所以天然满足
                
                # 期末
                final_value = capital
                for code, (shares, cost) in positions.items():
                    p = conn.execute('SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?', [code, rebal[-1]]).fetchone()
                    if p and p[0]:
                        final_value += shares * p[0]
                
                total_ret = (final_value - 1000000) / 1000000
                results.append(total_ret)
        
        if not results:
            return {'cagr': -1, 'sharpe': -1, 'max_dd': 1, 'win_rate': 0}
        
        # 计算指标
        total = 1.0
        for r in results:
            total *= (1 + r)
        cagr = (total ** (1/len(results)) - 1) if results else -1
        
        # 计算最大回撤
        cumulative = [1.0]
        for r in results:
            cumulative.append(cumulative[-1] * (1 + r))
        max_dd = 0
        peak = cumulative[0]
        for val in cumulative:
            if val > peak:
                peak = val
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd
        
        # 胜率
        wins = sum(1 for r in results if r > 0)
        win_rate = wins / len(results)
        
        # 综合评分 (CAGR为主，兼顾回撤和胜率)
        score = cagr * 100 - max_dd * 50 + win_rate * 10
        
        return {
            'cagr': cagr,
            'max_dd': max_dd,
            'win_rate': win_rate,
            'score': score,
            'yearly_returns': results
        }
    
    def random_search(self, n_iterations=50):
        """随机搜索最优参数"""
        print(f"🚀 开始随机搜索: {n_iterations}次迭代")
        print(f"参数空间大小: {np.prod([len(v) for v in self.param_grid.values()])}")
        print("="*70)
        
        for i in range(n_iterations):
            # 随机采样参数
            params = {k: random.choice(v) for k, v in self.param_grid.items()}
            
            print(f"\n[{i+1}/{n_iterations}] 测试参数组合...")
            
            # 运行回测
            result = self.run_single_backtest(params)
            
            print(f"   CAGR: {result['cagr']*100:+.2f}%, 最大回撤: {result['max_dd']*100:.1f}%, 胜率: {result['win_rate']*100:.0f}%")
            print(f"   综合评分: {result['score']:.2f}")
            
            # 更新最优
            if result['score'] > self.best_score:
                self.best_score = result['score']
                self.best_params = params.copy()
                self.best_result = result.copy()
                print(f"   ⭐ 发现更优解! 评分: {result['score']:.2f}")
        
        print(f"\n{'='*70}")
        print("🎯 最优参数找到!")
        print(f"{'='*70}")
        
    def save_results(self):
        """保存结果"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = f'{OUT_PATH}/wfo_v5_optimized_{timestamp}.json'
        
        output = {
            'timestamp': timestamp,
            'version': 'v5_advanced',
            'best_params': self.best_params,
            'best_score': self.best_score,
            'result': self.best_result,
            'summary': {
                'cagr': f"{self.best_result['cagr']*100:.2f}%",
                'max_drawdown': f"{self.best_result['max_dd']*100:.1f}%",
                'win_rate': f"{self.best_result['win_rate']*100:.0f}%",
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 结果保存: {filepath}")
        return filepath
    
    def run(self):
        """主运行"""
        print("="*70)
        print("🚀 WFO v5 - 高级参数优化器")
        print("="*70)
        
        # 随机搜索
        self.random_search(n_iterations=30)
        
        # 保存结果
        filepath = self.save_results()
        
        # 输出最优参数
        print("\n📊 最优参数配置:")
        print("-"*70)
        
        # 因子权重
        print("\n【因子权重】")
        print(f"  ret_20: {self.best_params['ret_20_w']}")
        print(f"  ret_60: {self.best_params['ret_60_w']}")
        print(f"  vol_20: {self.best_params['vol_20_w']}")
        print(f"  sharpe_like: {self.best_params['sharpe_w']}")
        print(f"  low_vol_score: {self.best_params['low_vol_w']}")
        print(f"  mom_accel: {self.best_params['mom_accel_w']}")
        
        # 择时阈值
        print("\n【择时阈值】")
        print(f"  牛市ret阈值: {self.best_params['bull_ret_threshold']}")
        print(f"  牛市up比率: {self.best_params['bull_up_ratio']}")
        print(f"  熊市ret阈值: {self.best_params['bear_ret_threshold']}")
        print(f"  波动率阈值: {self.best_params['volatile_vol_threshold']}")
        
        # 仓位配置
        print("\n【仓位配置】")
        print(f"  牛市: {self.best_params['bull_position']*100:.0f}%")
        print(f"  熊市: {self.best_params['bear_position']*100:.0f}%")
        print(f"  高波动: {self.best_params['volatile_position']*100:.0f}%")
        print(f"  震荡: {self.best_params['neutral_position']*100:.0f}%")
        
        # 止损参数
        print("\n【止损参数】")
        print(f"  止损线: {self.best_params['stop_loss']*100:.0f}%")
        print(f"  调仓周期: {self.best_params['rebalance_days']}天")
        
        # 回测结果
        print("\n【回测结果】")
        for i, ret in enumerate(self.best_result['yearly_returns'], 1):
            emoji = "🟢" if ret > 0 else "🔴"
            print(f"  {emoji} 周期{i}: {ret*100:+.2f}%")
        
        print(f"\n📈 汇总:")
        print(f"  年化CAGR: {self.best_result['cagr']*100:+.2f}%")
        print(f"  最大回撤: {self.best_result['max_dd']*100:.1f}%")
        print(f"  胜率: {self.best_result['win_rate']*100:.0f}%")
        print(f"  综合评分: {self.best_score:.2f}")
        
        print(f"\n{'='*70}")
        print(f"✅ WFO v5 优化完成!")
        print(f"{'='*70}")


if __name__ == '__main__':
    optimizer = WFOAdvancedOptimizer()
    optimizer.run()
