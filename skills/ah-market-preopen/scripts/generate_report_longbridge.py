#!/usr/bin/env python3
"""
A+H股开盘前瞻报告生成器 (长桥API版)
每日9:15前生成开盘策略分析，自动推送到飞书
"""
import sys
import os
import json
from datetime import datetime

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')
from longbridge_api import get_longbridge_api

# 飞书推送函数
def send_feishu_message(content: str, title: str = "A+H开盘报告"):
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

def get_a_h_quotes():
    """获取A+H股核心标的行情"""
    api = get_longbridge_api()
    
    # A股核心标的
    a_stocks = [
        ('002371.SZ', '北方华创'),
        ('688012.SH', '中微公司'),
        ('600519.SH', '贵州茅台'),
        ('000858.SZ', '五粮液'),
        ('300750.SZ', '宁德时代'),
    ]
    
    # 港股核心标的
    h_stocks = [
        ('00700.HK', '腾讯'),
        ('09988.HK', '阿里'),
        ('03690.HK', '美团'),
        ('01810.HK', '小米'),
        ('00883.HK', '中海油'),
    ]
    
    all_symbols = [s[0] for s in a_stocks + h_stocks]
    
    return api.get_quotes(all_symbols)

def generate_report():
    """生成A+H开盘前瞻报告"""
    print("🌅 正在获取A+H股行情数据...")
    quotes = get_a_h_quotes()
    
    if not quotes:
        print("❌ 获取数据失败")
        return
    
    today = datetime.now()
    
    # 生成报告内容
    report = f"""# 📊 A+H股开盘前瞻报告

**生成时间**: {today.strftime('%Y-%m-%d %H:%M')}
**数据来源**: 长桥API

---

## 一、隔夜美股回顾

*参见美股隔夜分析报告*

---

## 二、A股开盘前瞻

### 核心标的涨跌

| 标的 | 代码 | 价格 | 涨跌幅 | 成交额 |
|:----:|:----:|:----:|:------:|:-------|
"""
    
    a_data = [q for q in quotes if '.SZ' in q['symbol'] or '.SH' in q['symbol']]
    a_data.sort(key=lambda x: x['change'], reverse=True)
    
    name_map = {
        '002371.SZ': '北方华创',
        '688012.SH': '中微公司',
        '600519.SH': '贵州茅台',
        '000858.SZ': '五粮液',
        '300750.SZ': '宁德时代',
    }
    
    for q in a_data:
        name = name_map.get(q['symbol'], q['symbol'])
        code = q['symbol'].split('.')[0]
        emoji = '🔴' if q['change'] > 0 else '🟢' if q['change'] < 0 else '⚪'
        report += f"| {name} | {code} | ¥{q['price']:.2f} | {emoji} {q['change']:+.2f}% | {q['turnover']/1e8:.1f}亿 |\n"
    
    report += """
### 板块情绪判断

"""
    
    a_avg = sum(q['change'] for q in a_data) / len(a_data) if a_data else 0
    if a_avg > 1:
        report += f"**🟢 强势**: A股核心标的平均+{a_avg:.2f}%，开盘乐观\n"
    elif a_avg > 0:
        report += f"**🟡 偏强**: A股核心标的平均+{a_avg:.2f}%，开盘平稳\n"
    elif a_avg > -1:
        report += f"**🟠 偏弱**: A股核心标的平均{a_avg:.2f}%，开盘谨慎\n"
    else:
        report += f"**🔴 弱势**: A股核心标的平均{a_avg:.2f}%，开盘承压\n"
    
    report += """
---

## 三、港股开盘前瞻

### 核心标的涨跌

| 标的 | 代码 | 价格 | 涨跌幅 | 成交额 |
|:----:|:----:|:----:|:------:|:-------|
"""
    
    h_data = [q for q in quotes if '.HK' in q['symbol']]
    h_data.sort(key=lambda x: x['change'], reverse=True)
    
    h_name_map = {
        '00700.HK': '腾讯',
        '09988.HK': '阿里',
        '03690.HK': '美团',
        '01810.HK': '小米',
        '00883.HK': '中海油',
    }
    
    for q in h_data:
        name = h_name_map.get(q['symbol'], q['symbol'])
        code = q['symbol'].replace('.HK', '')
        emoji = '🔴' if q['change'] > 0 else '🟢' if q['change'] < 0 else '⚪'
        report += f"| {name} | {code} | HK${q['price']:.2f} | {emoji} {q['change']:+.2f}% | {q['turnover']/1e8:.1f}亿 |\n"
    
    report += """
### 板块情绪判断

"""
    
    h_avg = sum(q['change'] for q in h_data) / len(h_data) if h_data else 0
    if h_avg > 1:
        report += f"**🟢 强势**: 港股核心标的平均+{h_avg:.2f}%，开盘乐观\n"
    elif h_avg > 0:
        report += f"**🟡 偏强**: 港股核心标的平均+{h_avg:.2f}%，开盘平稳\n"
    elif h_avg > -1:
        report += f"**🟠 偏弱**: 港股核心标的平均{h_avg:.2f}%，开盘谨慎\n"
    else:
        report += f"**🔴 弱势**: 港股核心标的平均{h_avg:.2f}%，开盘承压\n"
    
    report += """
---

## 四、开盘策略建议

| 情景 | 概率 | 操作建议 |
|:-----|:----:|:---------|
"""
    
    if a_avg > 0 and h_avg > 0:
        report += "| A+H双双上涨 | 高 | 🟢 积极做多，科技成长优先 |\n"
    elif a_avg < 0 and h_avg < 0:
        report += "| A+H双双下跌 | 高 | 🔴 控制仓位，防御为主 |\n"
    else:
        report += "| A股强港股弱/ vice versa | 中 | 🟡 结构性机会，精选个股 |\n"
    
    report += """
---

## 五、重点关注

1. **北向资金流向**: 开盘后30分钟观察
2. **成交量变化**: 对比昨日同期
3. **板块轮动**: 科技/金融/消费跷跷板
4. **美股映射**: 关注科技板块联动

---

**数据来源**: 长桥API | **报告生成**: A+H开盘前瞻模块

"""
    
    # 保存报告
    report_file = f"/root/.openclaw/workspace/data/ah_market_preopen_{today.strftime('%Y%m%d')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 报告已生成: {report_file}")
    print("\n" + "="*80)
    print(report)
    
    # 发送到飞书
    print("\n📤 正在发送到飞书...")
    send_feishu_message(report, "🌅 A+H股开盘前瞻报告")
    
    return report

if __name__ == "__main__":
    generate_report()
