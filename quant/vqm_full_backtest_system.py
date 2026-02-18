#!/usr/bin/env python3
"""
VQM策略完整回测系统
功能：
1. 数据采集：每日股票数据+宏观数据保存到本地
2. 回测执行：每月第一个交易日建仓，逐步优化
3. 整点汇报：自动汇报进度
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import time
import sqlite3
from typing import Dict, List, Optional

class VQMBacktestSystem:
    """VQM完整回测系统"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.data_dir = config.get('data_dir', 'data/backtest')
        self.db_path = os.path.join(self.data_dir, 'vqm_backtest.db')
        
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 初始化数据库
        self.init_database()
        
        print("="*70)
        print("🚀 VQM完整回测系统")
        print("="*70)
        print(f"数据目录: {self.data_dir}")
        print(f"数据库: {self.db_path}")
        print("="*70)
    
    def init_database(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 股票日度数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_daily (
                date TEXT,
                code TEXT,
                name TEXT,
                close REAL,
                open REAL,
                high REAL,
                low REAL,
                volume REAL,
                pe REAL,
                pb REAL,
                market_cap REAL,
                PRIMARY KEY (date, code)
            )
        ''')
        
        # 宏观数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS macro_data (
                date TEXT PRIMARY KEY,
                cpi_yoy REAL,
                ppi_yoy REAL,
                pmi REAL,
                m2_yoy REAL,
                lpr_1y REAL,
                lpr_5y REAL,
                sh_index REAL,
                sz_index REAL
            )
        ''')
        
        # 回测结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT,
                entry_date TEXT,
                exit_date TEXT,
                initial_capital REAL,
                final_value REAL,
                total_return REAL,
                annual_return REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                stocks_selected TEXT,
                trades TEXT,
                params TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ 数据库初始化完成")
    
    def get_stock_pool(self, top_n: int = 1000) -> List[str]:
        """获取股票池（沪深300+中证500+其他）"""
        print(f"\n📊 获取股票池（前{top_n}只）...")
        
        stock_pool = set()
        
        # 沪深300
        try:
            df = ak.index_stock_cons_csindex(symbol="000300")
            stock_pool.update(df['成分券代码'].tolist())
            print(f"  沪深300: {len(df)}只")
        except:
            pass
        
        # 中证500
        try:
            df = ak.index_stock_cons_csindex(symbol="000905")
            stock_pool.update(df['成分券代码'].tolist())
            print(f"  中证500: {len(df)}只")
        except:
            pass
        
        # 中证1000
        try:
            df = ak.index_stock_cons_csindex(symbol="000852")
            stock_pool.update(df['成分券代码'].tolist())
            print(f"  中证1000: {len(df)}只")
        except:
            pass
        
        # 如果不够1000只，补充其他大盘股
        if len(stock_pool) < top_n:
            try:
                all_stocks = ak.stock_zh_a_spot_em()
                all_codes = all_stocks['代码'].tolist()
                # 补充到1000只
                for code in all_codes:
                    if len(stock_pool) >= top_n:
                        break
                    stock_pool.add(code)
            except:
                pass
        
        result = list(stock_pool)[:top_n]
        print(f"✅ 股票池总计: {len(result)}只")
        return result
    
    def download_daily_data(self, start_date: str, end_date: str):
        """下载日度股票数据"""
        print(f"\n📥 下载股票数据: {start_date} ~ {end_date}")
        
        stock_pool = self.get_stock_pool(1000)
        
        conn = sqlite3.connect(self.db_path)
        
        total = len(stock_pool)
        success = 0
        
        for i, code in enumerate(stock_pool):
            try:
                # 获取历史数据
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', ''),
                    adjust="qfq"
                )
                
                if df is None or len(df) == 0:
                    continue
                
                # 重命名列
                df = df.rename(columns={
                    '日期': 'date',
                    '收盘': 'close',
                    '开盘': 'open',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume'
                })
                
                df['code'] = code
                df['name'] = code  # 简化
                df['pe'] = None  # 稍后补充
                df['pb'] = None
                df['market_cap'] = None
                
                # 保存到数据库
                df[['date', 'code', 'name', 'close', 'open', 'high', 'low', 
                    'volume', 'pe', 'pb', 'market_cap']].to_sql(
                    'stock_daily', conn, if_exists='append', index=False
                )
                
                success += 1
                
                if (i + 1) % 100 == 0:
                    print(f"  进度: {i+1}/{total}, 成功: {success}")
                
                time.sleep(0.05)  # 避免请求过快
                
            except Exception as e:
                if (i + 1) % 100 == 0:
                    print(f"  进度: {i+1}/{total}, 失败: {e}")
                continue
        
        conn.close()
        print(f"✅ 数据下载完成: 成功{success}/{total}只")
    
    def download_macro_data(self, start_date: str, end_date: str):
        """下载宏观数据"""
        print(f"\n📥 下载宏观数据...")
        
        # 这里简化处理，实际需要获取CPI、PPI等数据
        print("  ⚠️ 宏观数据获取简化处理，实际需要调用对应API")
        
    def run_monthly_backtest(self, year: int, month: int) -> Dict:
        """运行单月回测"""
        print(f"\n{'='*70}")
        print(f"📅 {year}年{month}月回测")
        print(f"{'='*70}")
        
        # 获取该月第一个交易日
        first_day = datetime(year, month, 1)
        entry_date = first_day.strftime('%Y-%m-%d')
        
        # 从数据库读取数据
        conn = sqlite3.connect(self.db_path)
        
        # 获取该日期的股票数据
        query = """
            SELECT code, close, pe FROM stock_daily 
            WHERE date = ? AND pe > 0 AND pe < 100
        """
        df = pd.read_sql_query(query, conn, params=(entry_date,))
        
        conn.close()
        
        if len(df) == 0:
            print(f"  ⚠️ {entry_date} 无数据")
            return {'status': 'no_data'}
        
        print(f"  当日有效股票: {len(df)}只")
        
        # VQM选股
        df['pe_rank'] = df['pe'].rank(pct=True, ascending=True)
        df['roe_rank'] = 0.5  # 简化
        df['vqm_score'] = df['pe_rank'] * 0.6 + df['roe_rank'] * 0.4
        
        top10 = df.nlargest(10, 'vqm_score')
        
        print(f"  选中股票:")
        for _, row in top10.iterrows():
            print(f"    {row['code']}: PE={row['pe']:.1f}, 得分={row['vqm_score']:.3f}")
        
        # 简化回测：假设持有1个月
        result = {
            'year': year,
            'month': month,
            'entry_date': entry_date,
            'stocks_selected': top10['code'].tolist(),
            'avg_pe': top10['pe'].mean(),
            'status': 'success'
        }
        
        return result
    
    def run_full_backtest(self, start_year: int, end_year: int):
        """运行完整回测"""
        print(f"\n{'='*70}")
        print(f"🚀 开始完整回测: {start_year}~{end_year}")
        print(f"{'='*70}")
        
        all_results = []
        
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                result = self.run_monthly_backtest(year, month)
                all_results.append(result)
                
                # 保存结果
                self.save_result(result)
                
                # 整点汇报
                now = datetime.now()
                if now.minute == 0:
                    self.report_progress(all_results)
        
        return all_results
    
    def save_result(self, result: Dict):
        """保存回测结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO backtest_results 
            (start_date, entry_date, stocks_selected, params)
            VALUES (?, ?, ?, ?)
        ''', (
            result.get('entry_date', ''),
            result.get('entry_date', ''),
            json.dumps(result.get('stocks_selected', [])),
            json.dumps({'pe_weight': 0.6, 'roe_weight': 0.4})
        ))
        
        conn.commit()
        conn.close()
    
    def report_progress(self, results: List[Dict]):
        """汇报进度"""
        success_count = sum(1 for r in results if r.get('status') == 'success')
        total_count = len(results)
        
        print(f"\n{'='*70}")
        print(f"📊 进度汇报 [{datetime.now().strftime('%H:%M')}]")
        print(f"{'='*70}")
        print(f"  已完成: {success_count}/{total_count}")
        print(f"  成功率: {success_count/total_count*100:.1f}%")
        print(f"{'='*70}")


def main():
    """主函数"""
    config = {
        'data_dir': 'data/backtest',
        'initial_capital': 1000000,
        'pe_weight': 0.6,
        'roe_weight': 0.4,
    }
    
    system = VQMBacktestSystem(config)
    
    # 第一步：下载数据（只需要执行一次）
    print("\n" + "="*70)
    print("📥 第一阶段：数据下载")
    print("="*70)
    
    system.download_daily_data('2018-01-01', '2024-12-31')
    system.download_macro_data('2018-01-01', '2024-12-31')
    
    # 第二步：运行回测
    print("\n" + "="*70)
    print("🚀 第二阶段：运行回测")
    print("="*70)
    
    results = system.run_full_backtest(2018, 2024)
    
    # 生成报告
    print("\n" + "="*70)
    print("📊 回测完成")
    print("="*70)
    print(f"总计回测次数: {len(results)}")
    

if __name__ == '__main__':
    main()
