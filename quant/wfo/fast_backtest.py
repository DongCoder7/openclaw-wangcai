#!/usr/bin/env python3
"""
WFO真实回测 - 优化版本
使用简化的SQL查询和缓存
"""
import sqlite3
import numpy as np
from datetime import datetime
from typing import Dict, List

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class FastBacktest:
    """快速回测引擎"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        # 预加载因子数据到内存
        self._load_factors_cache()
        
    def _load_factors_cache(self):
        """预加载因子数据"""
        print("   加载因子缓存...")
        # 只加载最近的数据
        self.factors = {}
        for row in self.conn.execute('''
            SELECT ts_code, trade_date, ret_20, vol_20, price_pos_20
            FROM stock_factors 
            WHERE trade_date >= '20240101'
        ''').fetchall():
            key = (row[0], row[1])
            self.factors[key] = {'ret_20': row[2], 'vol_20': row[3], 'price_pos_20': row[4]}
        
        print(f"   缓存加载: {len(self.factors)} 条")
    
    def get_stocks_with_factors(self, trade_date: str, limit: int = 10):
        """获取有因子数据的股票"""
        # 先获取价格数据
        stocks = []
        for row in self.conn.execute('''
            SELECT ts_code, close FROM daily_price
            WHERE trade_date = ? AND close >= 10 AND volume > 0
            LIMIT 500
        ''', [trade_date]).fetchall():
            ts_code, close = row
            # 查找因子
            f = self.factors.get((ts_code, trade_date))
            if f and f['ret_20'] is not None:
                score = f['ret_20'] * 50 - (f['vol_20'] or 0) * 10
                stocks.append((ts_code, close, score))
        
        # 排序
        stocks.sort(key=lambda x: x[2], reverse=True)
        return stocks[:limit]
    
    def get_price(self, ts_code: str, trade_date: str) -> float:
        """获取价格"""
        row = self.conn.execute(
            'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
            [ts_code, trade_date]
        ).fetchone()
        return row[0] if row else None
    
    def run(self, start_date: str, end_date: str) -> Dict:
        """运行回测"""
        # 获取调仓日
        dates = [r[0] for r in self.conn.execute('''
            SELECT trade_date FROM daily_price 
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY trade_date ORDER BY trade_date
        ''', [start_date, end_date]).fetchall()]
        
        rebal_dates = dates[::10]  # 每10天
        print(f"   区间: {start_date} ~ {end_date}, 调仓: {len(rebal_dates)}次")
        
        capital = 1000000
        positions = {}  # {code: cost_value}
        
        for rd in rebal_dates:
            # 清仓
            for code in list(positions.keys()):
                p = self.get_price(code, rd)
                if p:
                    capital += positions[code]
            positions = {}
            
            # 选股
            stocks = self.get_stocks_with_factors(rd, 5)
            if stocks and capital > 0:
                pos_val = capital * 0.7 / len(stocks)
                for code, price, score in stocks:
                    if price > 0:
                        shares_val = int(pos_val / price / 100) * 100 * price
                        if shares_val > 1000:
                            capital -= shares_val
                            positions[code] = shares_val
            
            # 净值
            total = capital + sum(positions.values())
            print(f"   {rd}: ¥{total:,.0f} ({total/1000000*100-100:+.1f}%)")
        
        # 统计
        final = capital + sum(positions.values())
        ret = (final - 1000000) / 1000000
        years = len(rebal_dates) / 252
        ann_ret = (1+ret) ** (1/years) - 1 if years > 0 else 0
        
        return {'annual_return': ann_ret, 'total_return': ret}
    
    def close(self):
        self.conn.close()


if __name__ == '__main__':
    print("="*60)
    print("🚀 快速真实回测")
    print("="*60)
    
    bt = FastBacktest()
    result = bt.run('20240101', '20241231')
    
    print(f"\n📊 结果:")
    print(f"   年化: {result['annual_return']*100:+.2f}%")
    print(f"   总收益: {result['total_return']*100:+.2f}%")
    
    bt.close()
