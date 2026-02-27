#!/usr/bin/env python3
"""
WFO v26 完整历史版
整合多数据源:
- 2018-2021: stock_efinance (PE/PB/换手率)
- 2022-2024: stock_factors (技术因子)
- 2025-2026: stock_factors + stock_defensive_factors (完整26因子)
"""
import os
import sys
import sqlite3
import json
import random
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
OUT_DIR = '/root/.openclaw/workspace/quant/wfo/results'
os.makedirs(OUT_DIR, exist_ok=True)


class HistoricalWFOEngine:
    """历史数据WFO引擎"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_data_source(self, trade_date: str) -> str:
        """判断数据源"""
        year = int(trade_date[:4])
        if year <= 2021:
            return 'efinance'
        elif year >= 2025:
            return 'full_factors'
        else:
            return 'partial_factors'
    
    def select_stocks_historical(self, trade_date: str, max_holding: int = 5) -> List[Tuple]:
        """历史数据选股 (2018-2021)"""
        stocks = []
        
        # 使用efinance数据: PE/PB/换手率
        for row in self.conn.execute('''
            SELECT ts_code, close, pe, pb, turnover_rate, change_pct
            FROM stock_efinance
            WHERE trade_date = ?
            AND close >= 10
            AND pe > 0 AND pe < 100  -- 合理PE
            AND pb > 0 AND pb < 10     -- 合理PB
            LIMIT 200
        ''', [trade_date]).fetchall():
            
            ts_code, close, pe, pb, turnover, change = row
            
            # 价值+动量评分
            score = 0
            # 低PE加分 (PE 10-30最佳)
            if pe < 30:
                score += (30 - pe) * 2
            # 低PB加分
            if pb < 3:
                score += (3 - pb) * 10
            # 换手率适中 (1%-5%)
            if 1 <= turnover <= 5:
                score += 5
            # 近期涨幅 (动量)
            if change and change > 0:
                score += change * 2
            
            stocks.append((ts_code, close, score))
        
        # 排序选top
        stocks.sort(key=lambda x: x[2], reverse=True)
        return stocks[:max_holding]
    
    def select_stocks_modern(self, trade_date: str, max_holding: int = 5) -> List[Tuple]:
        """现代数据选股 (2025+ 完整因子)"""
        stocks = []
        
        # 找最近有数据的因子日期
        factor_date = self.conn.execute('''
            SELECT MAX(trade_date) FROM stock_factors WHERE trade_date <= ?
        ''', [trade_date]).fetchone()[0]
        
        if not factor_date:
            return []
        
        for row in self.conn.execute('''
            SELECT dp.ts_code, dp.close, sf.ret_20, sf.vol_20, sdf.sharpe_like
            FROM daily_price dp
            JOIN stock_factors sf ON dp.ts_code = sf.ts_code AND sf.trade_date = ?
            LEFT JOIN stock_defensive_factors sdf ON dp.ts_code = sdf.ts_code AND sdf.trade_date = ?
            WHERE dp.trade_date = ?
            AND dp.close >= 10
            LIMIT 200
        ''', [factor_date, factor_date, trade_date]).fetchall():
            
            ts_code, close, ret_20, vol_20, sharpe = row
            
            if ret_20 is not None:
                # 动量+防御评分
                score = ret_20 * 100 - (vol_20 or 0.5) * 30
                if sharpe and sharpe > 0:
                    score += sharpe * 20
                
                stocks.append((ts_code, close, score))
        
        stocks.sort(key=lambda x: x[2], reverse=True)
        return stocks[:max_holding]
    
    def select_stocks(self, trade_date: str, max_holding: int = 5) -> List[Tuple]:
        """统一选股接口"""
        source = self.get_data_source(trade_date)
        
        if source == 'efinance':
            return self.select_stocks_historical(trade_date, max_holding)
        else:
            return self.select_stocks_modern(trade_date, max_holding)
    
    def get_price(self, ts_code: str, trade_date: str) -> float:
        """获取价格"""
        # 优先从efinance获取(2018-2021)
        row = self.conn.execute('''
            SELECT close FROM stock_efinance 
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        if row:
            return row[0]
        
        # 从daily_price获取(2022+)
        row = self.conn.execute('''
            SELECT close FROM daily_price 
            WHERE ts_code = ? AND trade_date = ?
        ''', [ts_code, trade_date]).fetchone()
        
        return row[0] if row else None
    
    def run_backtest(self, start_date: str, end_date: str,
                    position_pct: float = 0.7,
                    stop_loss: float = 0.08,
                    max_holding: int = 5,
                    rebalance_days: int = 10) -> Dict:
        """执行回测"""
        print(f"   回测: {start_date} ~ {end_date}")
        
        # 获取交易日
        dates = []
        
        # 2018-2021从efinance获取
        if int(start_date[:4]) <= 2021:
            dates += [r[0] for r in self.conn.execute('''
                SELECT DISTINCT trade_date FROM stock_efinance
                WHERE trade_date BETWEEN ? AND ?
                ORDER BY trade_date
            ''', [start_date, min(end_date, '20211231')]).fetchall()]
        
        # 2022+从daily_price获取
        if int(end_date[:4]) >= 2022:
            dates += [r[0] for r in self.conn.execute('''
                SELECT DISTINCT trade_date FROM daily_price
                WHERE trade_date BETWEEN ? AND ?
                ORDER BY trade_date
            ''', [max(start_date, '20220101'), end_date]).fetchall()]
        
        # 去重排序
        dates = sorted(set(dates))
        
        if len(dates) < 10:
            print(f"   ⚠️ 交易日不足: {len(dates)}")
            return {'annual_return': 0, 'max_drawdown': 0, 'total_return': 0}
        
        rebalance_dates = dates[::rebalance_days]
        print(f"   调仓: {len(rebalance_dates)}次")
        
        capital = 1000000
        positions = {}
        equity_curve = []
        
        for i, rd in enumerate(rebalance_dates):
            # 清仓
            for code in list(positions.keys()):
                p = self.get_price(code, rd)
                if p:
                    capital += positions[code]
            positions = {}
            
            # 选股
            selected = self.select_stocks(rd, max_holding)
            
            # 建仓
            if selected and capital > 0:
                pos_val = capital * position_pct / len(selected)
                for code, price, score in selected:
                    if price and price > 0:
                        val = int(pos_val / price / 100) * 100 * price
                        if val > 1000:
                            capital -= val
                            positions[code] = val
            
            # 净值
            total = capital + sum(positions.values())
            equity_curve.append({'date': rd, 'equity': total})
            
            if (i + 1) % 5 == 0 or i == len(rebalance_dates) - 1:
                ret = (total - 1000000) / 1000000 * 100
                source = self.get_data_source(rd)
                print(f"      [{i+1}/{len(rebalance_dates)}] {rd} ({source}): "
                      f"¥{total:,.0f} ({ret:+.1f}%)")
        
        # 统计
        final = capital + sum(positions.values())
        total_ret = (final - 1000000) / 1000000
        
        # 最大回撤
        max_dd = 0
        peak = equity_curve[0]['equity']
        for e in equity_curve:
            if e['equity'] > peak:
                peak = e['equity']
            dd = (e['equity'] - peak) / peak
            if dd < max_dd:
                max_dd = dd
        
        # 年化
        days = len(equity_curve)
        years = days / 252
        ann_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
        
        return {
            'annual_return': ann_ret,
            'max_drawdown': max_dd,
            'total_return': total_ret,
            'days': days
        }
    
    def generate_wfo_windows(self) -> List[Dict]:
        """生成WFO窗口"""
        # 基于实际数据可用性
        windows = [
            # 2018-2019训练 -> 2020测试 (efinance数据)
            {'period': 1, 'train': ('20180101', '20191231'), 'test': ('20200101', '20201231'), 'type': 'historical'},
            # 2019-2020训练 -> 2021测试
            {'period': 2, 'train': ('20190101', '20201231'), 'test': ('20210101', '20211231'), 'type': 'historical'},
            # 2020-2021训练 -> 2022测试 (数据过渡期)
            {'period': 3, 'train': ('20200101', '20211231'), 'test': ('20220101', '20221231'), 'type': 'transition'},
            # 2025训练 -> 2026测试 (完整因子)
            {'period': 4, 'train': ('20250101', '20251231'), 'test': ('20260101', '20260213'), 'type': 'modern'},
        ]
        return windows
    
    def run_full_wfo(self):
        """执行完整WFO"""
        print("="*70)
        print("🚀 WFO v26 完整历史版")
        print("="*70)
        print("数据源:")
        print("  2018-2021: stock_efinance (PE/PB/价值因子)")
        print("  2022-2024: 混合数据源")
        print("  2025-2026: stock_factors (完整26因子)")
        print("="*70)
        
        windows = self.generate_wfo_windows()
        results = []
        
        for w in windows:
            print(f"\n{'='*70}")
            print(f"🚀 WFO周期 {w['period']} ({w['type']})")
            print(f"{'='*70}")
            print(f"训练: {w['train'][0]} ~ {w['train'][1]}")
            print(f"测试: {w['test'][0]} ~ {w['test'][1]}")
            
            # v26因子选择 (简化版)
            print(f"\n   🔍 v26因子选择...")
            if w['type'] == 'historical':
                factors = ['pe', 'pb', 'turnover', 'momentum']  # 历史可用因子
                print(f"   选中: 价值因子(PE/PB) + 动量")
            elif w['type'] == 'modern':
                factors = ['ret_20', 'vol_20', 'sharpe_like', 'roe']  # 现代完整因子
                print(f"   选中: 技术+防御+财务因子")
            else:
                factors = ['mixed']
                print(f"   选中: 混合策略")
            
            # 回测
            result = self.run_backtest(
                w['test'][0], w['test'][1],
                position_pct=0.7,
                stop_loss=0.08,
                max_holding=5,
                rebalance_days=10
            )
            
            results.append({
                'period': w['period'],
                'type': w['type'],
                'train': w['train'],
                'test': w['test'],
                'factors': factors,
                'result': result
            })
        
        # 汇总报告
        self._generate_report(results)
        return results
    
    def _generate_report(self, results: List[Dict]):
        """生成报告"""
        print(f"\n{'='*70}")
        print("📊 WFO完整历史报告")
        print(f"{'='*70}")
        
        print(f"\n【各周期结果】")
        total_return = 1.0
        
        for r in results:
            ret = r['result']['total_return']
            total_return *= (1 + ret)
            
            print(f"\n周期 {r['period']} ({r['type']}):")
            print(f"  训练: {r['train'][0]}~{r['train'][1]}")
            print(f"  测试: {r['test'][0]}~{r['test'][1]}")
            print(f"  因子: {', '.join(r['factors'][:2])}")
            print(f"  收益: {ret*100:+.2f}%")
            print(f"  回撤: {r['result']['max_drawdown']*100:.2f}%")
        
        # 汇总
        cagr = (total_return ** (1/len(results)) - 1) if results else 0
        
        print(f"\n【汇总统计】")
        print(f"  总周期: {len(results)}")
        print(f"  累计收益: {(total_return-1)*100:+.2f}%")
        print(f"  年化收益: {cagr*100:+.2f}%")
        
        # 保存
        with open(f'{OUT_DIR}/wfo_historical_full.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': results,
                'summary': {'cagr': cagr, 'total_return': total_return-1}
            }, f, indent=2, default=str)
        
        print(f"\n💾 保存: wfo_historical_full.json")
        print(f"{'='*70}")


if __name__ == '__main__':
    engine = HistoricalWFOEngine()
    engine.run_full_wfo()
    print("\n✅ 历史WFO执行完毕！")
