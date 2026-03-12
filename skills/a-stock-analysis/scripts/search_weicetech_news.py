#!/root/.openclaw/workspace/venv/bin/python3
# -*- coding: utf-8 -*-
"""
伟测科技 - 补充行业调研和最新财报数据
"""

import requests
import json
import datetime
import os
import sys

sys.path.insert(0, '/root/.openclaw/workspace/skills/a-stock-analysis/scripts')
from longport.openapi import Config, QuoteContext

def search_exa_news():
    """Exa全网搜索 - 伟测科技相关新闻"""
    print("=" * 70)
    print("【P1】Exa全网搜索 - 伟测科技/半导体测试行业")
    print("=" * 70)
    
    # 使用Exa MCP搜索（通过mcporter）
    search_queries = [
        "伟测科技 订单 产能 2025",
        "伟测科技 财报 业绩 增长",
        "半导体测试行业 国产替代",
        "AI芯片测试 需求 增长",
        "第三方芯片测试 市场份额"
    ]
    
    print("搜索关键词:")
    for q in search_queries:
        print(f"  • {q}")
    
    # 尝试调用mcporter
    try:
        # 由于无法直接调用mcporter，记录需要搜索的内容
        print("\n⚠️ Exa搜索结果需要通过外部搜索补充")
        print("建议搜索方向:")
        print("  1. 伟测科技最新订单公告")
        print("  2. 2024年报/2025一季报业绩预告")
        print("  3. AI芯片测试需求行业报告")
        print("  4. 半导体测试设备国产化进展")
    except Exception as e:
        print(f"搜索失败: {e}")
    
    return []

def search_sina_finance():
    """新浪财经搜索"""
    print("\n" + "=" * 70)
    print("【P2】新浪财经 - 伟测科技相关新闻")
    print("=" * 70)
    
    try:
        # 新浪财经API
        keywords = ["伟测科技", "688372"]
        
        for kw in keywords:
            # 新浪财经新闻搜索
            url = f"https://search.api.sina.com.cn/?c=news&q={kw}&page=1&num=5"
            print(f"\n搜索: {kw}")
            print(f"API: {url}")
            
        # 新浪个股新闻
        stock_news_url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=10"
        print(f"\n个股新闻源: {stock_news_url}")
        
    except Exception as e:
        print(f"新浪搜索失败: {e}")

def get_zsxq_insights():
    """知识星球调研纪要"""
    print("\n" + "=" * 70)
    print("【P3】知识星球 - 产业链调研")
    print("=" * 70)
    
    # 检查是否有知识星球数据
    zsxq_path = "/root/.openclaw/workspace/data/zsxq"
    if os.path.exists(zsxq_path):
        files = os.listdir(zsxq_path)
        print(f"知识星球数据目录: {zsxq_path}")
        print(f"可用文件: {files}")
    else:
        print("⚠️ 知识星球数据目录不存在")
        print("建议手动搜索关键词: 伟测科技、半导体测试、芯片测试")

def get_tushare_reports():
    """Tushare券商研报"""
    print("\n" + "=" * 70)
    print("【P4】券商研报 - Tushare")
    print("=" * 70)
    
    try:
        import tushare as ts
        ts.set_token("b837ac9e44a49e5818f0d34ca33ed7fa05a049c1d16f4f5335ed7c2")
        pro = ts.pro_api()
        
        # 获取研报
        df = pro.report_rc(ts_code='688372.SH')
        if not df.empty:
            print(f"找到 {len(df)} 条研报记录")
            print("\n最新研报:")
            for i, row in df.head(5).iterrows():
                print(f"  {row.get('report_date', '')} {row.get('org_name', '')}: {row.get('title', '')[:40]}...")
        else:
            print("未找到研报数据")
    except Exception as e:
        print(f"研报获取失败: {e}")

def get_eastmoney_detail():
    """东方财富详细财务数据"""
    print("\n" + "=" * 70)
    print("【财报数据】东方财富 - 伟测科技详细财务")
    print("=" * 70)
    
    try:
        # 东方财富主要财务指标API
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        
        params = {
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "pageSize": "10",
            "pageNumber": "1",
            "reportName": "RPT_FCI_PERFORMANCEE",
            "columns": "ALL",
            "filter": "(SECURITY_CODE=\"688372\")"
        }
        
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        if data.get('result') and data['result'].get('data'):
            items = data['result']['data']
            
            print("\n最新财务数据:")
            print("-" * 70)
            
            for item in items[:5]:
                date = item.get('REPORT_DATE', '')[:10]
                revenue = item.get('TOTAL_OPERATE_INCOME', 0)
                profit = item.get('NETPROFIT', 0)
                profit_dedt = item.get('DEDUCT_NETPROFIT', 0)
                eps = item.get('BASIC_EPS', 0)
                roe = item.get('ROE', 0)
                gross_margin = item.get('GROSSPROFIT_MARGIN', 0)
                
                print(f"\n报告期: {date}")
                print(f"  营业收入: {revenue/1e8:.2f}亿元" if revenue else "  营业收入: -")
                print(f"  净利润: {profit/1e8:.2f}亿元" if profit else "  净利润: -")
                print(f"  扣非净利润: {profit_dedt/1e8:.2f}亿元" if profit_dedt else "  扣非净利润: -")
                print(f"  基本EPS: {eps:.4f}元" if eps else "  基本EPS: -")
                print(f"  ROE: {roe:.2f}%" if roe else "  ROE: -")
                print(f"  毛利率: {gross_margin:.2f}%" if gross_margin else "  毛利率: -")
                
    except Exception as e:
        print(f"东财数据获取失败: {e}")

def get_10jqka_data():
    """同花顺财务数据"""
    print("\n" + "=" * 70)
    print("【财报数据】同花顺 - 伟测科技")
    print("=" * 70)
    
    try:
        # 同花顺财务数据API
        url = "http://basic.10jqka.com.cn/api/stockph/finance/688372"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"同花顺API状态: {resp.status_code}")
        
    except Exception as e:
        print(f"同花顺获取失败: {e}")

def search_comprehensive():
    """综合搜索汇总"""
    print("\n" + "=" * 70)
    print("行业调研信息汇总")
    print("=" * 70)
    
    # 执行所有搜索
    search_exa_news()
    search_sina_finance()
    get_zsxq_insights()
    get_tushare_reports()
    get_eastmoney_detail()
    get_10jqka_data()
    
    print("\n" + "=" * 70)
    print("搜索完成 - 待补充信息")
    print("=" * 70)
    print("""
由于部分API限制，以下信息建议通过其他渠道补充：

【高优先级】
1. 伟测科技2024年年报（预计2025年3-4月发布）
2. 最新机构调研纪要（知识星球/券商）
3. AI芯片测试行业订单情况

【中优先级】
4. 半导体测试设备国产化进展
5. 竞争对手（利扬芯片、华岭股份）动态
6. 下游客户（芯片设计公司）扩产计划

【搜索关键词建议】
• "伟测科技 年报 2024"
• "伟测科技 订单 产能"
• "半导体测试 国产替代"
• "AI芯片测试 需求"
• "第三方测试 市场规模"
    """)

if __name__ == "__main__":
    search_comprehensive()
