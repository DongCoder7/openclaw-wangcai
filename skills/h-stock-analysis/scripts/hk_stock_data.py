#!/usr/bin/env python3
"""
港股数据获取与分析脚本
包含AH比价、南向资金、做空比例等港股特色数据
"""

import akshare as ak
import pandas as pd
from datetime import datetime

def fetch_hk_stock_basic(stock_code: str) -> dict:
    """
    获取港股基本信息
    
    Args:
        stock_code: 港股代码，如 "00700"
    
    Returns:
        dict: 港股基本信息
    """
    try:
        # 使用akshare获取港股实时行情
        df = ak.stock_hk_ggt_components_em()
        
        # 港股通标的
        hk_spot = ak.stock_hk_spot_em()
        stock_info = hk_spot[hk_spot['代码'] == stock_code]
        
        if stock_info.empty:
            return {"error": "股票代码不存在或不在港股通"}
        
        return {
            "code": stock_code,
            "name": stock_info['名称'].values[0],
            "price_hkd": float(stock_info['最新价'].values[0]),
            "change_pct": float(stock_info['涨跌幅'].values[0]),
            "pe": float(stock_info['市盈率'].values[0]) if '市盈率' in stock_info.columns else None,
            "volume": float(stock_info['成交量'].values[0]) / 1e4  # 万股
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_ah_premium(a_code: str, h_code: str) -> dict:
    """
    计算AH溢价率
    
    Args:
        a_code: A股代码
        h_code: H股代码
    
    Returns:
        dict: AH溢价相关信息
    """
    try:
        # 获取A股价格
        a_spot = ak.stock_zh_a_spot_em()
        a_info = a_spot[a_spot['代码'] == a_code]
        a_price = float(a_info['最新价'].values[0]) if not a_info.empty else 0
        
        # 获取H股价格
        h_spot = ak.stock_hk_spot_em()
        h_info = h_spot[h_spot['代码'] == h_code]
        h_price_hkd = float(h_info['最新价'].values[0]) if not h_info.empty else 0
        
        # 获取汇率（简化处理，实际应获取实时汇率）
        # 人民币/港元汇率约0.92
        exchange_rate = 0.92
        
        # 计算AH溢价率
        if h_price_hkd > 0:
            ah_premium = (a_price / (h_price_hkd * exchange_rate) - 1) * 100
        else:
            ah_premium = 0
        
        return {
            "a_code": a_code,
            "h_code": h_code,
            "a_price": a_price,
            "h_price_hkd": h_price_hkd,
            "h_price_cny": round(h_price_hkd * exchange_rate, 2),
            "exchange_rate": exchange_rate,
            "ah_premium_pct": round(ah_premium, 2),
            "recommendation": "选H股" if ah_premium > 30 else ("选A股" if ah_premium < 15 else "综合考虑")
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_southbound_flow() -> dict:
    """
    获取南向资金流向
    
    Returns:
        dict: 南向资金流向数据
    """
    try:
        df = ak.stock_hsgt_hist_em(symbol="SH")
        
        if df.empty:
            return {"error": "南向数据不存在"}
        
        latest = df.iloc[0]
        
        return {
            "date": latest['日期'],
            "net_inflow": float(latest['当日资金流入']),  # 亿元
            "cumulative": float(latest['累计资金流入']),  # 亿元
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_southbound_holdings(stock_code: str) -> dict:
    """
    获取南向资金持股情况
    
    Args:
        stock_code: 港股代码
    
    Returns:
        dict: 南向资金持股比例
    """
    try:
        df = ak.stock_ggt_hold_em()
        stock_info = df[df['代码'] == stock_code]
        
        if stock_info.empty:
            return {"error": "无南向持股数据"}
        
        latest = stock_info.iloc[0]
        
        return {
            "code": stock_code,
            "name": latest['名称'],
            "hold_shares": float(latest['持股数量']),  # 万股
            "hold_ratio": float(latest['持股占比']),  # %
            "change_shares": float(latest['当日增持']),  # 万股
        }
    except Exception as e:
        return {"error": str(e)}

def generate_hk_report(stock_code: str) -> str:
    """
    生成港股分析报告
    
    Args:
        stock_code: 港股代码
    
    Returns:
        str: 报告文本
    """
    report = []
    report.append("=" * 60)
    report.append(f"港股分析报告 - {stock_code}")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("=" * 60)
    
    # 基本信息
    basic = fetch_hk_stock_basic(stock_code)
    if "error" not in basic:
        report.append(f"\n【基本信息】")
        report.append(f"  名称: {basic['name']}")
        report.append(f"  股价: HK${basic['price_hkd']}")
        report.append(f"  涨跌幅: {basic['change_pct']}%")
        if basic.get('pe'):
            report.append(f"  PE: {basic['pe']}")
    
    # 南向资金持股
    holdings = fetch_southbound_holdings(stock_code)
    if "error" not in holdings:
        report.append(f"\n【南向资金持股】")
        report.append(f"  持股比例: {holdings['hold_ratio']}%")
        report.append(f"  持股数量: {holdings['hold_shares']}万股")
        report.append(f"  当日变动: {holdings['change_shares']}万股")
    
    # 南向资金流向
    southbound = fetch_southbound_flow()
    if "error" not in southbound:
        report.append(f"\n【南向资金流向】")
        report.append(f"  当日净流入: {southbound['net_inflow']}亿港元")
    
    return "\n".join(report)

def main():
    """测试函数"""
    # 测试港股
    print(generate_hk_report("00700"))  # 腾讯
    
    print("\n" + "="*60 + "\n")
    
    # 测试AH比价
    ah_comparison = fetch_ah_premium("601398", "01398")  # 工商银行
    print("AH比价分析:")
    print(ah_comparison)

if __name__ == "__main__":
    main()
