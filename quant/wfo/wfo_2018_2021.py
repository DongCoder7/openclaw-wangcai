#!/usr/bin/env python3
"""
WFO历史回测 - 仅用价格/成交量计算技术指标
"""
import os
import sys
import sqlite3
import json
import numpy as np
from datetime import datetime
from typing import Dict, List

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
OUT_DIR = '/root/.openclaw/workspace/quant/wfo/results'
os.makedirs(OUT_DIR, exist_ok=True)


class PriceMomentumWFO:
    """纯价格动量WFO"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def get_historical_prices(self, ts_code: str, end_date: str, days: int = 60) -> List[float]:
        """获取历史价格序列"""
        rows = self.conn.execute('''
            SELECT close FROM stock_efinance
            WHERE ts_code = ? AND trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT ?
        ''', [ts_code, end_date, days]).fetchall()
        
        return [r[0] for r in rows if r[0] is not None][::-1]  # 正序
    
    def calculate_momentum_score(self, ts_code: str, trade_date: str) -> float:
        """计算动量评分 (仅用价格数据)"""
        prices = self.get_historical_prices(ts_code, trade_date, 60)
        
        if len(prices) < 20:
            return -999
        
        # 20日收益率
        ret_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] > 0 else 0
        
        # 60日收益率
        ret_60 = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        
        # 波动率 (20日)
        returns = []
        for i in range(len(prices)-20, len(prices)):
            if i > 0 and prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        vol = np.std(returns) * np.sqrt(252) if returns else 0.5
        
        # 动量评分: 高收益 + 低波动
        score = ret_20 * 100 - vol * 20 + ret_60 * 50
        
        return score
    
    def select_stocks(self, trade_date: str, max_holding: int = 5) -> List[Dict]:
        """选股"""
        stocks = []
        
        # 获取当日有交易的股票
        for row in self.conn.execute('''
            SELECT ts_code, close, volume
            FROM stock_efinance
            WHERE trade_date = ?
            AND close >= 10
            AND volume > 0
            LIMIT 100
        ''', [trade_date]).fetchall():
            
            ts_code, close, volume = row
            
            # 计算动量评分
            score = self.calculate_momentum_score(ts_code, trade_date)
            
            if score > -100:  # 有效评分
                stocks.append({
                    'ts_code': ts_code,
                    'price': close,
                    'score': score
                })
        
        # 排序
        stocks.sort(key=lambda x: x['score'], reverse=True)
        return stocks[:max_holding]
    
    def run_backtest(self, start_date: str, end_date: str) -> Dict:
        """回测"""
        print(f"   回测: {start_date} ~ {end_date}")
        
        # 获取交易日
        dates = [r[0] for r in self.conn.execute('''
            SELECT DISTINCT trade_date FROM stock_efinance
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        ''', [start_date, end_date]).fetchall()]
        
        rebalance_dates = dates[::10]  # 每10天
        print(f"   调仓: {len(rebalance_dates)}次")
        
        if len(rebalance_dates) < 2:
            return {'annual_return': 0, 'total_return': 0}
        
        capital = 1000000
        positions = {}  # {code: {'shares': int, 'cost': float}}
        
        for i, rd in enumerate(rebalance_dates):
            # 清仓
            for code in list(positions.keys()):
                price = self.conn.execute('''
                    SELECT close FROM stock_efinance
                    WHERE ts_code = ? AND trade_date = ?
                ''', [code, rd]).fetchone()
                
                if price:
                    capital += positions[code]['shares'] * price[0]
            
            positions = {}
            
            # 选股
            selected = self.select_stocks(rd, 5)
            
            # 建仓
            if selected and capital > 0:
                pos_val = capital * 0.7 / len(selected)
                
                for stock in selected:
                    price = stock['price']
                    if price > 0:
                        shares = int(pos_val / price / 100) * 100
                        if shares > 0:
                            capital -= shares * price
                            positions[stock['ts_code']] = {
                                'shares': shares,
                                'cost': price
                            }
            
            # 净值
            total = capital
            for code, pos in positions.items():
                price = self.conn.execute('''
                    SELECT close FROM stock_efinance
                    WHERE ts_code = ? AND trade_date = ?
                ''', [code, rd]).fetchone()
                
                if price:
                    total += pos['shares'] * price[0]
            
            if (i + 1) % 5 == 0 or i == len(rebalance_dates) - 1:
                ret = (total - 1000000) / 1000000 * 100
                print(f"      [{i+1}/{len(rebalance_dates)}] {rd}: "
                      f"¥{total:,.0f} ({ret:+.1f}%) 持仓{len(positions)}")
        
        # 统计
        final = capital
        for code, pos in positions.items():
            price = self.conn.execute('''
                SELECT close FROM stock_efinance
                WHERE ts_code = ? AND trade_date = ?
            ''', [code, rebalance_dates[-1]]).fetchone()
            
            if price:
                final += pos['shares'] * price[0]
        
        total_ret = (final - 1000000) / 1000000
        years = len(rebalance_dates) / 252
        ann_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
        
        return {
            'annual_return': ann_ret,
            'total_return': total_ret,
            'final_value': final
        }
    
    def run_wfo_2018_2021(self):
        """运行2018-2021 WFO"""
        print("="*70)
        print("🚀 WFO 历史回测 (2018-2021 纯价格动量)")
        print("="*70)
        
        # 4个周期: 每年滚动
        periods = [
            ('20180101', '20181231', '2019'),
            ('20190101', '20191231', '2020'),
            ('20200101', '20201231', '2021'),
            ('20210101', '20211231', '2022'),
        ]
        
        results = []
        for train_start, train_end, test_year in periods:
            test_start = f'{test_year}0101'
            test_end = f'{test_year}1231'
            
            print(f"\n{'='*70}")
            print(f"🚀 WFO周期: 训练[{train_start}-{train_end}] -> 测试[{test_year}]")
            print(f"{'='*70}")
            
            result = self.run_backtest(test_start, test_end)
            
            results.append({
                'period': test_year,
                'train': f'{train_start}-{train_end}',
                'test': f'{test_start}-{test_end}',
                'result': result
            })
        
        # 报告
        print(f"\n{'='*70}")
        print("📊 WFO历史回测报告")
        print(f"{'='*70}")
        
        total_return = 1.0
        for r in results:
            ret = r['result']['total_return']
            total_return *= (1 + ret)
            print(f"\n{r['period']}年:")
            print(f"  收益: {ret*100:+.2f}%")
            print(f"  年化: {r['result']['annual_return']*100:+.2f}%")
        
        cagr = (total_return ** (1/len(results)) - 1) if results else 0
        print(f"\n【汇总】")
        print(f"  累计收益: {(total_return-1)*100:+.2f}%")
        print(f"  年化CAGR: {cagr*100:+.2f}%")
        
        # 保存
        with open(f'{OUT_DIR}/wfo_2018_2021_momentum.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': results,
                'summary': {'cagr': cagr}
            }, f, indent=2)
        
        print(f"\n💾 保存: wfo_2018_2021_momentum.json")
        print(f"{'='*70}")


if __name__ == '__main__':
    wfo = PriceMomentumWFO()
    wfo.run_wfo_2018_2021()
    print("\n✅ 历史WFO完成！")
