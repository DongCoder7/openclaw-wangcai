#!/usr/bin/env python3
"""
WFO真实回测 - 修复版
使用最近可用因子数据
"""
import sqlite3
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class FixedBacktest:
    """修复版回测"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        
    def get_stocks(self, trade_date: str, limit: int = 10) -> List[Tuple]:
        """获取股票: 使用最近可用因子"""
        stocks = []
        
        # 查最近有数据的因子日期
        factor_date = self.conn.execute('''
            SELECT MAX(trade_date) FROM stock_factors WHERE trade_date <= ?
        ''', [trade_date]).fetchone()[0]
        
        if not factor_date:
            return []
        
        # 查有因子数据的股票
        for row in self.conn.execute(f'''
            SELECT dp.ts_code, dp.close, 
                   COALESCE(sf.ret_20, 0) as ret, 
                   COALESCE(sf.vol_20, 0.5) as vol
            FROM daily_price dp
            LEFT JOIN stock_factors sf ON dp.ts_code = sf.ts_code AND sf.trade_date = ?
            WHERE dp.trade_date = ?
            AND dp.close >= 10
            AND dp.volume > 0
            LIMIT 100
        ''', [factor_date, trade_date]).fetchall():
            ts_code, close, ret, vol = row
            if ret != 0:  # 有因子数据
                score = ret * 50 - vol * 10
                stocks.append((ts_code, close, score))
        
        stocks.sort(key=lambda x: x[2], reverse=True)
        return stocks[:limit]
    
    def get_price(self, ts_code: str, trade_date: str) -> Optional[float]:
        row = self.conn.execute(
            'SELECT close FROM daily_price WHERE ts_code=? AND trade_date=?',
            [ts_code, trade_date]
        ).fetchone()
        return row[0] if row else None
    
    def run(self, start_date: str, end_date: str) -> Dict:
        """运行回测"""
        dates = [r[0] for r in self.conn.execute('''
            SELECT trade_date FROM daily_price 
            WHERE trade_date BETWEEN ? AND ?
            GROUP BY trade_date ORDER BY trade_date
        ''', [start_date, end_date]).fetchall()]
        
        rebal = dates[::10]
        print(f"   {start_date}~{end_date}, 调仓{len(rebal)}次")
        
        capital = 1000000
        positions = {}
        
        for rd in rebal:
            # 清仓
            for code in list(positions.keys()):
                p = self.get_price(code, rd)
                if p:
                    capital += positions[code]
            positions = {}
            
            # 选股
            stocks = self.get_stocks(rd, 5)
            if stocks and capital > 0:
                pos_val = capital * 0.7 / len(stocks)
                for code, price, score in stocks:
                    if price > 0:
                        val = int(pos_val / price / 100) * 100 * price
                        if val > 1000:
                            capital -= val
                            positions[code] = val
            
            total = capital + sum(positions.values())
            print(f"   {rd}: ¥{total:,.0f} ({total/1000000*100-100:+.1f}%)")
        
        final = capital + sum(positions.values())
        ret = (final - 1000000) / 1000000
        years = len(rebal) / 252
        ann = (1+ret) ** (1/years) - 1 if years > 0 else 0
        
        return {'annual_return': ann, 'total_return': ret, 'final': final}
    
    def close(self):
        self.conn.close()


if __name__ == '__main__':
    print("="*50)
    print("🔧 修复版真实回测")
    print("="*50)
    
    bt = FixedBacktest()
    result = bt.run('20240101', '20241231')
    
    print(f"\n📊 2024年回测:")
    print(f"   年化: {result['annual_return']*100:+.2f}%")
    print(f"   总收益: {result['total_return']*100:+.2f}%")
    print(f"   最终: ¥{result['final']:,.0f}")
    
    bt.close()
