#!/root/.openclaw/workspace/venv/bin/python3
"""手动生成A+H开盘前瞻报告（备用数据修复版）"""
import subprocess
from datetime import datetime

now = datetime.now()
today_str = now.strftime('%Y-%m-%d')

# ============ A股数据（上周五2026-05-29收盘 + 今日集合竞价） ============
a_stocks = {
    '002371.SZ': {'name': '北方华创', 'sector': 'AI算力', 'change_fri': -4.42, 'change_pre': -0.77},
    '688012.SH': {'name': '中微公司', 'sector': '半导体设备', 'change_fri': -2.04, 'change_pre': -2.58},
    '688256.SH': {'name': '寒武纪', 'sector': 'AI算力', 'change_fri': -5.86, 'change_pre': None},
    '300474.SZ': {'name': '景嘉微', 'sector': 'AI算力', 'change_fri': -8.59, 'change_pre': 0.86},
    '688072.SH': {'name': '拓荆科技', 'sector': '半导体设备', 'change_fri': -6.63, 'change_pre': -2.71},
    '688120.SH': {'name': '华海清科', 'sector': '半导体设备', 'change_fri': -4.81, 'change_pre': -0.11},
    '300316.SZ': {'name': '晶盛机电', 'sector': '半导体设备', 'change_fri': -7.41, 'change_pre': 1.12},
    '300308.SZ': {'name': '中际旭创', 'sector': '光通讯', 'change_fri': -3.07, 'change_pre': -0.01},
    '300502.SZ': {'name': '新易盛', 'sector': '光通讯', 'change_fri': -1.66, 'change_pre': 0.38},
    '300394.SZ': {'name': '天孚通信', 'sector': '光通讯', 'change_fri': 1.71, 'change_pre': 1.00},
    '002281.SZ': {'name': '光迅科技', 'sector': '光通讯', 'change_fri': -5.10, 'change_pre': 2.02},
    '300750.SZ': {'name': '宁德时代', 'sector': '新能源', 'change_fri': 2.00, 'change_pre': 1.91},
    '002594.SZ': {'name': '比亚迪', 'sector': '新能源', 'change_fri': 0.31, 'change_pre': 0.00},
    '601012.SH': {'name': '隆基绿能', 'sector': '新能源', 'change_fri': -3.21, 'change_pre': -0.22},
    '600438.SH': {'name': '通威股份', 'sector': '新能源', 'change_fri': -2.38, 'change_pre': -1.15},
    '600519.SH': {'name': '贵州茅台', 'sector': '消费', 'change_fri': 3.92, 'change_pre': 0.08},
    '000858.SZ': {'name': '五粮液', 'sector': '消费', 'change_fri': 4.17, 'change_pre': -1.11},
    '000568.SZ': {'name': '泸州老窖', 'sector': '消费', 'change_fri': 2.27, 'change_pre': -0.14},
    '002304.SZ': {'name': '洋河股份', 'sector': '消费', 'change_fri': 3.49, 'change_pre': -0.24},
    '600036.SH': {'name': '招商银行', 'sector': '金融', 'change_fri': 2.40, 'change_pre': -0.03},
    '601318.SH': {'name': '中国平安', 'sector': '金融', 'change_fri': 1.96, 'change_pre': -0.02},
    '300059.SZ': {'name': '东方财富', 'sector': '金融', 'change_fri': -0.16, 'change_pre': -0.57},
    '600030.SH': {'name': '中信证券', 'sector': '金融', 'change_fri': 2.76, 'change_pre': -0.15},
    '600276.SH': {'name': '恒瑞医药', 'sector': '医药', 'change_fri': 4.56, 'change_pre': 0.26},
    '300760.SZ': {'name': '迈瑞医疗', 'sector': '医药', 'change_fri': 0.70, 'change_pre': -0.12},
    '603259.SH': {'name': '药明康德', 'sector': '医药', 'change_fri': 2.40, 'change_pre': 0.03},
    '688235.SH': {'name': '百济神州', 'sector': '医药', 'change_fri': 4.57, 'change_pre': -1.07},
}

# ============ 港股数据（实时 2026-06-01 09:20） ============
h_stocks = {
    '00700.HK': {'name': '腾讯控股', 'sector': '科技巨头', 'change': 1.22},
    '09988.HK': {'name': '阿里巴巴', 'sector': '科技巨头', 'change': 0.33},
    '09988.HK-b': {'name': '阿里巴巴', 'sector': '中概互联', 'change': 0.33},  # 映射到中概互联
    '03690.HK': {'name': '美团', 'sector': '科技巨头', 'change': 2.38},
    '01810.HK': {'name': '小米集团', 'sector': '科技巨头', 'change': 0.00},
    '09618.HK': {'name': '京东集团', 'sector': '中概互联', 'change': -1.50},
    '00241.HK': {'name': '阿里健康', 'sector': '中概互联', 'change': -0.28},
    '00386.HK': {'name': '中石化', 'sector': '能源', 'change': 0.00},
    '00883.HK': {'name': '中海油', 'sector': '能源', 'change': -0.61},
    '01088.HK': {'name': '中国神华', 'sector': '能源', 'change': -0.04},
    '02318.HK': {'name': '中国平安', 'sector': '金融', 'change': -0.08},
    '03968.HK': {'name': '招商银行', 'sector': '金融', 'change': 0.00},
    '01299.HK': {'name': '友邦保险', 'sector': '金融', 'change': 0.00},
    '01398.HK': {'name': '工商银行', 'sector': '金融', 'change': -0.75},
    '02331.HK': {'name': '李宁', 'sector': '消费', 'change': 0.38},
    '09633.HK': {'name': '农夫山泉', 'sector': '消费', 'change': -1.54},
    '02269.HK': {'name': '药明生物', 'sector': '生物医药', 'change': 1.08},
    '01093.HK': {'name': '石药集团', 'sector': '生物医药', 'change': 2.40},
    '01898.HK': {'name': '中煤能源', 'sector': '能源', 'change': 0.00},
    '02359.HK': {'name': '药明康德', 'sector': '生物医药', 'change': -1.00},
}

# ============ 美股隔夜回顾 ============
us_summary = {
    'dow': 0.72, 'nasdaq': 0.20, 'sp500': 0.22,
    'sectors': [
        ('存储/数据中心', 4.52, 'Datadog +9.82%'),
        ('AI算力', 2.92, '超微电脑 +11.60%'),
        ('金融', 1.12, '摩根士丹利 +2.07%'),
        ('科技巨头', -0.05, '微软 +5.45%'),
        ('中概互联', -0.27, '拼多多 +1.70%'),
        ('光通讯', -0.50, 'Arista +2.70%'),
        ('能源', -0.92, '雪佛龙 -0.31%'),
        ('生物医药', -0.93, '诺和诺德 +0.15%'),
        ('半导体', -1.03, '阿斯麦 +0.44%'),
        ('消费', -1.90, '麦当劳 +0.44%'),
    ]
}

# ============ 新闻驱动因子 ============
news_factors = [
    {'keyword': '半导体', 'importance': '⭐⭐⭐⭐ 高', 'sectors': '半导体设备', 'reason': '半导体产业动态', 'source': 'Exa全网搜索'},
    {'keyword': '芯片', 'importance': '⭐⭐⭐⭐ 高', 'sectors': '半导体设备/AI算力', 'reason': '芯片产业链', 'source': '新浪财经'},
    {'keyword': '人工智能', 'importance': '⭐⭐⭐⭐ 高', 'sectors': 'AI算力', 'reason': 'AI产业', 'source': '新浪财经'},
    {'keyword': '美联储', 'importance': '⭐⭐⭐⭐ 高', 'sectors': '金融', 'reason': '美联储政策', 'source': '华尔街见闻'},
    {'keyword': '港股', 'importance': '⭐⭐⭐ 中', 'sectors': '科技巨头/中概互联', 'reason': '港股市场', 'source': 'Exa全网搜索'},
    {'keyword': '政策', 'importance': '⭐⭐⭐ 中', 'sectors': '金融/消费', 'reason': '政策影响', 'source': '新浪财经'},
]

# ============ 辅助函数 ============
def get_emoji(change):
    if change >= 3: return '🚀'
    if change >= 1: return '📈'
    if change > 0: return '🟢'
    if change == 0: return '⚪'
    if change > -1: return '🔴'
    if change > -3: return '📉'
    return '🔻'

def format_change(change):
    if change is None: return '-'
    return f"{change:+.2f}%"

def get_action_emoji(change):
    if change >= 3: return ('🟢 看多', '板块强势，可考虑加仓')
    if change >= 1: return ('🟡 关注', '走势偏强，观察持续性')
    if change > 0: return ('⚪ 观望', '小幅上涨，等待方向')
    if change == 0: return ('⚪ 持平', '暂无明确信号')
    if change > -1: return ('⚪ 观望', '小幅回调，等待企稳')
    if change > -3: return ('🟠 谨慎', '板块走弱，注意风险')
    return ('🔴 回避', '板块低迷，建议减仓')

# ============ 计算板块数据 ============
from collections import defaultdict

a_sector_map = defaultdict(list)
for sym, info in a_stocks.items():
    a_sector_map[info['sector']].append(info)

h_sector_map = defaultdict(list)
for sym, info in h_stocks.items():
    # 处理双重映射
    if sym == '09988.HK':
        h_sector_map['科技巨头'].append(info)
    elif sym == '09988.HK-b':
        pass  # 已处理
    else:
        h_sector_map[info['sector']].append(info)

# A股板块强弱（基于上周五收盘，集合竞价辅助参考）
a_sectors_sorted = []
for sector_name, stocks in a_sector_map.items():
    changes = [s['change_fri'] for s in stocks if s['change_fri'] is not None]
    if changes:
        avg = sum(changes) / len(changes)
        leader = max(stocks, key=lambda x: x['change_fri'] if x['change_fri'] is not None else -999)
        a_sectors_sorted.append((sector_name, avg, len(stocks), leader))

a_sectors_sorted.sort(key=lambda x: x[1], reverse=True)

# 港股板块强弱
h_sectors_sorted = []
for sector_name, stocks in h_sector_map.items():
    changes = [s['change'] for s in stocks]
    if changes:
        avg = sum(changes) / len(changes)
        leader = max(stocks, key=lambda x: x['change'])
        h_sectors_sorted.append((sector_name, avg, len(stocks), leader))

h_sectors_sorted.sort(key=lambda x: x[1], reverse=True)

# 个股监控
a_all = list(a_stocks.values())
a_gainers = sorted(a_all, key=lambda x: x['change_fri'] if x['change_fri'] is not None else -999, reverse=True)[:5]
a_losers = sorted(a_all, key=lambda x: x['change_fri'] if x['change_fri'] is not None else 999)[:5]

h_all = [info for sym, info in h_stocks.items() if not sym.endswith('-b')]
h_gainers = sorted(h_all, key=lambda x: x['change'], reverse=True)[:5]
h_losers = sorted(h_all, key=lambda x: x['change'])[:5]

# ============ 生成报告 ============
report_lines = [
    f"# 🌅 A+H股开盘前瞻报告 v2.0",
    f"",
    f"**报告生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
    f"**数据日期**: {today_str}",
    f"**分析框架**: 美股回顾 + A股板块 + 港股板块 + 新闻驱动",
    f"**数据来源**: A股(新浪财经集合竞价+Tushare上周五收盘) | 港股(新浪财经实时)",
    f"",
    f"---",
    f"",
    f"## 一、隔夜美股回顾",
    f"",
    f"**核心指数表现**:",
    f"• 📈 道琼斯: +{us_summary['dow']:.2f}%",
    f"• 📈 纳斯达克: +{us_summary['nasdaq']:.2f}%",
    f"• 📈 标普500: +{us_summary['sp500']:.2f}%",
    f"",
    f"**美股板块强弱**:",
]

for name, change, leader in us_summary['sectors']:
    emoji = get_emoji(change)
    report_lines.append(f"• {emoji} **{name}** {change:+.2f}% ({leader})")

report_lines.extend([
    f"",
    f"**对A+H开盘启示**:",
    f"• 🟡 美股AI算力强势(+2.92%)，但半导体整体回调(-1.03%)",
    f"• 🟡 美股消费疲软(-1.90%)，关注A股消费分化",
    f"• 🟢 美股金融上涨(+1.12%)，对A股金融板块有正面映射",
    f"• ⚪ 中概互联微跌(-0.27%)，港股科技开盘情绪中性偏谨慎",
    f"",
    f"---",
    f"",
    f"## 二、A股板块强弱排序（上周五收盘参考）",
    f"",
    f"| 排名 | 板块 | 平均涨跌 | 个股数 | 领涨股 |",
    f"|------|------|----------|--------|--------|"
])

for i, (sector_name, avg, count, leader) in enumerate(a_sectors_sorted, 1):
    emoji = get_emoji(avg)
    rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
    leader_str = f"{leader['name']} {format_change(leader['change_fri'])}"
    report_lines.append(f"| {rank} | {emoji} {sector_name} | {format_change(avg)} | {count}只 | {leader_str} |")

report_lines.extend([
    f"",
    f"**集合竞价观察**: 光迅科技(+2.02%)、宁德时代(+1.91%)、晶盛机电(+1.12%)竞价偏强；拓荆科技(-2.71%)、中微公司(-2.58%)竞价承压。",
    f"",
    f"---",
    f"",
    f"## 三、港股板块强弱排序（实时 09:20）",
    f"",
    f"| 排名 | 板块 | 平均涨跌 | 个股数 | 领涨股 |",
    f"|------|------|----------|--------|--------|"
])

for i, (sector_name, avg, count, leader) in enumerate(h_sectors_sorted, 1):
    emoji = get_emoji(avg)
    rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
    leader_str = f"{leader['name']} {format_change(leader['change'])}"
    report_lines.append(f"| {rank} | {emoji} {sector_name} | {format_change(avg)} | {count}只 | {leader_str} |")

report_lines.extend([
    f"",
    f"---",
    f"",
    f"## 四、新闻驱动因子（隔夜+A股开盘）",
    f"",
    f"| 驱动因子 | 重要度 | 影响板块 | 逻辑 | 来源 |",
    f"|----------|--------|----------|------|------|"
])

for factor in news_factors:
    report_lines.append(f"| {factor['keyword']} | {factor['importance']} | {factor['sectors']} | {factor['reason']} | {factor['source']} |")

report_lines.extend([
    f"",
    f"---",
    f"",
    f"## 五、开盘策略建议",
    f"",
    f"### A股策略",
    f"",
    f"| 板块 | 操作 | 建议 |",
    f"|------|------|------|"
])

for sector_name, avg, count, leader in a_sectors_sorted:
    action, advice = get_action_emoji(avg)
    report_lines.append(f"| {sector_name} | {action} | {advice} |")

report_lines.extend([
    f"",
    f"**综合策略**:",
    f"• 🟢 消费/医药上周五强势，今日若延续可考虑短线参与",
    f"• 🟡 半导体/AI算力上周五调整+竞价分化，等待企稳信号",
    f"• 🟡 新能源宁德竞价偏强(+1.91%)，关注产业链修复",
    f"• ⚪ 金融板块稳健，但竞价偏弱，观望为主",
    f"",
    f"### 港股策略",
    f"",
    f"| 板块 | 操作 | 建议 |",
    f"|------|------|------|"
])

for sector_name, avg, count, leader in h_sectors_sorted:
    action, advice = get_action_emoji(avg)
    report_lines.append(f"| {sector_name} | {action} | {advice} |")

report_lines.extend([
    f"",
    f"**综合策略**:",
    f"• 🟢 科技巨头腾讯+美团竞价偏强，可适当关注",
    f"• 🟠 中概互联京东拖累(-1.50%)，谨慎对待",
    f"• ⚪ 能源/金融整体偏弱，观望为主",
    f"• 🟡 生物医药石药集团(+2.40%)偏强，药明系分化",
    f"",
    f"---",
    f"",
    f"## 六、重点个股监控",
    f"",
    f"### A股（上周五表现）",
    f"",
    f"**🔥 涨幅前5**:",
])

for stock in a_gainers:
    emoji = "🚀" if stock['change_fri'] > 5 else "📈"
    report_lines.append(f"- {emoji} **{stock['name']}**: {format_change(stock['change_fri'])} - {stock['sector']}")

report_lines.append(f"")
report_lines.append(f"**🔻 跌幅前5**:")

for stock in a_losers:
    emoji = "🔻" if stock['change_fri'] < -5 else "📉"
    report_lines.append(f"- {emoji} **{stock['name']}**: {format_change(stock['change_fri'])} - {stock['sector']}")

report_lines.extend([
    f"",
    f"### 港股（实时 09:20）",
    f"",
    f"**🔥 涨幅前5**:",
])

for stock in h_gainers:
    emoji = "🚀" if stock['change'] > 5 else "📈"
    report_lines.append(f"- {emoji} **{stock['name']}**: {format_change(stock['change'])} - {stock['sector']}")

report_lines.append(f"")
report_lines.append(f"**🔻 跌幅前5**:")

for stock in h_losers:
    emoji = "🔻" if stock['change'] < -5 else "📉"
    report_lines.append(f"- {emoji} **{stock['name']}**: {format_change(stock['change'])} - {stock['sector']}")

report_lines.extend([
    f"",
    f"---",
    f"",
    f"## ⚠️ 数据说明",
    f"",
    f"- **长桥API token已过期** (exp: 2026-05-21)，当前使用备用数据源",
    f"- **A股行情**: 新浪财经集合竞价 + Tushare上周五(2026-05-29)收盘数据",
    f"- **港股行情**: 新浪财经实时行情（2026-06-01 09:20）",
    f"- **美股回顾**: 引用 `us_market_daily_20260601.md` 报告",
    f"- **新闻驱动**: Exa全网搜索 + 新浪财经 + 华尔街见闻 + 第一财经",
    f"",
    f"---",
    f"",
    f"⚠️ **风险提示**: 本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。",
    f"",
    f"📅 **下次报告**: 15:00 收盘深度分析"
])

report = "\n".join(report_lines)

# 保存报告
report_file = f"/root/.openclaw/workspace/data/ah_market_preopen_{today_str}.md"
with open(report_file, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"✅ 报告已生成: {report_file}")
print(report[:3000])
print("\n... [完整报告见文件] ...")

# 发送到飞书
print("\n📤 正在发送到飞书...")
try:
    cmd = [
        '/root/.openclaw/workspace/venv/bin/python3',
        '/root/.openclaw/workspace/tools/send_feishu.py',
        'ou_efbad805767f4572e8f93ebafa8d5402',
        report
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        print("✅ 飞书消息已发送")
    else:
        print(f"⚠️ 飞书发送失败: {result.stderr[:200]}")
except Exception as e:
    print(f"⚠️ 飞书发送异常: {e}")
