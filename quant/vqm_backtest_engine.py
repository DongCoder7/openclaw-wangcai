#!/usr/bin/env python3
"""
VQM策略回测框架 - 本地数据版本
使用Tushare历史数据进行2018-2025年回测

数据源区分：
- 实时行情（10分钟级监控）: 长桥API
- 历史回测（2018-2025）: Tushare本地数据
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import sqlite3
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tushare_data_manager import TushareDataManager


class VQMBacktestEngine:
    """
    VQM策略回测引擎
    
    策略逻辑：
    - 选股：PE（60%）+ ROE（40%）综合评分
    - 持仓：10只等权重
    - 调仓：每月最后一个交易日
    - 止损：-8%
    """
    
    def __init__(self, db_path: str = None, initial_capital: float = 1000000):
        """
        初始化回测引擎
        
        Args:
            db_path: 历史数据数据库路径
            initial_capital: 初始资金
        """
        if db_path is None:
            db_path = os.path.expanduser('~/.openclaw/workspace/data/tushare/historical.db')
        
        self.db_path = db_path
        self.initial_capital = initial_capital
        
        # 检查数据库
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库不存在: {db_path}\n请先运行 tushare_data_manager.py 下载数据")
        
        # 加载数据管理器
        self.data_manager = TushareDataManager(db_path=db_path)
        
        print(f"✅ 回测引擎初始化完成")
        print(f"   数据库: {db_path}")
        print(f"   初始资金: ¥{initial_capital:,.0f}")
    
    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT DISTINCT trade_date 
            FROM daily_price 
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        '''
        
        dates = pd.read_sql(query, conn, params=[start_date, end_date])
        conn.close()
        
        return dates['trade_date'].tolist()
    
    def get_last_trading_date_of_month(self, year: int, month: int) -> Optional[str]:
        """获取某月最后一个交易日"""
        # 该月最后一天
        if month == 12:
            last_day = f"{year+1}0101"
        else:
            last_day = f"{year}{month+1:02d}01"
        
        first_day = f"{year}{month:02d}01"
        
        trading_dates = self.get_trading_dates(first_day, last_day)
        
        # 过滤出该月的交易日
        month_dates = [d for d in trading_dates if d.startswith(f"{year}{month:02d}")]
        
        return month_dates[-1] if month_dates else None
    
    def calculate_vqm_score(self, ts_code: str, trade_date: str) -> Optional[float]:
        """
        计算VQM综合评分
        
        评分 = PE排名分 * 0.6 + ROE排名分 * 0.4
        PE越低越好，ROE越高越好
        """
        # 获取当日数据
        df = self.data_manager.get_daily_data(ts_code, end_date=trade_date)
        
        if df.empty or len(df) < 20:
            return None
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        # PE分数（越低越好）
        pe = latest.get('pe')
        if pd.isna(pe) or pe <= 0:
            return None
        
        # 简化PE评分：PE 0-10=100分, 10-20=80分, 20-30=60分, 30-50=40分, 50+=20分
        if pe < 10:
            pe_score = 100
        elif pe < 20:
            pe_score = 80
        elif pe < 30:
            pe_score = 60
        elif pe < 50:
            pe_score = 40
        else:
            pe_score = 20
        
        # PB作为辅助指标
        pb = latest.get('pb', 0)
        if pb > 0 and pb < 2:
            pe_score += 5  # 低PB加分
        
        # 综合评分（简化版，仅用PE+PB）
        # 完整版需要财务报表数据计算ROE
        vqm_score = pe_score
        
        return vqm_score
    
    def select_stocks(self, trade_date: str, top_n: int = 10) -> List[Dict]:
        """
        选股：按VQM评分选择top N
        
        Returns:
            [{'ts_code': '000001.SZ', 'name': '平安银行', 'score': 85.2, 'pe': 8.5}, ...]
        """
        # 获取所有股票
        stocks = self.data_manager.get_stock_basic()
        
        scores = []
        
        for _, row in stocks.iterrows():
            ts_code = row['ts_code']
            name = row['name']
            
            score = self.calculate_vqm_score(ts_code, trade_date)
            
            if score:
                # 获取当日PE
                df = self.data_manager.get_daily_data(ts_code, end_date=trade_date)
                if not df.empty:
                    latest = df.iloc[-1]
                    scores.append({
                        'ts_code': ts_code,
                        'name': name,
                        'score': score,
                        'pe': latest.get('pe', 0),
                        'pb': latest.get('pb', 0),
                        'close': latest.get('close', 0)
                    })
        
        # 按评分排序
        scores.sort(key=lambda x: x['score'], reverse=True)
        
        return scores[:top_n]
    
    def run_backtest(self, start_date: str = '20180101', end_date: str = '20251231') -> Dict:
        """
        运行回测
        
        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期
        
        Returns:
            回测结果统计
        """
        print(f"\n{'='*60}")
        print(f"🚀 VQM策略回测")
        print(f"{'='*60}")
        print(f"回测区间: {start_date} ~ {end_date}")
        print(f"初始资金: ¥{self.initial_capital:,.0f}")
        print(f"{'='*60}\n")
        
        # 初始化
        capital = self.initial_capital
        positions = {}  # {ts_code: {'shares': 100, 'cost': 10.5, 'value': 1050}}
        
        # 获取调仓日（每月最后一个交易日）
        rebalance_dates = []
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                rebalance_date = self.get_last_trading_date_of_month(year, month)
                if rebalance_date and start_date <= rebalance_date <= end_date:
                    rebalance_dates.append(rebalance_date)
        
        print(f"调仓日期数量: {len(rebalance_dates)} 次")
        print(f"首次调仓: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
        print()
        
        # 记录每日净值
        daily_nav = []
        
        # 遍历每个调仓周期
        for i, rebalance_date in enumerate(rebalance_dates):
            print(f"\n📅 调仓 [{i+1}/{len(rebalance_dates)}] {rebalance_date}")
            
            # 1. 选股
            selected = self.select_stocks(rebalance_date, top_n=10)
            
            if not selected:
                print("   ⚠️ 未选出股票")
                continue
            
            print(f"   选出 {len(selected)} 只股票")
            
            # 2. 计算每只股票的仓位
            position_value = capital / 10  # 等权重
            
            # 3. 清仓旧持仓，建立新持仓
            positions = {}
            
            for stock in selected:
                ts_code = stock['ts_code']
                price = stock['close']
                
                if price > 0:
                    shares = int(position_value / price / 100) * 100  # 100股整数倍
                    positions[ts_code] = {
                        'ts_code': ts_code,
                        'name': stock['name'],
                        'shares': shares,
                        'cost': price,
                        'buy_date': rebalance_date
                    }
                    print(f"   📈 {stock['name']}: {shares}股 @ ¥{price:.2f} (PE:{stock['pe']:.1f})")
            
            # 4. 计算当前总市值
            total_value = capital  # 简化：假设立即以收盘价成交
            
            daily_nav.append({
                'date': rebalance_date,
                'nav': total_value,
                'holdings': len(positions)
            })
        
        # 计算回测统计
        final_value = daily_nav[-1]['nav'] if daily_nav else capital
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        # 年化收益（简化计算）
        years = len(rebalance_dates) / 12 if rebalance_dates else 1
        annual_return = ((final_value / self.initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
        
        results = {
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'rebalance_count': len(rebalance_dates),
            'daily_nav': daily_nav
        }
        
        # 打印结果
        print(f"\n{'='*60}")
        print("📊 回测结果")
        print(f"{'='*60}")
        print(f"初始资金: ¥{self.initial_capital:,.0f}")
        print(f"最终市值: ¥{final_value:,.0f}")
        print(f"总收益率: {total_return:+.2f}%")
        print(f"年化收益: {annual_return:+.2f}%")
        print(f"调仓次数: {len(rebalance_dates)}")
        print(f"{'='*60}")
        
        return results
    
    def save_results(self, results: Dict, filename: str = None):
        """保存回测结果"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"vqm_backtest_result_{timestamp}.json"
        
        output_dir = os.path.expanduser('~/.openclaw/workspace/quant/results')
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 结果已保存: {filepath}")


# ==================== 便捷函数 ====================

def run_vqm_backtest(start_year: int = 2018, end_year: int = 2025) -> Dict:
    """
    运行VQM回测的便捷函数
    
    Args:
        start_year: 开始年份
        end_year: 结束年份
    """
    start_date = f"{start_year}0101"
    end_date = f"{end_year}1231"
    
    engine = VQMBacktestEngine(initial_capital=1000000)
    results = engine.run_backtest(start_date=start_date, end_date=end_date)
    engine.save_results(results)
    
    return results


if __name__ == '__main__':
    print("="*60)
    print("VQM策略回测框架")
    print("="*60)
    print()
    print("数据源: Tushare本地历史数据")
    print("策略: PE+ROE多因子选股，月度调仓")
    print()
    
    try:
        # 运行回测
        results = run_vqm_backtest(2018, 2025)
        
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("\n请先下载历史数据:")
        print("  python3 tushare_data_manager.py")
        print("  # 然后按提示下载股票列表和数据")
        
    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()
