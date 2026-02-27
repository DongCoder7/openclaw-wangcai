#!/usr/bin/env python3
"""
世运电路长桥API实时分析
"""
import os
import sys
sys.path.insert(0, '/root/.openclaw/workspace/tools')

# 设置环境变量
os.environ['LONGPORT_APP_KEY'] = '68f2e2a62a7911943bd05db4bd584b6c'
os.environ['LONGPORT_APP_SECRET'] = 'ede99d5e90a810122983f159f2bc947aa962a0844f13f6e540b90981937a26dd'
os.environ['LONGPORT_ACCESS_TOKEN'] = 'm_eyJhbGciOiJSUzI1NiIsImtpZCI6ImQ5YWRiMGIxYTdlNzYxNzEiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJsb25nYnJpZGdlIiwic3ViIjoiYWNjZXNzX3Rva2VuIiwiZXhwIjoxNzc5Mzc1MjU3LCJpYXQiOjE3NzE1OTkyNTcsImFrIjoiNjhmMmUyYTYyYTc5MTE5NDNiZDA1ZGI0YmQ1ODRiNmMiLCJhYWlkIjoyMDY2MjY5MCwiYWMiOiJsYiIsIm1pZCI6MTkxOTcyNzksInNpZCI6IlJlWVV3Ymp2YS85RkZyVnNxdWNxZHc9PSIsImJsIjozLCJ1bCI6MCwiaWsiOiJsYl8yMDY2MjY5MCJ9.ZI9JnvLIXOK0ajC9QUa_hRq_tTYOGCorCbWM_xW4VyKIE8DOpa16icCclLI8KPtvVOcNfrmTmMBocK-HN_nUJLoHXQAznothipdrJ941Ja12xocc83PMWIiMMXTJU6xGTDBWl4lEBwDofRIx78d9BUlGteYobCMztdqt3360M9G0M2kqCj3U0mYBuZU5bdrRZE54NY4LTkD8D0zygaZlDTNrkMdBq4H1p6XFiiz5uliUSJmvZmc4V-rYehrgLGtC7nOmHsbhlOlUaW0jWyOtZquIFeUUo638UEACj5O2HM_b2nA2HXkkiDJvxRncl7qv1i0DEtsN5HUXQ_ZzbDMvs0VR3ID92v6zQ7EGi6u6mKZeCp5dlXIRmtBjee3Y5qxUVJccJxMhR0R78a4iSX68oUXhgoDhNTyctxPnfafttLo5SDdbSIpoScJ0oecM30wAWSkk-LAX305-K4076i4RWrxf3tFusORuWBA5y__rqBBOhYlhrqwxNsyfp6tl8n7ezZUnkGxglY9nhtyLG44tj-YqIOeITReMxq9MQ7knaKn5_6bM2cAFtSQHJyr5ZdoWOpCpZwZhwDGHYltX5tEaL5qxrfhEfncbOkZCkv7w1TvtlSNpVSeGnV2Am5W5cDm2cwEQzx1HlkdaVq1QspGkYP30uBEwoXgqhTCSSX7Atcw'

from longbridge_api import get_longbridge_api
import sqlite3

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def main():
    print("="*70)
    print("📊 世运电路(603920) - A股个股深度分析 (长桥API+Skill)")
    print("="*70)
    
    # Step 1: 使用长桥API获取实时行情
    print("\n【Step 1: 长桥API实时行情】")
    print("-"*70)
    
    api = get_longbridge_api()
    if not api:
        print("❌ 长桥API初始化失败")
        return
    
    quote = api.get_quote('603920.SH')
    if not quote:
        print("❌ 获取行情失败")
        return
    
    # 打印实时数据
    print(f"股票代码: {quote.get('symbol', 'N/A')}")
    print(f"股票名称: {quote.get('name', 'N/A')}")
    print(f"最新价格: ¥{quote.get('last_price', 0):.2f}")
    print(f"涨跌幅度: {quote.get('change_rate', 0)*100:+.2f}%")
    print(f"涨跌金额: ¥{quote.get('change', 0):.2f}")
    print(f"今日开盘: ¥{quote.get('open', 0):.2f}")
    print(f"今日最高: ¥{quote.get('high', 0):.2f}")
    print(f"今日最低: ¥{quote.get('low', 0):.2f}")
    print(f"昨日收盘: ¥{quote.get('prev_close', 0):.2f}")
    print(f"成交量: {quote.get('volume', 0)/10000:.0f}万手")
    print(f"成交额: ¥{quote.get('turnover', 0)/100000000:.2f}亿")
    
    # 保存实时价格
    current_price = quote.get('last_price', 0)
    change_rate = quote.get('change_rate', 0) * 100
    
    # Step 2: 数据库分析
    print("\n\n【Step 2: 历史数据分析】")
    print("-"*70)
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取历史因子数据
    row = conn.execute('''
        SELECT ret_20, ret_60, vol_20, price_pos_20, mom_accel
        FROM stock_factors
        WHERE ts_code = "603920.SH"
        ORDER BY trade_date DESC
        LIMIT 1
    ''').fetchone()
    
    if row:
        ret20, ret60, vol, price_pos, mom = row
        print(f"20日收益率: {ret20*100:.1f}%" if ret20 else "20日收益率: 无数据")
        print(f"60日收益率: {ret60*100:.1f}%" if ret60 else "60日收益率: 无数据")
        print(f"波动率: {vol:.2f}" if vol else "波动率: 无数据")
    
    # Step 3: v26评分
    print("\n\n【Step 3: v26全因子综合评分】")
    print("-"*70)
    
    score = 0
    details = []
    
    if ret20:
        s = ret20 * 100 * 0.20
        score += s
        details.append(("动量因子(20日)", s, ret20*100))
    
    if ret60:
        s = ret60 * 100 * 0.15
        score += s
        details.append(("中期动量(60日)", s, ret60*100))
    
    if vol:
        s = -vol * 30 * 0.15
        score += s
        details.append(("波动率因子", s, vol))
    
    print("评分明细:")
    for name, s, val in details:
        print(f"  {name}: {s:+.1f}分 (原始值: {val:.2f})")
    
    print(f"\n综合评分: {score:+.1f}分")
    
    if score > 15:
        rating = "🟢 Tier 1 - 强烈推荐"
    elif score > 8:
        rating = "🟡 Tier 2 - 推荐"
    elif score > 0:
        rating = "⚪ Tier 3 - 观望"
    else:
        rating = "🔴 Tier 4 - 回避"
    
    print(f"评级: {rating}")
    
    # Step 4: 投资建议
    print("\n\n【Step 4: 投资建议】")
    print("-"*70)
    
    print(f"🟡 基于长桥API实时数据:")
    print(f"  当前价格: ¥{current_price:.2f}")
    print(f"  今日涨跌: {change_rate:+.2f}%")
    print(f"  v26评分: {score:.1f}分")
    
    if score > 8:
        print(f"\n✅ 建议操作:")
        print(f"  - 评级: Tier 2 (推荐)")
        print(f"  - 仓位: 3-5%")
        print(f"  - 目标: +15%")
        print(f"  - 止损: -10%")
    else:
        print(f"\n⚠️ 建议操作:")
        print(f"  - 评级: Tier 3 (观望)")
        print(f"  - 仓位: 1-2%试水")
        print(f"  - 等待更好买点")
    
    conn.close()
    
    print("\n" + "="*70)
    print("分析完成!")
    print("="*70)

if __name__ == '__main__':
    main()
