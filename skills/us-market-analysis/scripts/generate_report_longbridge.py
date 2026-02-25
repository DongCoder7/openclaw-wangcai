#!/usr/bin/env python3
"""
美股市场分析报告生成器 (长桥API版)
每日生成美股隔夜分析报告，自动推送到飞书
"""
import sys
import os
import json
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')
from longbridge_api import get_longbridge_api

# 飞书推送函数
def send_feishu_message(content: str, title: str = "美股报告"):
    """发送飞书消息"""
    try:
        # 使用OpenClaw的消息工具
        import subprocess
        result = subprocess.run([
            'openclaw', 'message', 'send',
            '--channel', 'feishu',
            '--message', f"## {title}\n\n{content[:3000]}"  # 限制长度
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 飞书消息已发送")
        else:
            print(f"⚠️ 飞书发送失败: {result.stderr}")
    except Exception as e:
        print(f"⚠️ 飞书发送异常: {e}")

def get_us_market_quotes():
    """获取美股核心指数和个股行情"""
    api = get_longbridge_api()
    
    # 核心指数
    indices = [
        ('SPX.US', '标普500'),
        ('DJI.US', '道琼斯'),
        ('IXIC.US', '纳斯达克'),
        ('VIX.US', '恐慌指数'),
    ]
    
    # 核心科技股
    tech_stocks = [
        ('AAPL.US', '苹果'),
        ('MSFT.US', '微软'),
        ('GOOGL.US', '谷歌'),
        ('META.US', 'Meta'),
        ('NVDA.US', '英伟达'),
        ('AMD.US', 'AMD'),
        ('TSLA.US', '特斯拉'),
    ]
    
    # 半导体
    semi_stocks = [
        ('NVDA.US', '英伟达'),
        ('AMD.US', 'AMD'),
        ('TSM.US', '台积电'),
        ('ASML.US', 'ASML'),
        ('AVGO.US', '博通'),
        ('QCOM.US', '高通'),
    ]
    
    # 中概股
    china_stocks = [
        ('BABA.US', '阿里巴巴'),
        ('JD.US', '京东'),
        ('PDD.US', '拼多多'),
        ('BIDU.US', '百度'),
        ('NTES.US', '网易'),
    ]
    
    all_symbols = [s[0] for s in indices + tech_stocks + semi_stocks + china_stocks]
    
    # 去重
    seen = set()
    unique_symbols = []
    for s in all_symbols:
        if s not in seen:
            seen.add(s)
            unique_symbols.append(s)
    
    return api.get_quotes(unique_symbols)

def generate_report():
    """生成美股分析报告"""
    print("🌙 正在获取美股行情数据...")
    quotes = get_us_market_quotes()
    
    if not quotes:
        print("❌ 获取数据失败")
        return
    
    # 获取当前日期
    today = datetime.now()
    us_date = today - timedelta(days=1)  # 美股是前一个交易日
    
    # 生成报告内容
    report = f"""# 📊 美股市场隔夜分析报告

**生成时间**: {today.strftime('%Y-%m-%d %H:%M')}
**数据日期**: {us_date.strftime('%Y-%m-%d')} (美股前一交易日)

---

## 一、核心指数表现

"""
    
    # 指数表现
    indices_data = []
    for q in quotes:
        if '.US' in q['symbol'] and any(x in q['symbol'] for x in ['SPX', 'DJI', 'IXIC', 'VIX']):
            indices_data.append(q)
    
    indices_data.sort(key=lambda x: x['change'], reverse=True)
    
    for q in indices_data:
        symbol = q['symbol'].replace('.US', '')
        emoji = '📈' if q['change'] > 0 else '📉' if q['change'] < 0 else '➖'
        report += f"| {emoji} **{symbol}** | {q['change']:+.2f}% |\n"
    
    report += """
---

## 二、科技股表现

| 股票 | 代码 | 价格 | 涨跌幅 | 成交额 |
|:----:|:----:|:----:|:------:|:-------|
"""
    
    tech_data = [q for q in quotes if any(x in q['symbol'] for x in ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMD', 'TSLA'])]
    tech_data.sort(key=lambda x: x['change'], reverse=True)
    
    for q in tech_data[:5]:
        symbol = q['symbol'].replace('.US', '')
        name_map = {'AAPL': '苹果', 'MSFT': '微软', 'GOOGL': '谷歌', 'META': 'Meta', 'NVDA': '英伟达', 'AMD': 'AMD', 'TSLA': '特斯拉'}
        name = name_map.get(symbol, symbol)
        emoji = '🔴' if q['change'] > 0 else '🟢' if q['change'] < 0 else '⚪'
        report += f"| {name} | {symbol} | ${q['price']:.2f} | {emoji} {q['change']:+.2f}% | ${q['turnover']/1e9:.1f}B |\n"
    
    report += """
---

## 三、中概股表现

| 股票 | 代码 | 价格 | 涨跌幅 | 成交额 |
|:----:|:----:|:----:|:------:|:-------|
"""
    
    china_data = [q for q in quotes if any(x in q['symbol'] for x in ['BABA', 'JD', 'PDD', 'BIDU', 'NTES'])]
    china_data.sort(key=lambda x: x['change'], reverse=True)
    
    for q in china_data:
        symbol = q['symbol'].replace('.US', '')
        name_map = {'BABA': '阿里巴巴', 'JD': '京东', 'PDD': '拼多多', 'BIDU': '百度', 'NTES': '网易'}
        name = name_map.get(symbol, symbol)
        emoji = '🔴' if q['change'] > 0 else '🟢' if q['change'] < 0 else '⚪'
        report += f"| {name} | {symbol} | ${q['price']:.2f} | {emoji} {q['change']:+.2f}% | ${q['turnover']/1e9:.1f}B |\n"
    
    report += """
---

## 四、对A股开盘策略启示

**核心逻辑**:
1. 美股科技股表现 → A股科技板块映射
2. 中概股表现 → 港股/A股情绪
3. 指数整体方向 → 全球风险偏好

"""
    
    # 生成策略建议
    avg_change = sum(q['change'] for q in quotes) / len(quotes) if quotes else 0
    
    if avg_change > 1:
        report += "**🟢 美股强势**: 纳斯达克/标普大涨，A股高开概率大，关注科技成长板块\n"
    elif avg_change > 0:
        report += "**🟡 美股小涨**: 情绪偏积极，A股可能小幅高开\n"
    elif avg_change > -1:
        report += "**🟠 美股小跌**: 情绪偏谨慎，A股可能低开或平开\n"
    else:
        report += "**🔴 美股大跌**: 避险情绪升温，A股低开概率大，控制仓位\n"
    
    # 中概股情绪
    china_avg = sum(q['change'] for q in china_data) / len(china_data) if china_data else 0
    if china_avg > 2:
        report += f"**🚀 中概股强势**: 中概平均+{china_avg:.2f}%，港股科技股高开\n"
    elif china_avg < -2:
        report += f"**📉 中概股弱势**: 中概平均{china_avg:.2f}%，港股科技股承压\n"
    
    report += "\n---\n\n**数据来源**: 长桥API | **报告生成**: 美股分析模块\n"
    
    # 保存报告
    report_file = f"/root/.openclaw/workspace/data/us_market_daily_{today.strftime('%Y%m%d')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 报告已生成: {report_file}")
    print("\n" + "="*80)
    print(report)
    
    # 发送到飞书
    print("\n📤 正在发送到飞书...")
    send_feishu_message(report, "📊 美股市场隔夜分析报告")
    
    return report

if __name__ == "__main__":
    generate_report()
