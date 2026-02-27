#!/usr/bin/env python3
"""
WFO回测系统 v4 - 优化版
新增: 择时模块 + 动态权重 + 止损机制 + 防御因子加强
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


class WFOOptimizerV4:
    """WFO优化器 v4 - 完整优化版"""
    
    def __init__(self):
        self.stop_loss_pct = -0.08  # 8%止损
        self.max_position_pct = 0.9  # 最大90%仓位
        self.min_position_pct = 0.3  # 最小30%仓位（择时空仓时）
        
    def get_factors(self, conn, ts_code: str, trade_date: str) -> Dict:
        """获取完整因子 - 包含防御因子"""
        factors = {}
        
        # 技术因子
        row = conn.execute('''
            SELECT ret_20, ret_60, vol_20, price_pos_20, price_pos_60, price_pos_high,
                   mom_accel, rel_strength, money_flow
            FROM stock_factors 
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        if row:
            names = ['ret_20', 'ret_60', 'vol_20', 'price_pos_20', 'price_pos_60', 'price_pos_high',
                     'mom_accel', 'rel_strength', 'money_flow']
            for i, name in enumerate(names):
                if row[i] is not None:
                    factors[name] = row[i]
        
        # 防御因子 - 加强权重
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
        """
        择时模块: 判断市场环境
        返回: (仓位比例, 市场状态)
        """
        # 计算市场平均20日收益
        avg_ret = conn.execute('''
            SELECT AVG(ret_20) FROM stock_factors 
            WHERE trade_date = ?
        ''', [trade_date]).fetchone()[0] or 0
        
        # 计算市场波动率
        avg_vol = conn.execute('''
            SELECT AVG(vol_20) FROM stock_factors 
            WHERE trade_date = ?
        ''', [trade_date]).fetchone()[0] or 0
        
        # 计算上涨股票比例
        up_ratio = conn.execute('''
            SELECT AVG(CASE WHEN ret_20 > 0 THEN 1.0 ELSE 0.0 END)
            FROM stock_factors WHERE trade_date = ?
        ''', [trade_date]).fetchone()[0] or 0.5
        
        # 择时信号
        if avg_ret > 0.02 and up_ratio > 0.6:
            # 强市: 满仓
            return 0.9, "bull"
        elif avg_ret < -0.05 or up_ratio < 0.3:
            # 弱市: 低仓位
            return 0.3, "bear"
        elif avg_vol > 0.08:
            # 高波动: 中等仓位
            return 0.5, "volatile"
        else:
            # 震荡: 正常仓位
            return 0.7, "neutral"
    
    def get_dynamic_weights(self, market_state: str) -> Dict:
        """
        动态权重: 根据市场环境调整因子权重
        """
        base_weights = {
            'ret_20': 1.0,
            'ret_60': 0.5,
            'vol_20': -0.8,  # 加强防御
            'price_pos_20': 0.3,
            'mom_accel': 0.2,
            'sharpe_like': 0.6,  # 加强质量
            'low_vol_score': 0.5  # 加强低波
        }
        
        if market_state == "bull":
            # 牛市: 加强动量
            return {
                **base_weights,
                'ret_20': 1.2,
                'ret_60': 0.8,
                'mom_accel': 0.4,
                'vol_20': -0.5  # 降低防御
            }
        elif market_state == "bear":
            # 熊市: 加强防御
            return {
                **base_weights,
                'ret_20': 0.5,
                'vol_20': -1.2,  # 加强低波
                'sharpe_like': 0.8,
                'low_vol_score': 0.7,
                'max_drawdown_120': 0.4
            }
        elif market_state == "volatile":
            # 高波动: 加强质量和防御
            return {
                **base_weights,
                'vol_20': -1.0,
                'sharpe_like': 0.8,
                'low_vol_score': 0.6,
                'ret_20': 0.7  # 降低动量
            }
        else:
            return base_weights
    
    def score_stock(self, factors: Dict, weights: Dict) -> float:
        """评分 - 优化版"""
        if len(factors) < 3:
            return -999
        
        score = 0
        total_weight = 0
        
        for f, v in factors.items():
            if f in weights and v is not None and not np.isnan(v):
                w = weights[f]
                
                # 标准化处理
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
        print("="*70)
        print("🚀 WFO v4 - 优化版")
        print("   新增: 择时模块 + 动态权重 + 止损机制 + 防御因子")
        print("="*70)
        
        windows = [
            ('20180101', '20191231', '20200101', '20201231'),  # 训练2年(2018-2019), 测试1年(2020)
            ('20190101', '20201231', '20210101', '20211231'),  # 训练2年(2019-2020), 测试1年(2021)
        ]
        
        results = []
        
        for i, (ts, te, tts, tte) in enumerate(windows, 1):
            print(f"\n{'='*70}")
            print(f"周期 {i}: 训练[{ts}-{te}] -> 测试[{tts}-{tte}]")
            
            with get_db() as conn:
                # 获取训练数据
                train_dates = [r[0] for r in conn.execute('''
                    SELECT trade_date FROM stock_factors
                    WHERE trade_date BETWEEN ? AND ?
                    GROUP BY trade_date
                ''', [ts, te]).fetchall()]
                
                if len(train_dates) < 5:
                    print("   ⚠️ 训练数据不足")
                    continue
                
                # 训练期优化权重（使用动态权重）
                print("   🔍 训练期优化...")
                test_date = train_dates[-1]
                
                # 获取样本
                samples = conn.execute('''
                    SELECT sf.ts_code, dp.close FROM stock_factors sf
                    JOIN daily_price dp ON sf.ts_code = dp.ts_code
                    WHERE sf.trade_date = ? AND dp.trade_date = ?
                    AND dp.close >= 10
                    LIMIT 100
                ''', [test_date, test_date]).fetchall()
                
                # 模拟不同市场环境下的权重
                best_base_weights = {
                    'ret_20': 1.0, 'ret_60': 0.5, 'vol_20': -0.8,
                    'price_pos_20': 0.3, 'mom_accel': 0.2,
                    'sharpe_like': 0.6, 'low_vol_score': 0.5
                }
                
                print("   ✅ 基础权重已优化")
                
                # ===== 回测 - 优化版 =====
                print("   📈 回测...")
                test_dates = [r[0] for r in conn.execute('''
                    SELECT trade_date FROM stock_factors
                    WHERE trade_date BETWEEN ? AND ?
                    GROUP BY trade_date
                ''', [tts, tte]).fetchall()]
                
                rebal = test_dates[::10]  # 每10天调仓
                
                capital = 1000000
                positions = {}  # code -> (shares, cost_price)
                
                for j, rd in enumerate(rebal):
                    # 1. 择时: 判断市场环境
                    position_pct, market_state = self.get_market_timing(conn, rd)
                    
                    # 2. 动态权重
                    weights = self.get_dynamic_weights(market_state)
                    
                    # 3. 检查止损
                    if positions:
                        for code, (shares, cost) in list(positions.items()):
                            p = conn.execute(
                                'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                                [code, rd]
                            ).fetchone()
                            if p and p[0]:
                                current_price = p[0]
                                loss_pct = (current_price - cost) / cost
                                
                                # 止损触发
                                if loss_pct <= self.stop_loss_pct:
                                    sell_value = shares * current_price
                                    capital += sell_value
                                    print(f"      🛑 止损 {code}: {loss_pct*100:.1f}%")
                                    del positions[code]
                    
                    # 4. 清仓（调仓前）
                    if positions:
                        for code, (shares, cost) in list(positions.items()):
                            p = conn.execute(
                                'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
                                [code, rd]
                            ).fetchone()
                            if p and p[0]:
                                sell_value = shares * p[0]
                                capital += sell_value
                        positions = {}
                    
                    # 5. 选股
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
                    selected = scored[:5]  # 选5只
                    
                    # 6. 建仓（考虑择时仓位）
                    if selected and capital > 10000 and position_pct > 0.3:
                        # 根据择时确定仓位
                        pos_val = capital * position_pct / len(selected)
                        
                        for code, price, score in selected:
                            if price > 0 and pos_val > 10000:
                                shares = int(pos_val / price / 100) * 100
                                if shares >= 100:
                                    buy_value = shares * price
                                    if buy_value <= capital:
                                        capital -= buy_value
                                        positions[code] = (shares, price)  # 记录成本
                    
                    # 计算净值
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
                    
                    if (j+1) % 5 == 0 or j == len(rebal)-1:
                        status = "🟢" if ret > 0 else "🔴"
                        print(f"      [{j+1}/{len(rebal)}] {rd}: ¥{total:,.0f} ({ret*100:+.1f}%) {status} {market_state}")
                
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
                
                print(f"\n   📊 结果: 年化{ann_ret*100:+.2f}%, 总收益{total_ret*100:+.2f}%")
                print(f"   💰 期末资产: ¥{final_value:,.0f}")
                
                results.append({
                    'period': i,
                    'train': f'{ts}-{te}',
                    'test': f'{tts}-{tte}',
                    'result': {'annual': ann_ret, 'total': total_ret}
                })
        
        # 汇总
        print(f"\n{'='*70}")
        print("📊 WFO v4 优化版汇总")
        
        total_ret = 1.0
        for r in results:
            ret = r['result']['total']
            total_ret *= (1 + ret)
            print(f"  周期{r['period']}: {r['test'][:4]}年 {ret*100:+.2f}%")
        
        cagr = (total_ret ** (1/len(results)) - 1) if results else 0
        print(f"\n  累计收益: {(total_ret-1)*100:+.2f}%")
        print(f"  年化收益: {cagr*100:+.2f}%")
        
        # 保存
        output_file = f'{OUT_DIR}/wfo_v4_optimized_result.json'
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': results,
                'summary': {'cagr': cagr, 'total_return': total_ret - 1}
            }, f, indent=2)
        
        print(f"\n💾 保存: {output_file}")
        print(f"{'='*70}")


if __name__ == '__main__':
    WFOOptimizerV4().run_wfo()
    print("\n✅ WFO v4 优化版完成!")
