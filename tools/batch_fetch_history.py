#!/usr/bin/env python3
"""
批量补充历史数据 (2018-2024)
使用多数据源获取缺失的历史数据
"""
import sqlite3
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
from typing import List, Optional
import sys

sys.path.insert(0, '/root/.openclaw/workspace/skills/historical-data-fetcher')
from sources.local_source import LocalSource

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


class HistoricalDataFetcher:
    """历史数据获取器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
    
    def get_all_stock_codes(self) -> List[str]:
        """获取所有股票代码"""
        # 从已有数据中获取完整股票列表
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT ts_code FROM stock_factors ORDER BY ts_code")
        codes = [row[0] for row in cursor.fetchall()]
        return codes
    
    def get_stock_codes_from_tencent(self) -> List[str]:
        """从腾讯API获取股票列表"""
        try:
            # 获取A股列表
            url = "http://qt.gtimg.cn/q=sh000001"
            response = requests.get(url, timeout=10)
            
            # 简化：使用本地已知的股票代码列表
            # 实际应该从交易所获取完整列表
            return []
        except:
            return []
    
    def fetch_tencent_history(self, code: str, days: int = 240) -> Optional[pd.DataFrame]:
        """
        从腾讯API获取历史数据
        
        Args:
            code: 股票代码 (如 000001.SZ)
            days: 获取天数
        """
        try:
            # 转换代码格式
            if code.endswith('.SZ'):
                tencent_code = 'sz' + code[:-3]
            elif code.endswith('.SH'):
                tencent_code = 'sh' + code[:-3]
            elif code.endswith('.BJ'):
                tencent_code = 'bj' + code[:-3]
            else:
                return None
            
            # 腾讯API获取历史数据
            url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tencent_code},day,,,{days},qfq"
            response = requests.get(url, timeout=30)
            data = response.json()
            
            # 解析数据
            key = tencent_code
            if key not in data.get('data', {}):
                return None
            
            stock_data = data['data'][key]
            if 'qfqday' not in stock_data and 'day' not in stock_data:
                return None
            
            # 使用前复权数据
            kline_data = stock_data.get('qfqday', stock_data.get('day', []))
            
            if not kline_data:
                return None
            
            # 转换为DataFrame
            df = pd.DataFrame(kline_data, columns=['date', 'open', 'close', 'low', 'high', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            
            # 转换类型
            for col in ['open', 'close', 'low', 'high']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            
            df['ts_code'] = code
            
            return df
            
        except Exception as e:
            return None
    
    def calculate_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """从价格数据计算因子"""
        if df is None or len(df) < 20:
            return None
        
        df = df.sort_values('date')
        
        # 计算收益率
        df['ret_1'] = df['close'].pct_change()
        df['ret_5'] = df['close'].pct_change(5)
        df['ret_20'] = df['close'].pct_change(20)
        df['ret_60'] = df['close'].pct_change(60)
        df['ret_120'] = df['close'].pct_change(120)
        
        # 计算波动率
        df['vol_20'] = df['ret_1'].rolling(20).std()
        
        # 计算均线
        df['ma_20'] = df['close'].rolling(20).mean()
        df['ma_60'] = df['close'].rolling(60).mean()
        
        # 计算价格位置
        df['price_pos_20'] = (df['close'] - df['close'].rolling(20).min()) / (df['close'].rolling(20).max() - df['close'].rolling(20).min())
        df['price_pos_60'] = (df['close'] - df['close'].rolling(60).min()) / (df['close'].rolling(60).max() - df['close'].rolling(60).min())
        df['price_pos_high'] = (df['close'] - df['close'].rolling(120).max()) / df['close'].rolling(120).max()
        
        # 量比
        df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['vol_ratio_amt'] = df['vol_ratio']  # 简化
        
        # 资金流向 (简化)
        df['money_flow'] = np.where(df['close'] > df['open'], df['volume'], -df['volume'])
        
        # 相对强度
        df['rel_strength'] = (df['close'] / df['ma_20']) - 1
        
        # 动量加速
        df['mom_accel'] = df['ret_20'] - df['ret_60'] / 3
        
        # 收益动量
        df['profit_mom'] = df['ret_20']
        
        # 格式化日期
        df['trade_date'] = df['date'].dt.strftime('%Y%m%d')
        
        return df
    
    def save_to_database(self, df: pd.DataFrame):
        """保存到数据库"""
        if df is None or df.empty:
            return 0
        
        # 选择需要的列
        factor_cols = [
            'ts_code', 'trade_date',
            'ret_20', 'ret_60', 'ret_120',
            'vol_20', 'vol_ratio', 'ma_20', 'ma_60',
            'price_pos_20', 'price_pos_60', 'price_pos_high',
            'vol_ratio_amt', 'money_flow', 'rel_strength', 'mom_accel', 'profit_mom'
        ]
        
        available_cols = [c for c in factor_cols if c in df.columns]
        df_to_save = df[available_cols].copy()
        
        # 去除NaN
        df_to_save = df_to_save.dropna(subset=['ret_20'])
        
        if df_to_save.empty:
            return 0
        
        # 保存
        cursor = self.conn.cursor()
        
        inserted = 0
        for _, row in df_to_save.iterrows():
            try:
                placeholders = ','.join(['?' for _ in available_cols])
                query = f"INSERT OR REPLACE INTO stock_factors ({','.join(available_cols)}) VALUES ({placeholders})"
                cursor.execute(query, tuple(row.values))
                inserted += 1
            except Exception as e:
                continue
        
        self.conn.commit()
        return inserted
    
    def batch_fetch_history(self, start_year: int = 2018, end_year: int = 2024, 
                           max_stocks: int = None):
        """
        批量获取历史数据
        
        Args:
            start_year: 开始年份
            end_year: 结束年份
            max_stocks: 最大股票数（测试用）
        """
        print("="*70)
        print(f"批量获取历史数据: {start_year}-{end_year}")
        print("="*70)
        
        # 获取股票列表
        codes = self.get_all_stock_codes()
        
        if not codes:
            print("❌ 无法获取股票列表")
            return
        
        print(f"股票总数: {len(codes)}")
        
        if max_stocks:
            codes = codes[:max_stocks]
            print(f"测试模式: 限制 {max_stocks} 只股票")
        
        # 计算需要获取的天数
        days = (end_year - start_year + 1) * 250  # 每年约250个交易日
        
        success_count = 0
        fail_count = 0
        total_inserted = 0
        
        for i, code in enumerate(codes, 1):
            if i % 100 == 0:
                print(f"\n进度: {i}/{len(codes)} ({i/len(codes)*100:.1f}%)")
                print(f"  成功: {success_count}, 失败: {fail_count}, 已插入: {total_inserted} 条")
            
            # 获取历史数据
            df = self.fetch_tencent_history(code, days=days)
            
            if df is None or df.empty:
                fail_count += 1
                continue
            
            # 计算因子
            df = self.calculate_factors(df)
            
            if df is None or df.empty:
                fail_count += 1
                continue
            
            # 过滤年份
            df = df[(df['trade_date'] >= f'{start_year}0101') & 
                    (df['trade_date'] <= f'{end_year}1231')]
            
            if df.empty:
                fail_count += 1
                continue
            
            # 保存
            inserted = self.save_to_database(df)
            total_inserted += inserted
            success_count += 1
            
            # 限速
            time.sleep(0.1)
        
        print(f"\n{'='*70}")
        print("批量获取完成")
        print(f"成功: {success_count}, 失败: {fail_count}")
        print(f"总插入记录: {total_inserted}")
        print(f"{'='*70}")
    
    def check_data_coverage(self, year: int) -> dict:
        """检查某年的数据覆盖情况"""
        cursor = self.conn.cursor()
        
        query = f"""
        SELECT 
            COUNT(DISTINCT trade_date) as days,
            COUNT(DISTINCT ts_code) as stocks,
            MIN(trade_date) as min_date,
            MAX(trade_date) as max_date
        FROM stock_factors
        WHERE trade_date BETWEEN '{year}0101' AND '{year}1231'
        """
        
        cursor.execute(query)
        row = cursor.fetchone()
        
        return {
            'year': year,
            'trading_days': row[0],
            'stock_count': row[1],
            'date_range': f"{row[2]} ~ {row[3]}" if row[2] else "无数据"
        }
    
    def close(self):
        """关闭连接"""
        self.conn.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='批量获取历史数据')
    parser.add_argument('--start', type=int, default=2018, help='开始年份')
    parser.add_argument('--end', type=int, default=2024, help='结束年份')
    parser.add_argument('--check', action='store_true', help='检查数据覆盖')
    parser.add_argument('--fetch', action='store_true', help='获取数据')
    parser.add_argument('--limit', type=int, help='限制股票数（测试用）')
    
    args = parser.parse_args()
    
    fetcher = HistoricalDataFetcher()
    
    if args.check:
        print("数据覆盖检查:")
        for year in range(args.start, args.end + 1):
            coverage = fetcher.check_data_coverage(year)
            print(f"  {coverage['year']}: {coverage['trading_days']} 交易日, "
                  f"{coverage['stock_count']} 只股票")
    
    if args.fetch:
        fetcher.batch_fetch_history(args.start, args.end, args.limit)
    
    if not args.check and not args.fetch:
        print("使用方法:")
        print("  python3 batch_fetch_history.py --check --start 2018 --end 2024")
        print("  python3 batch_fetch_history.py --fetch --start 2018 --end 2024 --limit 100")
    
    fetcher.close()


if __name__ == '__main__':
    main()
