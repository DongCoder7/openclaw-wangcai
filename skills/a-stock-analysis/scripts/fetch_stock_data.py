#!/usr/bin/env python3
"""
A股个股数据获取脚本
整合实时行情、财务数据、历史数据获取
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

def fetch_stock_basic_info(stock_code: str) -> dict:
    """
    获取股票基本信息
    
    Args:
        stock_code: 股票代码，如 "000001"
    
    Returns:
        dict: 包含股票名称、行业、市值等信息
    """
    try:
        # 使用akshare获取实时行情
        df = ak.stock_zh_a_spot_em()
        stock_info = df[df['代码'] == stock_code]
        
        if stock_info.empty:
            return {"error": "股票代码不存在"}
        
        return {
            "code": stock_code,
            "name": stock_info['名称'].values[0],
            "price": float(stock_info['最新价'].values[0]),
            "change_pct": float(stock_info['涨跌幅'].values[0]),
            "pe": float(stock_info['市盈率-动态'].values[0]),
            "pb": float(stock_info['市净率'].values[0]),
            "market_cap": float(stock_info['总市值'].values[0]) / 1e8,  # 转换为亿元
            "turnover": float(stock_info['换手率'].values[0]),
            "volume": float(stock_info['成交量'].values[0]) / 1e4  # 转换为万手
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_stock_daily(stock_code: str, days: int = 252) -> pd.DataFrame:
    """
    获取股票历史日线数据
    
    Args:
        stock_code: 股票代码
        days: 获取天数，默认252个交易日（约1年）
    
    Returns:
        pd.DataFrame: 包含开高低收量等数据
    """
    try:
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )
        
        return df.tail(days)
    except Exception as e:
        print(f"获取历史数据失败: {e}")
        return pd.DataFrame()

def fetch_financial_data(stock_code: str) -> dict:
    """
    获取财务指标数据
    
    Args:
        stock_code: 股票代码
    
    Returns:
        dict: 包含ROE、毛利率等关键财务指标
    """
    try:
        # 获取主要财务指标
        df = ak.stock_financial_analysis_indicator(symbol=stock_code)
        
        if df.empty:
            return {"error": "财务数据不存在"}
        
        latest = df.iloc[0]
        
        return {
            "roe": float(latest.get('净资产收益率', 0)),
            "gross_margin": float(latest.get('销售毛利率', 0)),
            "net_margin": float(latest.get('销售净利率', 0)),
            "debt_ratio": float(latest.get('资产负债率', 0)),
            "eps": float(latest.get('基本每股收益', 0)),
            "revenue_growth": float(latest.get('营业收入增长率', 0)),
            "profit_growth": float(latest.get('净利润增长率', 0))
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_balance_sheet(stock_code: str) -> dict:
    """
    获取资产负债表关键数据
    
    Args:
        stock_code: 股票代码
    
    Returns:
        dict: 资产负债关键指标
    """
    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=stock_code)
        
        if df.empty:
            return {"error": "资产负债表不存在"}
        
        latest = df.iloc[0]
        
        return {
            "total_assets": float(latest.get('资产总计', 0)) / 1e8,
            "total_liabilities": float(latest.get('负债合计', 0)) / 1e8,
            "equity": float(latest.get('所有者权益合计', 0)) / 1e8,
            "cash": float(latest.get('货币资金', 0)) / 1e8,
            "receivables": float(latest.get('应收账款', 0)) / 1e8,
            "inventory": float(latest.get('存货', 0)) / 1e8
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    """测试函数"""
    stock_code = "000001"  # 平安银行
    
    print(f"正在获取 {stock_code} 的数据...")
    
    # 基本信息
    basic = fetch_stock_basic_info(stock_code)
    print("\n=== 基本信息 ===")
    print(basic)
    
    # 财务数据
    financial = fetch_financial_data(stock_code)
    print("\n=== 财务数据 ===")
    print(financial)
    
    # 资产负债表
    balance = fetch_balance_sheet(stock_code)
    print("\n=== 资产负债表 ===")
    print(balance)

if __name__ == "__main__":
    main()
