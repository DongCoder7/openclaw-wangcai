#!/root/.openclaw/workspace/venv/bin/python3
"""
Tushare历史数据本地化模块
下载2018-2025年各行业1000只股票的日度数据
用于策略回测

环境变量:
    TUSHARE_TOKEN: Tushare API Token
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

# 添加tools目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TushareDataManager:
    """
    Tushare数据管理器
    负责历史数据的下载、存储和管理
    """
    
    def __init__(self, db_path: str = None, token: str = None):
        """
        初始化
        
        Args:
            db_path: 数据库路径，默认 ~/.openclaw/workspace/data/tushare/historical.db
            token: Tushare token，默认从环境变量读取
        """
        if db_path is None:
            db_path = os.path.expanduser('~/.openclaw/workspace/data/tushare/historical.db')
        
        self.db_path = db_path
        self.data_dir = os.path.dirname(db_path)
        
        # 创建目录
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Tushare Token
        self.token = token or os.getenv('TUSHARE_TOKEN')
        if not self.token:
            # 尝试从配置文件读取
            self.token = self._load_token_from_config()
        
        self.pro = None
        if self.token:
            self._init_tushare()
        
        # 初始化数据库
        self._init_database()
        
        print(f"📁 数据目录: {self.data_dir}")
        print(f"🗄️  数据库: {self.db_path}")
    
    def _load_token_from_config(self) -> Optional[str]:
        """从配置文件读取token"""
        config_paths = [
            os.path.expanduser('~/.openclaw/workspace/.tushare.env'),
            os.path.expanduser('~/.tushare.env'),
            '.tushare.env',
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('TUSHARE_TOKEN='):
                            return line.split('=', 1)[1].strip().strip('"\'')
        return None
    
    def _init_tushare(self):
        """初始化Tushare Pro API"""
        try:
            import tushare as ts
            self.pro = ts.pro_api(self.token)
            print("✅ Tushare API 初始化成功")
        except ImportError:
            print("❌ 未安装tushare，请执行: pip install tushare")
            raise
        except Exception as e:
            print(f"❌ Tushare初始化失败: {e}")
            raise
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 股票基础信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_basic (
                ts_code TEXT PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                industry TEXT,
                industry_code TEXT,
                sector TEXT,
                list_date TEXT,
                is_hs TEXT,
                list_status TEXT
            )
        ''')
        
        # 日度行情数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_price (
                ts_code TEXT,
                trade_date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                pre_close REAL,
                change REAL,
                pct_chg REAL,
                vol REAL,
                amount REAL,
                PRIMARY KEY (ts_code, trade_date)
            )
        ''')
        
        # 每日指标数据表（PE/PB等）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_basic (
                ts_code TEXT,
                trade_date TEXT,
                close REAL,
                turnover_rate REAL,
                turnover_rate_f REAL,
                volume_ratio REAL,
                pe REAL,
                pe_ttm REAL,
                pb REAL,
                ps REAL,
                ps_ttm REAL,
                dv_ratio REAL,
                dv_ttm REAL,
                total_share REAL,
                float_share REAL,
                free_share REAL,
                total_mv REAL,
                circ_mv REAL,
                PRIMARY KEY (ts_code, trade_date)
            )
        ''')
        
        # 下载进度表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_progress (
                ts_code TEXT PRIMARY KEY,
                last_date TEXT,
                status TEXT,
                updated_at TEXT
            )
        ''')
        
        # 行业分类表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS industry_classification (
                code TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                weight REAL DEFAULT 1.0
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ 数据库表初始化完成")
    
    def get_stock_list(self, sectors: List[str] = None, max_per_sector: int = 100) -> pd.DataFrame:
        """
        获取股票列表，按行业均衡选择
        
        Args:
            sectors: 指定行业列表，None表示全部
            max_per_sector: 每行业最多选择股票数
        
        Returns:
            DataFrame with columns: ts_code, symbol, name, industry, sector
        """
        if self.pro is None:
            raise ValueError("Tushare未初始化")
        
        print("📊 获取股票列表...")
        
        # 获取基础信息
        df = self.pro.stock_basic(exchange='', list_status='L', 
                                   fields='ts_code,symbol,name,industry,list_date')
        
        # 过滤2018年前上市的股票
        df = df[df['list_date'] < '20180101']
        
        # 行业映射（简化版）
        industry_to_sector = {
            '银行': '金融', '证券': '金融', '保险': '金融', '多元金融': '金融',
            '房地产开发': '地产', '房地产服务': '地产',
            '白酒': '消费', '饮料制造': '消费', '食品加工': '消费', '医药商业': '消费',
            '化学制药': '医药', '中药': '医药', '生物制品': '医药', '医疗器械': '医药',
            '半导体': '科技', '电子': '科技', '计算机应用': '科技', '通信设备': '科技',
            '汽车整车': '制造', '汽车零部件': '制造', '专用设备': '制造', '通用设备': '制造',
            '电力': '能源', '煤炭开采': '能源', '石油开采': '能源', '新能源': '能源',
            '化工': '周期', '钢铁': '周期', '有色金属': '周期', '建材': '周期',
        }
        
        df['sector'] = df['industry'].map(industry_to_sector).fillna('其他')
        
        # 按行业选择
        if sectors:
            df = df[df['sector'].isin(sectors)]
        
        # 每行业限制数量
        selected = []
        for sector in df['sector'].unique():
            sector_df = df[df['sector'] == sector]
            if len(sector_df) > max_per_sector:
                # 按市值排序选择（需要额外获取市值数据，这里随机选择）
                sector_df = sector_df.sample(n=max_per_sector, random_state=42)
            selected.append(sector_df)
        
        result = pd.concat(selected, ignore_index=True)
        
        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        result.to_sql('stock_basic', conn, if_exists='replace', index=False)
        conn.close()
        
        print(f"✅ 获取股票列表: {len(result)} 只")
        print(f"   行业分布:")
        for sector, count in result['sector'].value_counts().items():
            print(f"     {sector}: {count} 只")
        
        return result
    
    def download_daily_data(self, ts_code: str, start_date: str = '20180101', 
                           end_date: str = None) -> bool:
        """
        下载单只股票的日度数据
        
        Args:
            ts_code: Tushare股票代码 (如 '000001.SZ')
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)，默认今天
        
        Returns:
            bool: 是否成功
        """
        if self.pro is None:
            return False
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        
        try:
            # 获取行情数据
            df_price = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if df_price is None or df_price.empty:
                return False
            
            # 获取指标数据
            df_basic = self.pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            # 保存到数据库
            conn = sqlite3.connect(self.db_path)
            
            # 保存价格数据
            df_price.to_sql('daily_price', conn, if_exists='append', index=False)
            
            # 保存指标数据
            if df_basic is not None and not df_basic.empty:
                df_basic.to_sql('daily_basic', conn, if_exists='append', index=False)
            
            # 更新进度
            last_date = df_price['trade_date'].max()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO download_progress (ts_code, last_date, status, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (ts_code, last_date, 'completed', datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"   ⚠️ 下载 {ts_code} 失败: {e}")
            return False
    
    def batch_download(self, stock_list: pd.DataFrame = None, 
                       start_date: str = '20180101',
                       end_date: str = None,
                       delay: float = 0.5) -> Dict:
        """
        批量下载股票数据
        
        Args:
            stock_list: 股票列表DataFrame，None则从数据库读取
            start_date: 开始日期
            end_date: 结束日期
            delay: 请求间隔（秒），避免频率限制
        
        Returns:
            统计信息
        """
        if stock_list is None:
            conn = sqlite3.connect(self.db_path)
            stock_list = pd.read_sql('SELECT * FROM stock_basic', conn)
            conn.close()
        
        if stock_list is None or stock_list.empty:
            print("❌ 无股票列表，请先执行 get_stock_list()")
            return {}
        
        total = len(stock_list)
        success = 0
        failed = 0
        
        print(f"\n🚀 开始批量下载: {total} 只股票")
        print(f"   日期范围: {start_date} - {end_date or '今天'}")
        print()
        
        for i, row in stock_list.iterrows():
            ts_code = row['ts_code']
            name = row['name']
            
            print(f"[{i+1}/{total}] 下载 {ts_code} {name}...", end=' ')
            
            if self.download_daily_data(ts_code, start_date, end_date):
                print("✅")
                success += 1
            else:
                print("❌")
                failed += 1
            
            # 限速
            time.sleep(delay)
            
            # 每50只保存进度
            if (i + 1) % 50 == 0:
                print(f"\n   📊 进度: {i+1}/{total} (成功:{success}, 失败:{failed})\n")
        
        stats = {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': success / total * 100 if total > 0 else 0
        }
        
        print(f"\n{'='*60}")
        print("下载完成!")
        print(f"   总计: {total}")
        print(f"   成功: {success}")
        print(f"   失败: {failed}")
        print(f"   成功率: {stats['success_rate']:.1f}%")
        print(f"{'='*60}")
        
        return stats
    
    def get_daily_data(self, ts_code: str, start_date: str = None, 
                       end_date: str = None) -> pd.DataFrame:
        """
        从本地数据库读取日度数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
        
        Returns:
            DataFrame with price and basic data
        """
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT p.*, b.pe, b.pb, b.total_mv, b.circ_mv
            FROM daily_price p
            LEFT JOIN daily_basic b ON p.ts_code = b.ts_code AND p.trade_date = b.trade_date
            WHERE p.ts_code = ?
        '''
        params = [ts_code]
        
        if start_date:
            query += ' AND p.trade_date >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND p.trade_date <= ?'
            params.append(end_date)
        
        query += ' ORDER BY p.trade_date'
        
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        
        if not df.empty:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        return df
    
    def get_stock_basic(self, sector: str = None) -> pd.DataFrame:
        """获取股票基础信息"""
        conn = sqlite3.connect(self.db_path)
        
        query = 'SELECT * FROM stock_basic'
        if sector:
            query += f" WHERE sector = '{sector}'"
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
    
    def get_download_stats(self) -> Dict:
        """获取下载统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 股票数量
        cursor.execute('SELECT COUNT(*) FROM stock_basic')
        stock_count = cursor.fetchone()[0]
        
        # 日度数据量
        cursor.execute('SELECT COUNT(*) FROM daily_price')
        price_count = cursor.fetchone()[0]
        
        # 日期范围
        cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM daily_price')
        date_range = cursor.fetchone()
        
        # 完成下载的股票数
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


# ==================== 便捷函数 ====================

def init_tushare_manager(token: str = None) -> TushareDataManager:
    """获取Tushare数据管理器实例"""
    return TushareDataManager(token=token)


def download_historical_data(target_count: int = 1000, 
                              start_date: str = '20180101',
                              end_date: str = None):
    """
    下载历史数据的便捷函数
    
    Args:
        target_count: 目标股票数量
        start_date: 开始日期
        end_date: 结束日期
    """
    manager = TushareDataManager()
    
    # 计算每行业数量
    sectors = ['金融', '地产', '消费', '医药', '科技', '制造', '能源', '周期', '其他']
    per_sector = target_count // len(sectors)
    
    # 获取股票列表
    stock_list = manager.get_stock_list(sectors=sectors, max_per_sector=per_sector)
    
    # 限制总数
    if len(stock_list) > target_count:
        stock_list = stock_list.sample(n=target_count, random_state=42)
    
    # 批量下载
    stats = manager.batch_download(stock_list, start_date=start_date, end_date=end_date)
    
    return stats


# ==================== 测试 ====================

if __name__ == '__main__':
    print("="*60)
    print("Tushare历史数据管理器")
    print("="*60)
    
    # 检查token
    token = os.getenv('TUSHARE_TOKEN')
    if not token:
        print("\n⚠️ 请设置 TUSHARE_TOKEN 环境变量")
        print("   export TUSHARE_TOKEN='your_token_here'")
        print("   或在 ~/.openclaw/workspace/.tushare.env 中配置")
        print()
    
    try:
        manager = TushareDataManager()
        
        # 显示当前统计
        stats = manager.get_download_stats()
        print("\n📊 当前数据状态:")
        print(f"   股票数量: {stats['stock_count']}")
        print(f"   日度记录: {stats['price_records']:,}")
        print(f"   完成下载: {stats['completed_stocks']} 只")
        print(f"   日期范围: {stats['date_range'][0]} ~ {stats['date_range'][1]}")
        print(f"   数据库大小: {stats['db_size_mb']:.1f} MB")
        
        print("\n使用示例:")
        print("  1. 下载股票列表: manager.get_stock_list()")
        print("  2. 批量下载: manager.batch_download()")
        print("  3. 读取数据: manager.get_daily_data('000001.SZ')")
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
