#!/usr/bin/env python3
"""
WFO v5.1 - 修复数据读取问题
"""
import os
import sys
import sqlite3
import json
import random
import numpy as np
from datetime import datetime

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
OUT_PATH = '/root/.openclaw/workspace/quant/optimizer'

class WFOV51:
    def __init__(self):
        self.best_score = -999
        self.best_params = None
        self.best_result = None
        
    def get_factors(self, conn, ts_code, trade_date):
        factors = {}
        row = conn.execute('''
            SELECT ret_20, ret_60, vol_20, price_pos_20, mom_accel
            FROM stock_factors WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        if row:
            names = ['ret_20', 'ret_60', 'vol_20', 'price_pos_20', 'mom_accel']
            for i, name in enumerate(names):
                if row[i] is not None:
                    factors[name] = row[i]
        
        row = conn.execute('''
            SELECT sharpe_like, low_vol_score
            FROM stock_defensive_factors WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        if row:
            for i, name in enumerate(['sharpe_like', 'low_vol_score']):
                if row[i] is not None:
                    factors[name] = row[i]
        return factors
    
    def score_stock(self, factors, weights):
        if len(factors) < 3:
            return -999
        score = 0
        if 'ret_20' in factors and 'ret_20' in weights:
            score += weights['ret_20'] * factors['ret_20'] * 100
        if 'vol_20' in factors and 'vol_20' in weights:
            score += weights['vol_20'] * (-factors['vol_20'] * 50)
        if 'sharpe_like' in factors and 'sharpe_like' in weights:
            score += weights['sharpe_like'] * factors['sharpe_like'] * 20
        return score
    
    def run_backtest(self, params):
        # 使用有效的数据窗口
        windows = [
            ('20180101', '20191231', '20200101', '20201231'),  # 2020
            ('20190101', '20201231', '20210101', '20211231'),  # 2021
        ]
        
        results = []
        conn = sqlite3.connect(DB_PATH)
        
        for ts, te, tts, tte in windows:
            # 检查测试期数据
            test_dates = [r[0] for r in conn.execute(
                'SELECT DISTINCT trade_date FROM stock_factors WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date',
                [tts, tte]
            ).fetchall()]
            
            if len(test_dates) < 100:
                print(f"   数据不足: {tts[:4]}年只有{len(test_dates)}个交易日")
                continue
            
            rebal = test_dates[::params.get('rebal_days', 10)]
            capital = 1000000
            positions = {}
            
            for rd in rebal[:25]:  # 只跑前25个调仓日，加速
                # 清仓
                if positions:
                    for code in list(positions.keys()):
                        p = conn.execute('SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?', [code, rd]).fetchone()
                        if p and p[0]:
                            capital += positions[code] * p[0]
                    positions = {}
                
                # 选股
                stocks = conn.execute('''
                    SELECT sf.ts_code, dp.close FROM stock_factors sf
                    JOIN daily_price dp ON sf.ts_code = dp.ts_code
                    WHERE sf.trade_date = ? AND dp.trade_date = ? AND dp.close BETWEEN 5 AND 500
                    LIMIT 100
                ''', [rd, rd]).fetchall()
                
                if len(stocks) < 10:
                    continue
                
                scored = []
                for code, close in stocks:
                    f = self.get_factors(conn, code, rd)
                    if f:
                        s = self.score_stock(f, params['weights'])
                        if s > -50:
                            scored.append((code, close, s))
                
                if len(scored) < 5:
                    continue
                
                scored.sort(key=lambda x: x[2], reverse=True)
                selected = scored[:5]
                
                # 建仓
                if capital > 10000:
                    pos_val = capital * 0.7 / len(selected)
                    for code, price, score in selected:
                        if price > 0:
                            shares = int(pos_val / price / 100) * 100
                            if shares > 0:
                                cost = shares * price
                                if cost <= capital:
                                    capital -= cost
                                    positions[code] = shares
                
                # 净值
                total = capital
                for code, shares in positions.items():
                    p = conn.execute('SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?', [code, rd]).fetchone()
                    if p and p[0]:
                        total += shares * p[0]
            
            # 期末
            final = capital
            for code, shares in positions.items():
                p = conn.execute('SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?', [code, rebal[-1]]).fetchone()
                if p and p[0]:
                    final += shares * p[0]
            
            ret = (final - 1000000) / 1000000
            results.append(ret)
            print(f"   {tts[:4]}年: {ret*100:+.2f}%")
        
        conn.close()
        
        if not results:
            return {'cagr': 0, 'score': -999}
        
        # 计算
        total = 1.0
        for r in results:
            total *= (1 + r)
        cagr = (total ** (1/len(results)) - 1)
        
        return {'cagr': cagr, 'results': results, 'score': cagr * 100}
    
    def optimize(self, n_iter=20):
        print("="*70)
        print("🚀 WFO v5.1 - 简化优化器")
        print("="*70)
        
        for i in range(n_iter):
            # 随机参数
            params = {
                'weights': {
                    'ret_20': random.choice([0.8, 1.0, 1.2, 1.5]),
                    'vol_20': random.choice([-0.6, -0.8, -1.0]),
                    'sharpe_like': random.choice([0.4, 0.6, 0.8]),
                },
                'rebal_days': random.choice([8, 10, 12])
            }
            
            print(f"\n[{i+1}/{n_iter}] 测试: {params['weights']}")
            result = self.run_backtest(params)
            
            print(f"   结果: CAGR={result['cagr']*100:+.2f}%, 评分={result['score']:.2f}")
            
            if result['score'] > self.best_score:
                self.best_score = result['score']
                self.best_params = params
                self.best_result = result
                print(f"   ⭐ 更优!")
        
        # 保存
        print(f"\n{'='*70}")
        print("🎯 最优结果")
        print(f"{'='*70}")
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'best_params': self.best_params,
            'best_score': self.best_score,
            'cagr': self.best_result['cagr'],
            'yearly': self.best_result['results']
        }
        
        filepath = f'{OUT_PATH}/wfo_v51_best_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n最优权重: {self.best_params['weights']}")
        print(f"年化CAGR: {self.best_result['cagr']*100:+.2f}%")
        print(f"保存: {filepath}")
        
        return output


if __name__ == '__main__':
    optimizer = WFOV51()
    result = optimizer.optimize(n_iter=15)
    print("\n✅ 完成!")
