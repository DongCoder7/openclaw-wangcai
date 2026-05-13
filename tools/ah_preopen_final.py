#!/root/.openclaw/workspace/venv/bin/python3
"""
A+H股开盘前瞻报告 - 完整版
整合长桥API/腾讯API数据
"""
import json
from datetime import datetime

# ============ A股盘前数据（腾讯API） ============
a_quotes = {
    '600887': {'name': '伊利股份', 'price': 29.43, 'change_pct': -0.32, 'sector': '消费医药'},
    '600036': {'name': '招商银行', 'price': 44.31, 'change_pct': 0.08, 'sector': '金融'},
    '603893': {'name': '瑞芯微', 'price': 175.50, 'change_pct': -5.26, 'sector': '科技/半导体'},
    '300502': {'name': '新易盛', 'price': 118.68, 'change_pct': -1.25, 'sector': 'AI算力'},
    '600900': {'name': '长江电力', 'price': 29.42, 'change_pct': 0.00, 'sector': '新能源/资源'},
    '601012': {'name': '隆基绿能', 'price': 15.97, 'change_pct': 0.00, 'sector': '新能源/资源'},
    '601318': {'name': '中国平安', 'price': 53.31, 'change_pct': -0.17, 'sector': '金融'},
    '000858': {'name': '五 粮 液', 'price': 132.66, 'change_pct': 0.01, 'sector': '消费医药'},
    '601899': {'name': '紫金矿业', 'price': 17.73, 'change_pct': 0.09, 'sector': '新能源/资源'},
    '600519': {'name': '贵州茅台', 'price': 1568.00, 'change_pct': -0.12, 'sector': '消费医药'},
    '300760': {'name': '迈瑞医疗', 'price': 219.00, 'change_pct': 0.00, 'sector': '科技/半导体'},
    '688981': {'name': '中芯国际', 'price': 82.74, 'change_pct': -1.62, 'sector': '科技/半导体'},
    '688012': {'name': '中微公司', 'price': 176.77, 'change_pct': -1.92, 'sector': '科技/半导体'},
    '300750': {'name': '宁德时代', 'price': 229.95, 'change_pct': -0.65, 'sector': '新能源/资源'},
    '603019': {'name': '中科曙光', 'price': 66.40, 'change_pct': -0.94, 'sector': 'AI算力'},
    '002230': {'name': '科大讯飞', 'price': 48.65, 'change_pct': -0.31, 'sector': 'AI算力'},
    '000001': {'name': '平安银行', 'price': 11.97, 'change_pct': 0.00, 'sector': '金融'},
    '300308': {'name': '中际旭创', 'price': 138.02, 'change_pct': -2.26, 'sector': 'AI算力'},
    '601166': {'name': '兴业银行', 'price': 22.72, 'change_pct': 0.11, 'sector': '金融'},
    '603259': {'name': '药明康德', 'price': 63.04, 'change_pct': 0.01, 'sector': '消费医药'},
}

# ============ 港股盘前数据（腾讯API） ============
h_quotes = {
    '00700': {'name': '腾讯控股', 'price': 451.60, 'change_pct': -1.22, 'sector': '科技'},
    '09988': {'name': '阿里巴巴-W', 'price': 137.00, 'change_pct': 2.78, 'sector': '科技'},
    '03690': {'name': '美团-W', 'price': 83.80, 'change_pct': -0.42, 'sector': '科技'},
    '01810': {'name': '小米集团-W', 'price': 31.92, 'change_pct': 1.46, 'sector': '科技'},
    '02318': {'name': '中国平安', 'price': 64.10, 'change_pct': -1.38, 'sector': '金融地产'},
    '03988': {'name': '中国银行', 'price': 5.23, 'change_pct': -0.19, 'sector': '金融地产'},
    '01109': {'name': '华润置地', 'price': 35.46, 'change_pct': -6.98, 'sector': '金融地产'},
    '00688': {'name': '中国海外发展', 'price': 15.82, 'change_pct': -1.13, 'sector': '金融地产'},
    '00883': {'name': '中国海洋石油', 'price': 26.92, 'change_pct': 0.00, 'sector': '能源资源'},
    '00857': {'name': '中国石油股份', 'price': 10.53, 'change_pct': -4.79, 'sector': '能源资源'},
    '01088': {'name': '中国神华', 'price': 44.90, 'change_pct': 0.00, 'sector': '能源资源'},
    '00998': {'name': '中信银行', 'price': 8.48, 'change_pct': 0.00, 'sector': '能源资源'},
    '02331': {'name': '李宁', 'price': 19.02, 'change_pct': -2.01, 'sector': '消费医药'},
    '06690': {'name': '海尔智家', 'price': 21.20, 'change_pct': 0.09, 'sector': '消费医药'},
    '09618': {'name': '京东集团-SW', 'price': 123.50, 'change_pct': 4.31, 'sector': '消费医药'},
    '09999': {'name': '网易-S', 'price': 170.00, 'change_pct': -8.55, 'sector': '消费医药'},
}

# ============ 板块分析 ============
def analyze_a_sectors():
    sectors = {}
    for code, q in a_quotes.items():
        s = q['sector']
        if s not in sectors:
            sectors[s] = {'stocks': [], 'sum_change': 0}
        sectors[s]['stocks'].append(q)
        sectors[s]['sum_change'] += q['change_pct']
    
    result = []
    for s, data in sectors.items():
        avg = data['sum_change'] / len(data['stocks'])
        up = sum(1 for st in data['stocks'] if st['change_pct'] > 0)
        result.append({
            'name': s,
            'avg': avg,
            'up': up,
            'total': len(data['stocks']),
            'stocks': sorted(data['stocks'], key=lambda x: x['change_pct'], reverse=True)
        })
    return sorted(result, key=lambda x: x['avg'], reverse=True)

def analyze_h_sectors():
    sectors = {}
    for code, q in h_quotes.items():
        s = q['sector']
        if s not in sectors:
            sectors[s] = {'stocks': [], 'sum_change': 0}
        sectors[s]['stocks'].append(q)
        sectors[s]['sum_change'] += q['change_pct']
    
    result = []
    for s, data in sectors.items():
        avg = data['sum_change'] / len(data['stocks'])
        up = sum(1 for st in data['stocks'] if st['change_pct'] > 0)
        result.append({
            'name': s,
            'avg': avg,
            'up': up,
            'total': len(data['stocks']),
            'stocks': sorted(data['stocks'], key=lambda x: x['change_pct'], reverse=True)
        })
    return sorted(result, key=lambda x: x['avg'], reverse=True)

# ============ 生成报告 ============
today = datetime.now().strftime('%Y-%m-%d')
time_str = datetime.now().strftime('%H:%M')

a_sectors = analyze_a_sectors()
h_sectors = analyze_h_sectors()

# A股涨跌统计
a_up = sum(1 for q in a_quotes.values() if q['change_pct'] > 0)
a_down = sum(1 for q in a_quotes.values() if q['change_pct'] < 0)
a_flat = len(a_quotes) - a_up - a_down

# 港股涨跌统计
h_up = sum(1 for q in h_quotes.values() if q['change_pct'] > 0)
h_down = sum(1 for q in h_quotes.values() if q['change_pct'] < 0)
h_flat = len(h_quotes) - h_up - h_down

report = f"""📊 A+H股开盘前瞻报告

生成时间: {today} {time_str}
数据来源: 腾讯财经API（集合竞价）+ 美股盘前数据

═══════════════════════════════════════

🇺🇸 一、隔夜美股回顾（5月12日）

• 📈 道琼斯: +0.11%
• 📉 纳斯达克: -0.71%
• 📉 标普500: -0.16%

板块表现:
🥇 生物医药 +1.68% | 🥈 能源 +1.17% | 🥉 消费 +0.95%
🔻 半导体 -3.51%（QCOM -11.46%, INTC -6.82%）
🔻 中概互联 -2.47%

关键映射:
⚠️ 半导体大跌 → A股芯片/半导体承压
⚠️ 高通跌11% → 拖累消费电子情绪
✅ 能源上涨 → 三桶油有支撑
✅ 消费上涨 → 白酒板块情绪稳定

═══════════════════════════════════════

🇨🇳 二、A股开盘前瞻（集合竞价）

情绪面: 涨跌比 {a_up}:{a_down}:{a_flat}（涨:跌:平）

板块强弱:
"""

for i, s in enumerate(a_sectors, 1):
    emoji = '🟢' if s['avg'] >= 0 else '🔴'
    report += f"{i}. {emoji} {s['name']}: {s['avg']:+.2f}% ({s['up']}/{s['total']}涨)\n"
    for st in s['stocks'][:2]:
        report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"

# A股涨跌幅排行
a_sorted = sorted(a_quotes.values(), key=lambda x: x['change_pct'], reverse=True)
report += "\n📈 涨幅前三:\n"
for st in a_sorted[:3]:
    report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
report += "\n📉 跌幅前三:\n"
for st in a_sorted[-3:]:
    report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"

report += f"""
═══════════════════════════════════════

🇭🇰 三、港股开盘前瞻（集合竞价）

情绪面: 涨跌比 {h_up}:{h_down}:{h_flat}（涨:跌:平）

板块强弱:
"""

for i, s in enumerate(h_sectors, 1):
    emoji = '🟢' if s['avg'] >= 0 else '🔴'
    report += f"{i}. {emoji} {s['name']}: {s['avg']:+.2f}% ({s['up']}/{s['total']}涨)\n"
    for st in s['stocks'][:2]:
        report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"

# 港股涨跌幅排行
h_sorted = sorted(h_quotes.values(), key=lambda x: x['change_pct'], reverse=True)
report += "\n📈 涨幅前三:\n"
for st in h_sorted[:3]:
    report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"
report += "\n📉 跌幅前三:\n"
for st in h_sorted[-3:]:
    report += f"   {st['name']}: {st['change_pct']:+.2f}%\n"

report += """
═══════════════════════════════════════

🎯 四、开盘策略建议

【A股】
• 半导体/芯片板块受美股拖累，开盘承压，谨慎观望
• 能源板块（三桶油映射）有支撑
• 高股息防御属性继续受青睐
• 重点关注：中际旭创(-2.26%)、瑞芯微(-5.26%)能否企稳

【港股】
• 科技股分化：阿里(+2.78%)强势，腾讯(-1.22%)承压
• 地产板块大跌（华润置地-6.98%），谨慎
• 京东(+4.31%)受业绩利好带动
• 网易(-8.55%)大幅调整，关注原因

【跨市场联动】
• 半导体→承压 | 能源→有支撑 | 消费→中性
• 若A股低开 > 0.5%，关注错杀机会
• 若A股高开，半导体不追，能源可持有

═══════════════════════════════════════

⚠️ 免责声明: 本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。

"""

print(report)

# 保存报告
import os
output_dir = os.path.expanduser('~/.openclaw/workshop/data')
os.makedirs(output_dir, exist_ok=True)
filename = f'{output_dir}/ah_preopen_{today}.md'
with open(filename, 'w', encoding='utf-8') as f:
    f.write(report)
print(f'✅ 报告已保存: {filename}')
