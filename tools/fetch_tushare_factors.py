#!/usr/bin/env python3
"""
Tushare Pro 因子补充采集脚本
采集TOP 20高价值因子补充到数据库

优先级因子：
1. PE_TTM, PB - 估值
2. ROA, ROIC - 质量
3. Debt_to_Assets - 杠杆
4. OCF_to_Revenue - 现金流
5. Revenue_Growth_QoQ, Profit_Growth_QoQ - 成长
6. Turnover_Rate - 情绪
7. PEG, PS_TTM - 估值
8. Gross_Margin, AR_Turn, Inv_Turn - 质量/效率
9. Current_Ratio, Interest_Coverage - 质量/杠杆
10. RSI_14, MACD - 技术
11. Northbound_Hold - 情绪
12. FCF_Yield - 现金流
"""

import sys
import os
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import tushare as ts

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace')

# 配置
WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
BATCH_SIZE = 100  # 每批处理股票数

class TushareFactorFetcher:
    """Tushare Pro 因子获取器"""
    
    def __init__(self):
        self.pro = self._init_tushare()
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        
    def _init_tushare(self):
        """初始化Tushare Pro API"""
        token = ''
        env_file = f'{WORKSPACE}/.tushare.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if 'TUSHARE_TOKEN' in line and '=' in line:
                        token = line.split('=', 1)[1].strip().strip('"').strip("'")
        
        if not token:
            raise ValueError("未找到Tushare Token，请配置.tushare.env")
        
        return ts.pro_api(token)
    
    def get_stock_list(self, limit: int = None) -> List[str]:
        """获取股票列表"""
        query = """
        SELECT DISTINCT ts_code FROM stock_basic 
        WHERE ts_code NOT LIKE '8%' AND ts_code NOT LIKE '4%' 
        AND ts_code NOT LIKE '68%' AND ts_code NOT LIKE '30%'
        """
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql(query, self.conn)
        return df['ts_code'].tolist()
    
    def fetch_valuation_factors(self, trade_date: str) -> pd.DataFrame:
        """
        获取估值因子
        - PE_TTM, PB, PS_TTM, PEG
        """
        try:
            # 使用daily_basic接口获取估值指标
            df = self.pro.daily_basic(trade_date=trade_date)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 选择估值相关字段
            valuation_cols = ['ts_code', 'trade_date', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 
                            'dv_ratio', 'total_mv', 'circ_mv']
            
            # 过滤存在的列
            cols = [c for c in valuation_cols if c in df.columns]
            df = df[cols].copy()
            
            # 计算PEG (PE_TTM / 净利润增长率)
            # 需要结合财务数据，这里先预留
            
            return df
            
        except Exception as e:
            print(f"❌ 获取估值因子失败: {e}")
            return pd.DataFrame()
    
    def fetch_financial_factors(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取财务质量因子
        - ROA, ROIC, Gross_Margin, Current_Ratio, Interest_Coverage
        - OCF_to_Revenue, AR_Turn, Inv_Turn
        - Revenue_Growth_QoQ, Profit_Growth_QoQ
        """
        try:
            # 获取财务指标
            df = self.pro.fina_indicator(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 关键财务字段
            key_cols = ['ts_code', 'end_date', 'ann_date',
                       'roa', 'roa_yearly', 'roic',
                       'grossprofit_margin', 'netprofit_margin',
                       'current_ratio', 'quick_ratio', 'cash_ratio',
                       'ar_turn', 'inv_turn', 'ca_turn', 'fa_turn', 'assets_turn',
                       'debt_to_assets', 'debt_to_eqt',
                       'ocf_to_revenue', 'ocf_to_profit',
                       'q_sales_yoy', 'q_profit_yoy', 'q_op_yoy',
                       'roe', 'roe_waa', 'roe_dt', 'roe_yearly',
                       'eps', 'dt_eps', 'bps']
            
            # 过滤存在的列
            cols = [c for c in key_cols if c in df.columns]
            df = df[cols].copy()
            
            # 计算Interest_Coverage (利息保障倍数) = EBIT / 利息费用
            # 如果字段不存在，使用近似值
            if 'int_cover' not in df.columns and 'profit_to_gr' in df.columns:
                # 简化计算
                pass
            
            return df
            
        except Exception as e:
            print(f"❌ 获取财务因子失败 {ts_code}: {e}")
            return pd.DataFrame()
    
    def fetch_technical_factors(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        计算技术指标因子
        - RSI_14, MACD
        """
        try:
            # 获取日线数据
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty or len(df) < 30:
                return pd.DataFrame()
            
            df = df.sort_values('trade_date')
            
            # 计算RSI_14
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi_14'] = 100 - (100 / (1 + rs))
            
            # 计算MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp1 - exp2
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
            # 计算ATR (平均真实波幅)
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift())
            df['tr3'] = abs(df['low'] - df['close'].shift())
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            df['atr_14'] = df['tr'].rolling(window=14).mean()
            
            return df[['ts_code', 'trade_date', 'close', 'rsi_14', 'macd', 'macd_signal', 'macd_hist', 'atr_14']]
            
        except Exception as e:
            print(f"❌ 计算技术指标失败 {ts_code}: {e}")
            return pd.DataFrame()
    
    def fetch_northbound_hold(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取北向资金持股
        """
        try:
            # 将股票代码转换为HK格式
            if ts_code.endswith('.SH'):
                hk_code = ts_code.replace('.SH', '.SH')
            else:
                hk_code = ts_code.replace('.SZ', '.SZ')
            
            # 获取港股通持股
            df = self.pro.hk_hold(ts_code=hk_code, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            return df[['ts_code', 'trade_date', 'vol', 'ratio']].rename(columns={
                'vol': 'northbound_vol',
                'ratio': 'northbound_ratio'
            })
            
        except Exception as e:
            print(f"❌ 获取北向资金失败 {ts_code}: {e}")
            return pd.DataFrame()
    
    def fetch_turnover_rate(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取换手率
        """
        try:
            df = self.pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            cols = ['ts_code', 'trade_date', 'turnover_rate', 'turnover_rate_f']
            cols = [c for c in cols if c in df.columns]
            return df[cols].copy()
            
        except Exception as e:
            print(f"❌ 获取换手率失败 {ts_code}: {e}")
            return pd.DataFrame()
    
    def save_to_database(self, df: pd.DataFrame, table_name: str, if_exists: str = 'append'):
        """保存数据到数据库"""
        if df is None or df.empty:
            return 0
        
        try:
            df.to_sql(table_name, self.conn, if_exists=if_exists, index=False)
            return len(df)
        except Exception as e:
            print(f"❌ 保存到数据库失败: {e}")
            return 0
    
    def create_tables(self):
        """创建因子存储表"""
        
        # 估值因子表
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_valuation_factors (
            ts_code TEXT,
            trade_date TEXT,
            pe REAL,
            pe_ttm REAL,
            pb REAL,
            ps REAL,
            ps_ttm REAL,
            dv_ratio REAL,
            total_mv REAL,
            circ_mv REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, trade_date)
        )
        """)
        
        # 技术指标表
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_technical_factors (
            ts_code TEXT,
            trade_date TEXT,
            close REAL,
            rsi_14 REAL,
            macd REAL,
            macd_signal REAL,
            macd_hist REAL,
            atr_14 REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, trade_date)
        )
        """)
        
        # 北向资金表
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_northbound (
            ts_code TEXT,
            trade_date TEXT,
            northbound_vol REAL,
            northbound_ratio REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, trade_date)
        )
        """)
        
        # 换手率表
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_turnover (
            ts_code TEXT,
            trade_date TEXT,
            turnover_rate REAL,
            turnover_rate_f REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, trade_date)
        )
        """)
        
        self.conn.commit()
        print("✅ 数据库表创建完成")
    
    def batch_fetch_valuation(self, trade_date: str):
        """批量获取估值因子（市场级别）"""
        print(f"📊 获取 {trade_date} 估值因子...")
        
        df = self.fetch_valuation_factors(trade_date)
        if not df.empty:
            df['update_time'] = datetime.now().isoformat()
            count = self.save_to_database(df, 'stock_valuation_factors')
            print(f"   ✅ 保存 {count} 条估值因子")
            return count
        return 0
    
    def batch_fetch_technical(self, ts_codes: List[str], start_date: str, end_date: str):
        """批量获取技术指标"""
        print(f"📊 获取 {len(ts_codes)} 只股票技术指标...")
        
        total = 0
        for i, ts_code in enumerate(ts_codes, 1):
            if i % 50 == 0:
                print(f"   进度: {i}/{len(ts_codes)}")
            
            df = self.fetch_technical_factors(ts_code, start_date, end_date)
            if not df.empty:
                df['update_time'] = datetime.now().isoformat()
                count = self.save_to_database(df, 'stock_technical_factors')
                total += count
        
        print(f"   ✅ 共保存 {total} 条技术指标")
        return total
    
    def batch_fetch_financial(self, ts_codes: List[str], start_date: str, end_date: str):
        """批量获取财务因子"""
        print(f"📊 获取 {len(ts_codes)} 只股票财务因子...")
        
        total = 0
        for i, ts_code in enumerate(ts_codes, 1):
            if i % 50 == 0:
                print(f"   进度: {i}/{len(ts_codes)}")
            
            df = self.fetch_financial_factors(ts_code, start_date, end_date)
            if not df.empty:
                # 重命名列以匹配现有表
                df = df.rename(columns={'end_date': 'trade_date'})
                df['update_time'] = datetime.now().isoformat()
                count = self.save_to_database(df, 'stock_fina_tushare')
                total += count
        
        print(f"   ✅ 共保存 {total} 条财务因子")
        return total
    
    def run_daily_update(self, trade_date: str = None):
        """
        每日更新入口
        """
        if trade_date is None:
            trade_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        
        print(f"\n{'='*60}")
        print(f"🚀 Tushare因子每日更新 - {trade_date}")
        print(f"{'='*60}\n")
        
        # 创建表
        self.create_tables()
        
        # 1. 获取市场级别估值因子
        self.batch_fetch_valuation(trade_date)
        
        # 2. 获取股票列表
        stock_list = self.get_stock_list()
        print(f"\n📋 共 {len(stock_list)} 只股票需要更新\n")
        
        # 3. 获取技术指标
        start_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=60)).strftime('%Y%m%d')
        self.batch_fetch_technical(stock_list[:500], start_date, trade_date)  # 先更新500只
        
        # 4. 获取换手率
        print(f"\n📊 获取换手率...")
        for i, ts_code in enumerate(stock_list[:200], 1):
            if i % 50 == 0:
                print(f"   进度: {i}/200")
            df = self.fetch_turnover_rate(ts_code, trade_date, trade_date)
            if not df.empty:
                df['update_time'] = datetime.now().isoformat()
                self.save_to_database(df, 'stock_turnover')
        
        print(f"\n{'='*60}")
        print("✅ 每日更新完成")
        print(f"{'='*60}\n")
    
    def run_full_update(self, start_date: str, end_date: str):
        """
        全量更新（历史数据回补）
        """
        print(f"\n{'='*60}")
        print(f"🚀 Tushare因子全量更新")
        print(f"   时间范围: {start_date} 至 {end_date}")
        print(f"{'='*60}\n")
        
        self.create_tables()
        
        # 获取股票列表
        stock_list = self.get_stock_list()
        print(f"📋 共 {len(stock_list)} 只股票\n")
        
        # 分批获取财务因子
        batch_size = 100
        for i in range(0, len(stock_list), batch_size):
            batch = stock_list[i:i+batch_size]
            print(f"\n批次 {i//batch_size + 1}/{(len(stock_list)+batch_size-1)//batch_size}")
            self.batch_fetch_financial(batch, start_date, end_date)
        
        print(f"\n{'='*60}")
        print("✅ 全量更新完成")
        print(f"{'='*60}\n")
    
    def close(self):
        """关闭连接"""
        self.conn.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Tushare Pro 因子采集')
    parser.add_argument('--mode', choices=['daily', 'full'], default='daily',
                       help='更新模式: daily(每日) 或 full(全量)')
    parser.add_argument('--date', type=str, help='指定日期 (YYYYMMDD)，默认昨日')
    parser.add_argument('--start', type=str, help='全量更新开始日期')
    parser.add_argument('--end', type=str, help='全量更新结束日期')
    
    args = parser.parse_args()
    
    fetcher = TushareFactorFetcher()
    
    try:
        if args.mode == 'daily':
            fetcher.run_daily_update(args.date)
        else:
            if not args.start or not args.end:
                print("❌ 全量更新需要指定 --start 和 --end")
                return
            fetcher.run_full_update(args.start, args.end)
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
