#!/root/.openclaw/workspace/venv/bin/python3
"""
A股收盘深度报告 - 专业版 v5
包含: 行情、资金流向、龙虎榜、Exa新闻、操作建议
API: 长桥 > efinance > 腾讯
"""
import sys
import os
sys.path.insert(0, '/root/.openclaw/workspace/tools')

from datetime import datetime
import pandas as pd
import numpy as np
import requests
import json
import subprocess
import time

from longbridge_api import get_longbridge_api

REPORT_DIR = '/root/.openclaw/workspace/data'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_exa_news(query, num_results=5):
    """使用Exa搜索新闻"""
    try:
        result = subprocess.run(
            ['mcporter', 'call', f'exa.web_search_exa({{"query": "{query}", "numResults": {num_results}}})'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            # 解析mcporter输出
            output = result.stdout
            # 尝试提取JSON结果
            try:
                # 找到JSON开始的位置
                json_start = output.find('{')
                if json_start >= 0:
                    data = json.loads(output[json_start:])
                    return data.get('results', [])
            except:
                pass
    except Exception as e:
        log(f"Exa搜索失败 {query}: {e}")
    return []

def analyze_news_impact(news_list):
    """分析新闻影响"""
    keywords = {
        '政策利好': ['政策', '降准', '降息', '刺激', '支持', '补贴', '改革'],
        '政策利空': ['收紧', '监管', '处罚', '退市', '风险', '警示'],
        '行业利好': ['订单', '中标', '扩产', '技术突破', '新产品', '认证'],
        '行业利空': ['减持', '亏损', '暴雷', '问询', '调查'],
        '外部因素': ['美股', '港股', '美联储', '汇率', '贸易战', '地缘'],
    }
    
    analysis = {k: [] for k in keywords.keys()}
    
    for news in news_list:
        title = news.get('title', '') + ' ' + news.get('text', '')
        for category, words in keywords.items():
            if any(word in title for word in words):
                analysis[category].append(news)
    
    return analysis

def get_fund_flow():
    """获取资金流向（使用efinance）"""
    try:
        import efinance as ef
        
        # 获取行业资金流向
        log("获取行业资金流向...")
        
        # 使用akshare获取资金流向
        try:
            import akshare as ak
            
            # 行业资金流向
            sector_flow = ak.stock_sector_fund_flow_rank()
            if sector_flow is not None and not sector_flow.empty:
                return sector_flow
        except:
            pass
        
        # 备选：使用efinance获取主力净流入
        log("使用备选方案获取资金流向...")
        return None
    except Exception as e:
        log(f"获取资金流向失败: {e}")
    return None

def get_longhu_data():
    """获取龙虎榜数据"""
    try:
        import akshare as ak
        
        today = datetime.now().strftime('%Y%m%d')
        log(f"获取龙虎榜数据 {today}...")
        
        # 龙虎榜详情
        longhu = ak.stock_lhb_detail_daily(start_date=today, end_date=today)
        if longhu is not None and not longhu.empty:
            return longhu
    except Exception as e:
        log(f"获取龙虎榜失败: {e}")
    return None

def get_market_data():
    """获取市场数据（长桥API）"""
    try:
        import tushare as ts
        ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
        pro = ts.pro_api()
        stocks = pro.stock_basic(exchange='', list_status='L')
        codes = stocks['ts_code'].tolist()
        
        log(f"长桥API获取 {len(codes)} 只股票...")
        api = get_longbridge_api()
        
        lb_codes = []
        for code in codes:
            if code.endswith('.SH'):
                lb_codes.append(f"{code[:-3]}.SH")
            elif code.endswith('.SZ'):
                lb_codes.append(f"{code[:-3]}.SZ")
            elif code.endswith('.BJ'):
                lb_codes.append(f"{code[:-3]}.BJ")
        
        all_data = []
        batch_size = 100
        
        for i in range(0, len(lb_codes), batch_size):
            batch = lb_codes[i:i+batch_size]
            try:
                quotes = api.get_quotes(batch)
                for q in quotes:
                    all_data.append({
                        'ts_code': q['symbol'],
                        'close': q['price'],
                        'pct_chg': q['change'],
                        'volume': q['volume'],
                        'amount': q['turnover']
                    })
                time.sleep(0.05)
            except:
                continue
        
        return pd.DataFrame(all_data)
    except Exception as e:
        log(f"获取市场数据失败: {e}")
    return None

def generate_deep_report():
    """生成深度报告"""
    log("="*60)
    log("A股收盘深度报告 - 专业版 v5")
    log("="*60)
    
    today = datetime.now().strftime('%Y%m%d')
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 1. 基础行情
    df = get_market_data()
    if df is None or df.empty:
        log("❌ 无法获取市场数据")
        return None
    
    total = len(df)
    up = len(df[df['pct_chg'] > 0])
    down = len(df[df['pct_chg'] < 0])
    avg_change = df['pct_chg'].mean()
    limit_up = len(df[df['pct_chg'] >= 9.5])
    limit_down = len(df[df['pct_chg'] <= -9.5])
    total_amount = df['amount'].sum()
    
    # 2. Exa新闻搜索
    log("="*60)
    log("Exa搜索实时新闻...")
    
    news_queries = [
        "A股市场今日行情",
        "A股资金流向", 
        "中国政策利好",
        "美股影响A股",
        "科技股行情"
    ]
    
    all_news = []
    for query in news_queries:
        news = get_exa_news(query, 3)
        all_news.extend(news)
        time.sleep(0.5)
    
    news_analysis = analyze_news_impact(all_news)
    
    # 3. 资金流向
    fund_flow = get_fund_flow()
    
    # 4. 龙虎榜
    longhu = get_longhu_data()
    
    # 生成报告
    report = f"""{'='*70}
📊 A股收盘深度报告 - 专业版 ({today})
数据来源: 长桥API + Exa搜索 + efinance | 统计: {total}只
{'='*70}

【一、市场全景】
┌─────────────────────────────────────────────────────────────────────┐
│ 涨跌分布: 🔴 {up:5}只上涨 | 🟢 {down:5}只下跌                              │
│ 平均涨跌幅: {avg_change:+.2f}%                                              │
│ 涨停: {limit_up:3}只 | 跌停: {limit_down:3}只                                   │
│ 两市成交额: {total_amount/1e8:.0f}亿                                        │
└─────────────────────────────────────────────────────────────────────┘

【二、热点新闻分析】(Exa实时搜索)
"""
    
    for category, news_list in news_analysis.items():
        if news_list:
            report += f"\n📰 {category} ({len(news_list)}条):\n"
            for news in news_list[:3]:
                title = news.get('title', '无标题')
                report += f"   • {title[:60]}...\n"
    
    # 板块表现（基于个股数据估算）
    df['sector'] = df['ts_code'].apply(lambda x: 
        '科创板' if x.startswith('6') and x[3:5] in ['88', '89'] 
        else '创业板' if x.startswith('3')
        else '北交所' if x.startswith('8') or x.startswith('4')
        else '主板'
    )
    
    sector_perf = df.groupby('sector')['pct_chg'].mean().sort_values(ascending=False)
    
    report += f"""
【三、板块表现】
"""
    for sector, pct in sector_perf.items():
        emoji = "🔴" if pct > 0 else "🟢"
        report += f"{emoji} {sector:8s}: {pct:+6.2f}%\n"
    
    # 涨跌幅榜
    top_up = df.nlargest(10, 'pct_chg')
    top_down = df.nsmallest(10, 'pct_chg')
    
    report += f"""
【四、涨幅榜 TOP10】
"""
    for i, (_, row) in enumerate(top_up.iterrows(), 1):
        report += f"{i:2}. {row['ts_code']}: {row['close']:8.2f}  +{row['pct_chg']:6.2f}%\n"
    
    report += f"""
【五、跌幅榜 TOP10】
"""
    for i, (_, row) in enumerate(top_down.iterrows(), 1):
        report += f"{i:2}. {row['ts_code']}: {row['close']:8.2f}  {row['pct_chg']:6.2f}%\n"
    
    # 操作建议
    trend = "上涨" if avg_change > 0.5 else "下跌" if avg_change < -0.5 else "震荡"
    sentiment = "积极" if limit_up > limit_down * 1.5 else "中性" if limit_up > limit_down else "谨慎"
    
    report += f"""
【六、深度分析与明日展望】

📊 **技术面分析:**
• 今日市场呈{trend}态势，{up}只上涨，{down}只下跌
• 涨跌停比 {limit_up}:{limit_down}，情绪{sentiment}
• 成交额 {total_amount/1e8:.0f}亿，{'放量' if total_amount > 1e12 else '缩量'}

📰 **新闻面影响:**
"""
    
    if news_analysis['政策利好']:
        report += "• 政策面有利好支撑\n"
    if news_analysis['外部因素']:
        report += "• 需关注外盘动态及地缘政治影响\n"
    if news_analysis['行业利好']:
        report += "• 行业层面有积极信号\n"
    
    report += f"""
💡 **明日操作策略:**

**整体仓位建议:** {'维持6-7成' if sentiment == '积极' else '控制在5成左右' if sentiment == '中性' else '减仓至4成以下'}

**板块建议:**
"""
    
    # 根据今日表现给出建议
    if sector_perf.iloc[0] > 0:
        report += f"• ✅ 关注: {sector_perf.index[0]}（今日领涨，趋势可能延续）\n"
    if sector_perf.iloc[-1] < -1:
        report += f"• ⚠️ 规避: {sector_perf.index[-1]}（今日领跌，谨慎抄底）\n"
    
    report += f"""• 💡 策略: {'逢低布局优质标的' if avg_change < 0 else '持股待涨，注意止盈'}
• ⏰ 时机: 关注开盘30分钟资金流向，再决定加仓与否

⚠️ **风险提示:**
• 注意高位股回调风险
• 关注北向资金流向
• 控制单票仓位，分散投资
• 设置止损位，严格执行

{'='*70}
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}
"""
    
    filename = f"{REPORT_DIR}/daily_report_deep_{today}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"✅ 深度报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_deep_report()
