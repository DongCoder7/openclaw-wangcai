#!/usr/bin/env python3
"""
板块跟踪与轮动分析脚本
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

# T0级板块核心标的
T0_SECTORS = {
    "AI算力": ["300308", "300394", "300502", "601138"],  # 中际旭创、天孚通信、新易盛、工业富联
    "算力租赁": ["300442", "300738", "002837"],  # 润泽科技、奥飞数据、英维克
    "半导体设备": ["002371", "688012", "688072"],  # 北方华创、中微公司、拓荆科技
    "储能": ["300274", "300750", "300014"],  # 阳光电源、宁德时代、亿纬锂能
    "高股息": ["600900", "601088", "601398"]  # 长江电力、中国神华、工商银行
}

# T1级板块核心标的
T1_SECTORS = {
    "人形机器人": ["688017", "002050", "601689"],  # 绿的谐波、三花智控、拓普集团
    "自动驾驶": ["002920", "603596", "002906"],  # 德赛西威、伯特利、华阳集团
    "低空经济": ["002085", "NASDAQ:EH", "001696"],  # 万丰奥威、亿航智能、宗申动力
    "卫星互联网": ["600118", "600879", "002465"],  # 中国卫星、航天电子、海格通信
    "创新药": ["688235", "01801.HK", "688506"]  # 百济神州、信达生物、百利天恒
}

def fetch_sector_performance(sector_name: str, stock_codes: list) -> dict:
    """
    获取板块表现
    
    Args:
        sector_name: 板块名称
        stock_codes: 板块内股票代码列表
    
    Returns:
        dict: 板块平均涨跌幅、成交额等
    """
    try:
        df = ak.stock_zh_a_spot_em()
        
        sector_stocks = df[df['代码'].isin(stock_codes)]
        
        if sector_stocks.empty:
            return {"error": "未找到板块股票数据"}
        
        avg_change = sector_stocks['涨跌幅'].mean()
        total_volume = sector_stocks['成交额'].sum() / 1e8  # 亿元
        
        # 领涨股
        leader = sector_stocks.loc[sector_stocks['涨跌幅'].idxmax()]
        
        return {
            "sector": sector_name,
            "avg_change": round(avg_change, 2),
            "total_volume": round(total_volume, 2),
            "leader_name": leader['名称'],
            "leader_change": round(leader['涨跌幅'], 2),
            "stock_count": len(sector_stocks)
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_northbound_flow() -> dict:
    """
    获取北向资金流向
    
    Returns:
        dict: 北向资金净流入情况
    """
    try:
        df = ak.stock_hsgt_hist_em(symbol="HK")
        
        if df.empty:
            return {"error": "北向数据不存在"}
        
        latest = df.iloc[0]
        
        return {
            "date": latest['日期'],
            "net_inflow": float(latest['当日资金流入']),  # 亿元
            "cumulative": float(latest['累计资金流入']),  # 亿元
            "buy_amount": float(latest['当日买入成交额']),  # 亿元
            "sell_amount": float(latest['当日卖出成交额'])  # 亿元
        }
    except Exception as e:
        return {"error": str(e)}

def calculate_sector_score(sector_data: dict) -> int:
    """
    计算板块景气度评分（简化版）
    
    Args:
        sector_data: 板块数据
    
    Returns:
        int: 1-5分
    """
    score = 3  # 基准分
    
    # 涨跌幅评分
    if sector_data.get('avg_change', 0) > 3:
        score += 1
    elif sector_data.get('avg_change', 0) > 5:
        score += 2
    elif sector_data.get('avg_change', 0) < -2:
        score -= 1
    elif sector_data.get('avg_change', 0) < -4:
        score -= 2
    
    # 成交额评分
    if sector_data.get('total_volume', 0) > 100:
        score += 1
    
    return max(1, min(5, score))

def generate_sector_report() -> str:
    """
    生成板块监控报告
    
    Returns:
        str: 报告文本
    """
    report = []
    report.append("=" * 60)
    report.append("A股板块监控报告")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("=" * 60)
    
    # T0板块
    report.append("\n【T0级板块 - 核心持仓】")
    for sector_name, codes in T0_SECTORS.items():
        data = fetch_sector_performance(sector_name, codes)
        if "error" not in data:
            score = calculate_sector_score(data)
            report.append(f"\n{sector_name}:")
            report.append(f"  平均涨幅: {data['avg_change']}%")
            report.append(f"  成交额: {data['total_volume']}亿")
            report.append(f"  领涨: {data['leader_name']} (+{data['leader_change']}%)")
            report.append(f"  景气度: {'🟢' * score}{'⚪' * (5-score)}")
    
    # 北向资金
    northbound = fetch_northbound_flow()
    if "error" not in northbound:
        report.append("\n【北向资金】")
        report.append(f"  当日净流入: {northbound['net_inflow']}亿")
        report.append(f"  累计净流入: {northbound['cumulative']}亿")
    
    return "\n".join(report)

def main():
    """测试函数"""
    report = generate_sector_report()
    print(report)

if __name__ == "__main__":
    main()
