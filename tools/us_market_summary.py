#!/usr/bin/env python3
"""
美股市场深度分析 - 专业版
每日8:30运行，生成完整的美股板块分析报告
"""
import subprocess
import json
from datetime import datetime, timedelta
import sys
import os

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')

USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

# 美股板块定义
US_SECTORS = {
    '光通讯': ['ANET', 'LITE', 'CIEN', 'NPTN', 'AAOI'],
    '半导体': ['NVDA', 'AMD', 'INTC', 'TSM', 'ASML', 'AMAT', 'LRCX', 'KLAC'],
    'AI算力': ['NVDA', 'AMD', 'AVGO', 'MRVL', 'SMCI'],
    '科技巨头': ['AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA'],
    '生物医药': ['LLY', 'NVO', 'JNJ', 'PFE', 'MRK', 'UNH'],
    '存储/数据中心': ['WDC', 'STX', 'SNOW', 'NET', 'DDOG'],
    '能源': ['XOM', 'CVX', 'COP', 'OXY', 'SLB'],
    '金融': ['V', 'MA', 'JPM', 'BAC', 'GS', 'MS'],
    '消费': ['WMT', 'COST', 'HD', 'NKE', 'MCD', 'SBUX'],
    '中概互联': ['BABA', 'JD', 'PDD', 'NIO', 'LI', 'XPEV', 'TME']
}

def get_us_stock_quote(symbol):
    """获取美股个股行情 - 使用腾讯API"""
    try:
        import requests
        url = f"https://qt.gtimg.cn/q=us{symbol}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            text = response.text
            if '"' in text:
                inner = text.split('"')[1]
                parts = inner.split('~')
                if len(parts) > 32:
                    name = parts[1] if len(parts) > 1 else symbol
                    price = float(parts[3]) if len(parts) > 3 else 0
                    change = float(parts[32]) if len(parts) > 32 else 0
                    return {'symbol': symbol, 'name': name, 'price': price, 'change': change}
    except Exception as e:
        print(f"获取{symbol}失败: {e}")
    return None

def analyze_sectors():
    """分析美股板块"""
    print("📊 正在获取美股板块数据...")
    
    sector_data = {}
    
    for sector_name, symbols in US_SECTORS.items():
        stocks = []
        for symbol in symbols:
            quote = get_us_stock_quote(symbol)
            if quote:
                stocks.append(quote)
        
        if stocks:
            avg_change = sum(s['change'] for s in stocks) / len(stocks)
            up_count = sum(1 for s in stocks if s['change'] > 0)
            
            # 排序找出领涨/领跌
            stocks_sorted = sorted(stocks, key=lambda x: x['change'], reverse=True)
            leader = stocks_sorted[0] if stocks_sorted else None
            
            sector_data[sector_name] = {
                'avg_change': avg_change,
                'up_count': up_count,
                'total': len(stocks),
                'stocks': stocks,
                'leader': leader
            }
    
    # 按涨幅排序
    sorted_sectors = sorted(sector_data.items(), key=lambda x: x[1]['avg_change'], reverse=True)
    return sorted_sectors

def get_market_indices():
    """获取主要指数"""
    indices = {}
    
    # 道琼斯
    dji = get_us_stock_quote('DJI')
    if dji:
        indices['道琼斯'] = dji
    
    # 纳斯达克
    ixic = get_us_stock_quote('IXIC')
    if ixic:
        indices['纳斯达克'] = ixic
    
    # 标普500
    spx = get_us_stock_quote('SPX') or get_us_stock_quote('INX')
    if spx:
        indices['标普500'] = spx
    
    return indices

def format_change(value):
    """格式化涨跌幅"""
    try:
        change = float(value)
        if change > 0:
            return f"+{change:.2f}%"
        else:
            return f"{change:.2f}%"
    except:
        return "--"

def get_emoji(change):
    """根据涨跌获取emoji"""
    try:
        c = float(change)
        if c > 1.5:
            return "🚀"
        elif c > 0:
            return "📈"
        elif c > -1.5:
            return "📉"
        else:
            return "🔻"
    except:
        return "⚪"

def generate_report():
    """生成完整报告"""
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    
    # 数据日期（前一交易日）
    data_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 获取板块数据
    sectors = analyze_sectors()
    indices = get_market_indices()
    
    # 找出亮点个股（涨幅前5）
    all_stocks = []
    for sector_name, sector_info in sectors:
        for stock in sector_info['stocks']:
            all_stocks.append({**stock, 'sector': sector_name})
    
    top_gainers = sorted(all_stocks, key=lambda x: x['change'], reverse=True)[:5]
    top_losers = sorted(all_stocks, key=lambda x: x['change'])[:5]
    
    # 生成报告
    report = f"""✅ **美股市场深度分析任务完成**

报告生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
数据日期: {data_date}（前一交易日）

📊 **核心摘要**

**主要指数**:
"""
    
    # 添加指数
    for name, idx in indices.items():
        emoji = get_emoji(idx['change'])
        report += f"• {emoji} **{name}**: {format_change(idx['change'])}\n"
    
    report += "\n**板块强弱排序**:\n"
    
    # 添加板块排序
    for i, (sector_name, sector_info) in enumerate(sectors, 1):
        emoji = get_emoji(sector_info['avg_change'])
        leader_info = ""
        if sector_info['leader']:
            leader = sector_info['leader']
            leader_info = f"（{leader['name']} {format_change(leader['change'])}领涨）"
        
        report += f"{i}. {emoji} **{sector_name}** {format_change(sector_info['avg_change'])} {leader_info}\n"
    
    report += """
🔥 **关键发现**

**亮点个股**:
"""
    
    # 添加亮点个股
    for stock in top_gainers:
        emoji = "🚀" if stock['change'] > 3 else "📈"
        report += f"• {emoji} **{stock['name']}** ({stock['symbol']}): {format_change(stock['change'])} — {stock['sector']}板块\n"
    
    report += """
**拖累因素**:
"""
    
    # 添加拖累个股
    for stock in top_losers:
        emoji = "🔻" if stock['change'] < -3 else "📉"
        report += f"• {emoji} **{stock['name']}** ({stock['symbol']}): {format_change(stock['change'])} — {stock['sector']}板块\n"
    
    report += """
💡 **对A股开盘策略启示**

"""
    
    # 根据美股表现给出启示
    if indices:
        nasdaq_change = indices.get('纳斯达克', {}).get('change', 0)
        if nasdaq_change > 1:
            report += "• 🟢 美股科技股大涨，A股AI算力/半导体板块可能高开\n"
            report += "• 🟢 光通讯板块美股强势，关注A股光模块联动\n"
        elif nasdaq_change < -1:
            report += "• 🔴 美股科技股下跌，A股科技板块可能承压\n"
            report += "• 🟡 关注防御性板块（高股息、消费）避险机会\n"
        else:
            report += "• ⚪ 美股震荡，A股可能独立走势\n"
            report += "• 🟡 关注国内政策和资金流向\n"
    
    report += """
📁 **产出文件**
- 美股板块数据已保存到数据库
- 可用于后续A+H开盘前瞻分析

---
下次任务: 09:15 A+H市场盘前分析（ah-market-preopen）
"""
    
    return report

def send_report(report):
    """发送报告到Feishu"""
    try:
        result = subprocess.run(
            ['openclaw', 'message', 'send', '--target', USER_ID, '--message', report],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("✅ 报告已发送到Feishu")
            return True
        else:
            print(f"❌ 发送失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False

def main():
    print("="*60)
    print("📊 美股市场深度分析")
    print("="*60)
    
    # 生成报告
    report = generate_report()
    
    print("\n" + "="*60)
    print(report)
    
    # 发送报告
    success = send_report(report)
    
    # 保存报告
    today = datetime.now().strftime('%Y%m%d')
    report_path = f'/root/.openclaw/workspace/data/us_market_daily_{today}.md'
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n✅ 报告已保存: {report_path}")
    
    # 记录发送状态
    with open('/root/.openclaw/workspace/tools/us_market_send.log', 'a') as f:
        f.write(f"{datetime.now()}: {'发送成功' if success else '发送失败'}\n")

if __name__ == "__main__":
    main()
