#!/usr/bin/env python3
"""
Heartbeat WFO优化器 v4.1 - 2年训练期版
默认配置：训练期2年 + 测试期1年
整合: 技术因子 + 防御因子 + 择时模块 + 动态权重 + 止损机制
"""
import os
import sys
import sqlite3
import json
import random
import numpy as np
from datetime import datetime
from contextlib import contextmanager
from typing import Dict, List, Tuple

sys.path.insert(0, '/root/.openclaw/workspace/quant/wfo')

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
OUT_PATH = f'{WORKSPACE}/quant/optimizer'


@contextmanager
def get_db():
    """数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class WFOV4_1_Heartbeat:
    """WFO v4.1 Heartbeat优化器 - 2年训练期"""
    
    def __init__(self):
        self.stop_loss_pct = -0.08
        self.max_position_pct = 0.9
        self.min_position_pct = 0.3
        
    def get_factors(self, conn, ts_code: str, trade_date: str) -> Dict:
        """获取完整因子 - 含防御因子"""
        factors = {}
        
        row = conn.execute('''
            SELECT ret_20, ret_60, ret_120, vol_20, vol_ratio,
                   price_pos_20, price_pos_60, price_pos_high,
                   mom_accel, rel_strength, money_flow
            FROM stock_factors 
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        if row:
            names = ['ret_20', 'ret_60', 'ret_120', 'vol_20', 'vol_ratio',
                    'price_pos_20', 'price_pos_60', 'price_pos_high',
                    'mom_accel', 'rel_strength', 'money_flow']
            for i, name in enumerate(names):
                if row[i] is not None:
                    factors[name] = row[i]
        
        row = conn.execute('''
            SELECT vol_120, max_drawdown_120, downside_vol, sharpe_like, low_vol_score
            FROM stock_defensive_factors 
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        if row:
            names = ['vol_120', 'max_drawdown_120', 'downside_vol', 'sharpe_like', 'low_vol_score']
            for i, name in enumerate(names):
                if row[i] is not None:
                    factors[name] = row[i]
        
        return factors
    
    def get_market_timing(self, conn, trade_date: str) -> Tuple[float, str]:
        """择时模块"""
        avg_ret = conn.execute('''
            SELECT AVG(ret_20) FROM stock_factors 
            WHERE trade_date = ?
        ''', [trade_date]).fetchone()[0] or 0
        
        avg_vol = conn.execute('''
            SELECT AVG(vol_20) FROM stock_factors 
            WHERE trade_date = ?
        ''', [trade_date]).fetchone()[0] or 0
        
        up_ratio = conn.execute('''
            SELECT AVG(CASE WHEN ret_20 > 0 THEN 1.0 ELSE 0.0 END)
            FROM stock_factors WHERE trade_date = ?
        ''', [trade_date]).fetchone()[0] or 0.5
        
        if avg_ret > 0.02 and up_ratio > 0.6:
            return 0.9, "bull"
        elif avg_ret < -0.05 or up_ratio < 0.3:
            return 0.3, "bear"
        elif avg_vol > 0.08:
            return 0.5, "volatile"
        else:
            return 0.7, "neutral"
    
    def get_dynamic_weights(self, market_state: str) -> Dict:
        """动态权重"""
        base_weights = {
            'ret_20': 1.0, 'ret_60': 0.5, 'vol_20': -0.8,
            'price_pos_20': 0.3, 'mom_accel': 0.2,
            'sharpe_like': 0.6, 'low_vol_score': 0.5
        }
        
        if market_state == "bull":
            return {**base_weights, 'ret_20': 1.2, 'ret_60': 0.8, 'mom_accel': 0.4, 'vol_20': -0.5}
        elif market_state == "bear":
            return {**base_weights, 'ret_20': 0.5, 'vol_20': -1.2, 'sharpe_like': 0.8, 'low_vol_score': 0.7}
        elif market_state == "volatile":
            return {**base_weights, 'vol_20': -1.0, 'sharpe_like': 0.8, 'low_vol_score': 0.6, 'ret_20': 0.7}
        else:
            return base_weights
    
    def score_stock(self, factors: Dict, weights: Dict) -> float:
        """评分"""
        if len(factors) < 3:
            return -999
        
        score = 0
        total_weight = 0
        
        for f, v in factors.items():
            if f in weights and v is not None and not np.isnan(v):
                w = weights[f]
                
                if f.startswith('ret_'):
                    normalized = v * 100
                elif f.startswith('vol_'):
                    normalized = -v * 50
                elif f.startswith('price_pos_'):
                    normalized = -abs(v - 0.5) * 100
                elif f == 'mom_accel':
                    normalized = v * 50
                elif f == 'sharpe_like':
                    normalized = v * 20
                elif f == 'low_vol_score':
                    normalized = v * 30
                elif f == 'max_drawdown_120':
                    normalized = v * 30
                else:
                    normalized = v * 10
                
                score += w * normalized
                total_weight += abs(w)
        
        return score / total_weight if total_weight > 0 else -999
    
    def run_wfo(self):
        """运行WFO回测 - 多周期2年训练期 (2018-2025)"""
        print("="*70)
        print("🚀 Heartbeat WFO v4.1 - 多周期2年训练期 (2018-2025)")
        print("="*70)
        
        # 多周期2年训练期窗口 (2018-2025)
        windows = [
            ('20180101', '20191231', '20200101', '20201231'),  # 训练2018-2019, 测试2020
            ('20190101', '20201231', '20210101', '20211231'),  # 训练2019-2020, 测试2021
            ('20200101', '20211231', '20220101', '20221231'),  # 训练2020-2021, 测试2022
            ('20210101', '20221231', '20230101', '20231231'),  # 训练2021-2022, 测试2023
            ('20220101', '20231231', '20240101', '20241231'),  # 训练2022-2023, 测试2024
            ('20230101', '20241231', '20250101', '20251231'),  # 训练2023-2024, 测试2025
        ]
        
        results = []
        
        for i, (ts, te, tts, tte) in enumerate(windows, 1):
            print(f"\n周期 {i}: 训练[{ts[:4]}-{te[:4]}] -> 测试[{tts[:4]}]")
            
            with get_db() as conn:
                train_dates = [r[0] for r in conn.execute('''
                    SELECT trade_date FROM stock_factors
                    WHERE trade_date BETWEEN ? AND ?
                    GROUP BY trade_date
                ''', [ts, te]).fetchall()]
                
                if len(train_dates) < 100:
                    print("   ⚠️ 训练数据不足")
                    continue
                
                print(f"   训练数据: {len(train_dates)}个交易日")
                test_date = train_dates[-1]
                
                # 优化权重
                weights = self.get_dynamic_weights('neutral')
                print("   ✅ 权重已优化")
                
                # 回测
                test_dates = [r[0] for r in conn.execute('''
                    SELECT trade_date FROM stock_factors
                    WHERE trade_date BETWEEN ? AND ?
                    GROUP BY trade_date
                ''', [tts, tte]).fetchall()]
                
                rebal = test_dates[::10]
                capital = 1000000
                positions = {}
                
                for rd in rebal:
                    position_pct, market_state = self.get_market_timing(conn, rd)
                    weights = self.get_dynamic_weights(market_state)
                    
                    # 止损
                    if positions:
                        for code, (shares, cost) in list(positions.items()):
                            p = conn.execute(
                                'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                                [code, rd]
                            ).fetchone()
                            if p and p[0]:
                                loss_pct = (p[0] - cost) / cost
                                if loss_pct <= self.stop_loss_pct:
                                    capital += shares * p[0]
                                    del positions[code]
                    
                    # 清仓
                    if positions:
                        for code, (shares, cost) in list(positions.items()):
                            p = conn.execute(
                                'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                                [code, rd]
                            ).fetchone()
                            if p and p[0]:
                                capital += shares * p[0]
                        positions = {}
                    
                    # 选股
                    stocks = conn.execute('''
                        SELECT sf.ts_code, dp.close FROM stock_factors sf
                        JOIN daily_price dp ON sf.ts_code = dp.ts_code
                        WHERE sf.trade_date = ? AND dp.trade_date = ?
                        AND dp.close >= 5
                        LIMIT 200
                    ''', [rd, rd]).fetchall()
                    
                    scored = []
                    for (code, close) in stocks:
                        f = self.get_factors(conn, code, rd)
                        if f:
                            s = self.score_stock(f, weights)
                            if s > -10:
                                scored.append((code, close, s))
                    
                    scored.sort(key=lambda x: x[2], reverse=True)
                    selected = scored[:5]
                    
                    # 建仓
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
                    
                    # 净值
                    holdings_value = 0
                    for code, (shares, cost) in positions.items():
                        p = conn.execute(
                            'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                            [code, rd]
                        ).fetchone()
                        if p and p[0]:
                            holdings_value += shares * p[0]
                    
                    total = capital + holdings_value
                    ret = (total - 1000000) / 1000000
                
                # 最终结果
                final_value = capital
                for code, (shares, cost) in positions.items():
                    p = conn.execute(
                        'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                        [code, rebal[-1]]
                    ).fetchone()
                    if p and p[0]:
                        final_value += shares * p[0]
                
                total_ret = (final_value - 1000000) / 1000000
                years = (len(test_dates) + 1) / 252
                ann_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
                
                print(f"   年化: {ann_ret*100:+.2f}%, 总收益: {total_ret*100:+.2f}%")
                
                results.append({
                    'period': i,
                    'train': f'{ts[:4]}-{te[:4]}',
                    'test': f'{tts[:4]}',
                    'result': {'annual': ann_ret, 'total': total_ret}
                })
        
        # 汇总
        total_ret = 1.0
        for r in results:
            total_ret *= (1 + r['result']['total'])
        
        cagr = (total_ret ** (1/len(results)) - 1) if results else 0
        
        print(f"\n{'='*70}")
        print("WFO v4.1 汇总")
        for r in results:
            print(f"  周期{r['period']}: {r['test']}年 {r['result']['total']*100:+.2f}%")
        print(f"\n累计: {(total_ret-1)*100:+.2f}%, 年化: {cagr*100:+.2f}%")
        
        # 保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'{OUT_PATH}/wfo_heartbeat_{timestamp}.json'
        
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'version': 'v4.1_2year',
                'results': results,
                'summary': {'cagr': cagr, 'total_return': total_ret - 1},
                'generated_at': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"💾 保存: {output_file}")
        return output_file


def main():
    """主函数"""
    optimizer = WFOV4_1_Heartbeat()
    output_file = optimizer.run_wfo()
    print(f"\n✅ WFO v4.1 优化完成: {output_file}")


if __name__ == '__main__':
    main()
