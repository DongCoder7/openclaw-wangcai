#!/root/.openclaw/workspace/venv/bin/python3
"""
历史数据本地化下载器
优先级：腾讯API → AKShare（免费，无需Token）
用于2018-2025年历史数据下载

使用：
    python3 historical_data_downloader.py
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sqlite3
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class HistoricalDataDownloader:
    """
    历史数据下载器
    优先级：腾讯 → AKShare
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.expanduser('~/.openclaw/workspace/data/historical/historical.db')
        
        self.db_path = db_path
        self.data_dir = os.path.dirname(db_path)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
        print(f"📁 数据目录: {self.data_dir}")
        print(f"🗄️  数据库: {self.db_path}")
    
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 股票基础信息
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_basic (
                ts_code TEXT PRIMARY KEY,
                code TEXT,
                name TEXT,
                industry TEXT,
                sector TEXT,
                list_date TEXT
            )
        ''')
        
        # 日度行情数据
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_price (
                ts_code TEXT,
                trade_date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                PRIMARY KEY (ts_code, trade_date)
            )
        ''')
        
        # 下载进度
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_progress (
                ts_code TEXT PRIMARY KEY,
                records INTEGER,
                date_range TEXT,
                status TEXT,
                updated_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ 数据库初始化完成")
    
    def get_stock_list(self, max_stocks: int = 1000) -> pd.DataFrame:
        """
        获取股票列表
        
        Args:
            max_stocks: 最大股票数量
        """
        from data_utils import StockDataProvider
        
        provider = StockDataProvider()
        
        # 获取全市场股票
        print("📊 获取股票列表...")
        df = provider.get_stock_list('all')
        
        if df.empty:
            print("❌ 无法获取股票列表")
            return pd.DataFrame()
        
        # 简化：随机选择
        if len(df) > max_stocks:
            df = df.sample(n=max_stocks, random_state=42)
        
        # 转换格式
        df['ts_code'] = df['code'].apply(
            lambda x: f"{x}.SZ" if not x.startswith('6') else f"{x}.SH"
        )
        df['sector'] = '综合'  # 简化处理
        
        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        df.to_sql('stock_basic', conn, if_exists='replace', index=False)
        conn.close()
        
        print(f"✅ 获取股票列表: {len(df)} 只")
        
        return df[['code', 'name', 'ts_code', 'sector']]
    
    def download_stock_data(self, code: str, start_date: str = '20180101', 
                          end_date: str = None) -> bool:
        """
        下载单只股票历史数据
        
        Args:
            code: 股票代码 (如 '600519' 或 '000001')
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
        
        Returns:
            bool: 是否成功
        """
        from data_utils import StockDataProvider
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        
        provider = StockDataProvider()
        
        try:
            # 获取日线数据（腾讯API → AKShare）
            df = provider.get_daily_data(code, 
                                         start_date=start_date.replace('-', ''), 
                                         end_date=end_date.replace('-', ''))
            
            if df is None or df.empty:
                return False
            
            # 转换格式
            ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
            df['ts_code'] = ts_code
            df['trade_date'] = df['date'].dt.strftime('%Y%m%d')
            df = df[['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
            # 保存到数据库
            conn = sqlite3.connect(self.db_path)
            df.to_sql('daily_price', conn, if_exists='append', index=False)
            
            # 更新进度
            cursor = conn.cursor()
            date_range = f"{df['trade_date'].min()}-{df['trade_date'].max()}"
            cursor.execute('''
                INSERT OR REPLACE INTO download_progress (ts_code, records, date_range, status, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (ts_code, len(df), date_range, 'completed', datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            return False
    
    def batch_download(self, max_stocks: int = 1000, start_date: str = '20180101',
                     end_date: str = None, delay: float = 0.3) -> Dict:
        """
        批量下载历史数据
        
        Args:
            max_stocks: 最大股票数量
            start_date: 开始日期
            end_date: 结束日期
            delay: 请求间隔（秒）
        
        Returns:
            下载统计
        """
        # 获取股票列表
        stock_list = self.get_stock_list(max_stocks)
        
        if stock_list.empty:
            print("❌ 无股票可下载")
            return {}
        
        total = len(stock_list)
        success = 0
        failed = 0
        
        print(f"\n🚀 开始下载历史数据")
        print(f"   股票数量: {total}")
        print(f"   日期范围: {start_date} ~ {end_date or '今天'}")
        print()
        
        for i, row in stock_list.iterrows():
            code = row['code']
            name = row['name']
            
            print(f"[{i+1}/{total}] {code} {name}...", end=' ')
            
            if self.download_stock_data(code, start_date, end_date):
                print(f"✅")
                success += 1
            else:
                print(f"❌")
                failed += 1
            
            time.sleep(delay)
            
            # 每50只报告进度
            if (i + 1) % 50 == 0:
                print(f"\n   📊 进度: {i+1}/{total} (成功:{success}, 失败:{failed})\n")
        
        stats = {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': success / total * 100 if total > 0 else 0
        }
        
        print(f"\n{'='*60}")
        print("📥 下载完成!")
        print(f"   总计: {total}")
        print(f"   成功: {success}")
        print(f"   失败: {failed}")
        print(f"   成功率: {stats['success_rate']:.1f}%")
        print(f"{'='*60}")
        
        return stats
    
    def get_stats(self) -> Dict:
        """获取数据统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM stock_basic')
        stock_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM daily_price')
        price_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM daily_price')
        date_range = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM download_progress WHERE status = 'completed'")
        completed = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'stock_count': stock_count,
            'price_records': price_count,
            'date_range': date_range,
            'completed_stocks': completed,
            'db_size_mb': os.path.getsize(self.db_path) / 1024 / 1024
        }


def main():
    """主函数"""
    print("="*60)
    print("📥 历史数据本地化下载器")
    print("   优先级: 腾讯API → AKShare")
    print("="*60)
    print()
    
    downloader = HistoricalDataDownloader()
    
    # 显示当前状态
    stats = downloader.get_stats()
    print("\n📊 当前状态:")
    print(f"   股票数量: {stats['stock_count']}")
    print(f"   日度记录: {stats['price_records']:,}")
    print(f"   完成下载: {stats['completed_stocks']} 只")
    print(f"   日期范围: {stats['date_range'][0] or 'N/A'} ~ {stats['date_range'][1] or 'N/A'}")
    print(f"   数据库大小: {stats['db_size_mb']:.1f} MB")
    print()
    
    # 询问是否开始下载
    print("开始下载历史数据 (2018-2025)...")
    print("="*60)
    
    # 下载1000只股票
    stats = downloader.batch_download(
        max_stocks=1000,
        start_date='20180101',
        end_date=None,
        delay=0.3
    )
    
    # 最终状态
    print("\n📊 最终状态:")
    final_stats = downloader.get_stats()
    print(f"   股票数量: {final_stats['stock_count']}")
    print(f"   日度记录: {final_stats['price_records']:,}")
    print(f"   数据库大小: {final_stats['db_size_mb']:.1f} MB")


if __name__ == '__main__':
    main()
