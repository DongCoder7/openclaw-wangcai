#!/usr/bin/env python3
"""
历史数据下载器 - 使用eFinance获取A股数据
获取2018-2025年1000只股票每日收盘数据

数据源: efinance (国产金融数据库)
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict
import sqlite3
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class HistoricalDataDownloader:
    """
    历史数据下载器 - eFinance版本
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.expanduser('~/.openclaw/workspace/data/historical/historical.db')
        
        self.db_path = db_path
        self.data_dir = os.path.dirname(db_path)
        os.makedirs(self.data_dir, exist_ok=True)
        
        self._init_database()
        
        print(f"📁 数据目录: {self.data_dir}")
        print(f"🗄️  数据库: {self.db_path}")
    
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 股票基础信息
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_basic (
                ts_code TEXT PRIMARY KEY,
                code TEXT,
                name TEXT,
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
                change_pct REAL,
                PRIMARY KEY (ts_code, trade_date)
            )
        ''')
        
        # 下载进度
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_progress (
                ts_code TEXT PRIMARY KEY,
                records INTEGER,
                start_date TEXT,
                end_date TEXT,
                status TEXT,
                updated_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ 数据库初始化完成")
    
    def get_stock_list(self, max_stocks: int = 1000) -> pd.DataFrame:
        """获取股票列表"""
        import efinance as ef
        
        print("📊 获取股票列表...")
        
        # 获取沪深A股全部股票
        try:
            df = ef.stock.get_code_list()
            print(f"   获取到 {len(df)} 只股票")
        except Exception as e:
            print(f"   获取失败: {e}")
            return pd.DataFrame()
        
        # 过滤上海和深圳股票
        df = df[df['代码'].str.startswith(('6', '0'))]
        
        # 随机选择
        if len(df) > max_stocks:
            df = df.sample(n=max_stocks, random_state=42)
        
        # 转换格式
        df['ts_code'] = df['代码'].apply(
            lambda x: f"{x}.SH" if x.startswith('6') else f"{x}.SZ"
        )
        
        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        df.to_sql('stock_basic', conn, if_exists='replace', index=False)
        conn.close()
        
        print(f"✅ 股票列表: {len(df)} 只")
        return df
    
    def download_stock_data(self, code: str, start_date: str = '2018-01-01', 
                          end_date: str = None) -> bool:
        """下载单只股票历史数据"""
        import efinance as ef
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # 获取历史数据
            df = ef.stock.get_quote_history(code)
            
            if df is None or df.empty:
                return False
            
            # 过滤日期范围
            df['日期'] = pd.to_datetime(df['日期'])
            df = df[(df['日期'] >= start_date) & (df['日期'] <= end_date)]
            
            if df.empty:
                return False
            
            # 转换格式
            ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
            df['ts_code'] = ts_code
            df['trade_date'] = df['日期'].dt.strftime('%Y%m%d')
            
            # 选择需要的列
            df = df[['ts_code', 'trade_date', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '涨跌幅']]
            df = df.rename(columns={
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '涨跌幅': 'change_pct'
            })
            
            # 保存到数据库
            conn = sqlite3.connect(self.db_path)
            df.to_sql('daily_price', conn, if_exists='append', index=False)
            
            # 更新进度
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO download_progress 
                (ts_code, records, start_date, end_date, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ts_code, 
                len(df), 
                df['trade_date'].min(), 
                df['trade_date'].max(),
                'completed', 
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            return False
    
    def batch_download(self, max_stocks: int = 1000, start_date: str = '2018-01-01',
                     end_date: str = None, delay: float = 0.5) -> Dict:
        """批量下载"""
        # 获取股票列表
        stock_list = self.get_stock_list(max_stocks)
        
        if stock_list.empty:
            return {}
        
        total = len(stock_list)
        success = 0
        failed = 0
        
        print(f"\n🚀 开始下载历史数据")
        print(f"   股票数量: {total}")
        print(f"   日期范围: {start_date} ~ {end_date or '今天'}")
        print()
        
        for i, row in stock_list.iterrows():
            code = row['代码']
            name = row['名称']
            
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
        """获取统计信息"""
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
    print("📥 历史数据下载器 (eFinance版)")
    print("   数据范围: 2018-2025")
    print("   目标数量: 1000只股票")
    print("="*60)
    print()
    
    downloader = HistoricalDataDownloader()
    
    # 显示当前状态
    stats = downloader.get_stats()
    print("\n📊 当前状态:")
    print(f"   股票数量: {stats['stock_count']}")
    print(f"   日度记录: {stats['price_records']:,}")
    print(f"   日期范围: {stats['date_range'][0] or 'N/A'} ~ {stats['date_range'][1] or 'N/A'}")
    print(f"   数据库大小: {stats['db_size_mb']:.1f} MB")
    print()
    
    # 开始下载
    print("开始下载...")
    print("="*60)
    
    # 下载1000只股票
    downloader.batch_download(
        max_stocks=1000,
        start_date='2018-01-01',
        end_date=None,
        delay=0.5
    )
    
    # 最终状态
    print("\n📊 最终状态:")
    final = downloader.get_stats()
    print(f"   股票数量: {final['stock_count']}")
    print(f"   日度记录: {final['price_records']:,}")
    print(f"   日期范围: {final['date_range'][0]} ~ {final['date_range'][1]}")
    print(f"   数据库大小: {final['db_size_mb']:.1f} MB")


if __name__ == '__main__':
    main()
