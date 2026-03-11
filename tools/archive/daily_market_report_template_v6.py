#!/root/.openclaw/workspace/venv/bin/python3
"""
A股收盘深度报告 - 标准模板 v6
包含: 外围市场、A股行情、资金流向、龙虎榜、Exa新闻、操作建议
API: 长桥 > efinance > 腾讯

使用方式:
    ./venv_runner.sh tools/daily_market_report_template_v6.py
    
输出: data/daily_report_YYYYMMDD.md
"""
import sys
import os
sys.path.insert(0, '/root/.openclaw/workspace/tools')

from datetime import datetime
import pandas as pd
import requests
import json
import subprocess
import time

from longbridge_api import get_longbridge_api

REPORT_DIR = '/root/.openclaw/workspace/data'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_exa_news(queries, num_results=5):
    """使用Exa搜索新闻"""
    all_news = []
    for query in queries:
        try:
            result = subprocess.run(
                ['mcporter', 'call', f'exa.web_search_exa({{"query": "{query}", "numResults": {num_results}}})'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                output = result.stdout
                try:
                    json_start = output.find('{')
                    if json_start >= 0:
                        data = json.loads(output[json_start:])
                        results = data.get('results', [])
                        for r in results:
                            all_news.append({
                                'title': r.get('title', ''),
                                'text': r.get('text', '')[:200],
                                'url': r.get('url', '')
                            })
                except:
                    pass
            time.sleep(0.3)
        except Exception as e:
            log(f"Exa搜索失败 {query}: {e}")
    return all_news

def get_us_stock_market():
    """获取美股行情"""
    try:
        url = 'https://qt.gtimg.cn/q=usDJI,usIXIC,usINX'
        r = requests.get(url, timeout=10)
        data = {}
        for line in r.text.strip().split(';'):
            if not line.strip():
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            code = parts[0].split('_')[-1]
            values = parts[1].strip('"').split('~')
            if len(values) > 30:
                name_map = {'usDJI': '道琼斯', 'usIXIC': '纳斯达克', 'usINX': '标普500'}
                name = name_map.get(code, code)
                price = float(values[3])
                pre_close = float(values[4])
                if pre_close > 0:
                    change_pct = (price - pre_close) / pre_close * 100
                    change = price - pre_close
                else:
                    change_pct = 0
                    change = 0
                data[code] = {'name': name, 'price': price, 'change': change, 'change_pct': change_pct}
        return data
    except Exception as e:
        log(f"获取美股失败: {e}")
    return {}

def get_hk_stock_market():
    """获取港股行情"""
    try:
        url = 'https://qt.gtimg.cn/q=hkHSI,hkHSTECH'
        r = requests.get(url, timeout=10)
        data = {}
        for line in r.text.strip().split(';'):
            if not line.strip():
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            values = parts[1].strip('"').split('~')
            if len(values) > 30:
                name = values[1]
                price = float(values[3])
                pre_close = float(values[4])
                if pre_close > 0:
                    change_pct = (price - pre_close) / pre_close * 100
                    change = price - pre_close
                else:
                    change_pct = 0
                    change = 0
                data[name] = {'price': price, 'change': change, 'change_pct': change_pct}
        return data
    except Exception as e:
        log(f"获取港股失败: {e}")
    return {}

def get_longhu_data():
    """获取龙虎榜数据"""
    try:
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        longhu = ak.stock_lhb_detail_em(start_date=today, end_date=today)
        if longhu is not None and not longhu.empty:
            return longhu
    except Exception as e:
        log(f"获取龙虎榜失败: {e}")
    return None

def get_a_stock_market():
    """获取A股行情（长桥API）"""
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
        log(f"获取A股失败: {e}")
    return None

def generate_report():
    """生成标准深度报告"""
    log("="*60)
    log("A股收盘深度报告 - 标准模板 v6")
    log("="*60)
    
    today = datetime.now().strftime('%Y%m%d')
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 1. 外围市场
    log("获取外围市场数据...")
    us_market = get_us_stock_market()
    hk_market = get_hk_stock_market()
    
    # 2. A股数据
    log("获取A股行情...")
    df = get_a_stock_market()
    if df is None or df.empty:
        log("❌ A股数据获取失败")
        return None
    
    total = len(df)
    up = len(df[df['pct_chg'] > 0])
    down = len(df[df['pct_chg'] < 0])
    avg_change = df['pct_chg'].mean()
    limit_up = len(df[df['pct_chg'] >= 9.5])
    limit_down = len(df[df['pct_chg'] <= -9.5])
    total_amount = df['amount'].sum()
    
    # 3. Exa新闻
    log("Exa搜索新闻...")
    news_queries = [
        "A股今日行情",
        "美股最新走势",
        "中东局势 美伊以冲突",
        "AI算力 芯片 最新消息",
        "龙虎榜 机构席位"
    ]
    news_list = get_exa_news(news_queries, 3)
    
    # 4. 龙虎榜
    log("获取龙虎榜...")
    longhu = get_longhu_data()
    
    # 5. 板块分析
    df['sector'] = df['ts_code'].apply(lambda x: 
        '科创板' if x.startswith('6') and x[3:5] in ['88', '89'] 
        else '创业板' if x.startswith('3')
        else '北交所' if x.startswith('8') or x.startswith('4')
        else '主板'
    )
    sector_perf = df.groupby('sector')['pct_chg'].mean().sort_values(ascending=False)
    
    # 涨跌幅榜
    top_up = df.nlargest(10, 'pct_chg')
    top_down = df.nsmallest(10, 'pct_chg')
    
    # 生成报告
    report = f"""{'='*70}
📊 A股收盘深度报告 ({today})
数据来源: 长桥API + Exa搜索 + Akshare | 统计: {total}只
{'='*70}

【一、外围市场环境】

🇺🇸 美股隔夜行情:
"""
    
    for code, data in us_market.items():
        emoji = "🔴" if data['change'] > 0 else "🟢"
        report += f"{emoji} {data['name']}: {data['price']:.2f} ({data['change']:+.2f}, {data['change_pct']:+.2f}%)\n"
    
    report += f"""
🇭🇰 港股收盘:
"""
    for name, data in hk_market.items():
        emoji = "🔴" if data['change'] > 0 else "🟢"
        report += f"{emoji} {name}: {data['price']:.2f} ({data['change']:+.2f}, {data['change_pct']:+.2f}%)\n"
    
    report += f"""
【二、A股市场全景】

┌─────────────────────────────────────────────────────────────────────┐
│ 涨跌分布: 🔴 {up:5}只上涨 | 🟢 {down:5}只下跌                              │
│ 平均涨跌幅: {avg_change:+.2f}%                                              │
│ 涨停: {limit_up:3}只 | 跌停: {limit_down:3}只                                   │
│ 两市成交额: {total_amount/1e8:.0f}亿                                        │
└─────────────────────────────────────────────────────────────────────┘

【三、板块表现】
"""
    
    for sector, pct in sector_perf.items():
        emoji = "🔴" if pct > 0 else "🟢"
        report += f"{emoji} {sector:8s}: {pct:+6.2f}%\n"
    
    report += f"""
【四、热点新闻】(Exa搜索)
"""
    for news in news_list[:10]:
        title = news.get('title', '')
        if title:
            report += f"• {title[:60]}...\n"
    
    if longhu is not None and not longhu.empty:
        report += f"""
【五、龙虎榜数据】

机构净买入TOP5:
"""
        longhu_buy = longhu[longhu['龙虎榜净买额'] > 0].sort_values('龙虎榜净买额', ascending=False)
        for i, (_, row) in enumerate(longhu_buy.head(5).iterrows(), 1):
            report += f"{i}. {row['名称']}({row['代码']}): 净买{row['龙虎榜净买额']/1e8:.2f}亿, 涨{row['涨跌幅']:.2f}%\n"
        
        report += f"""
机构净卖出TOP5:
"""
        longhu_sell = longhu[longhu['龙虎榜净买额'] < 0].sort_values('龙虎榜净买额')
        for i, (_, row) in enumerate(longhu_sell.head(5).iterrows(), 1):
            report += f"{i}. {row['名称']}({row['代码']}): 净卖{row['龙虎榜净买额']/1e8:.2f}亿, 涨{row['涨跌幅']:.2f}%\n"
    
    report += f"""
【六、涨幅榜 TOP10】
"""
    for i, (_, row) in enumerate(top_up.iterrows(), 1):
        report += f"{i:2}. {row['ts_code']}: {row['close']:8.2f}  +{row['pct_chg']:6.2f}%\n"
    
    report += f"""
【七、跌幅榜 TOP10】
"""
    for i, (_, row) in enumerate(top_down.iterrows(), 1):
        report += f"{i:2}. {row['ts_code']}: {row['close']:8.2f}  {row['pct_chg']:6.2f}%\n"
    
    # 明日展望
    trend = "上涨" if avg_change > 0.5 else "下跌" if avg_change < -0.5 else "震荡"
    sentiment = "积极" if limit_up > limit_down * 1.5 else "中性" if limit_up > limit_down else "谨慎"
    
    report += f"""
【八、明日展望与操作建议】

📊 **技术面:**
• 今日市场呈{trend}态势，{up}只上涨，{down}只下跌
• 涨跌停比 {limit_up}:{limit_down}，情绪{sentiment}
• 成交额 {total_amount/1e8:.0f}亿

💡 **操作策略:**
• 仓位建议: {'维持6-7成' if sentiment == '积极' else '控制在5成左右'}
• 关注方向: 科技成长主线（AI算力/存储/光通讯）
• 回避方向: 高位消费股、受外围影响大的板块

⚠️ **风险提示:**
• 注意外围市场波动风险
• 关注地缘政治局势变化
• 控制单票仓位，设置止损

{'='*70}
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}
"""
    
    filename = f"{REPORT_DIR}/daily_report_{today}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"✅ 报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_report()
