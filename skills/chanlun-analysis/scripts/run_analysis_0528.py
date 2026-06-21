#!/root/.openclaw/workspace/venv/bin/python3
"""
获取2026-05-28上证指数数据并运行缠论v3.3分析
"""
import sys
sys.path.insert(0, '/root/.openclaw/skills/chanlun-analysis/scripts')

import efinance as ef
import pandas as pd
from datetime import datetime

# 获取数据
print("="*60)
print("获取上证指数(000001) 2026-05-28数据...")
print("="*60)

# 日线数据（最近3个月）
df_daily = ef.stock.get_quote_history('000001', klt=101)  # 日线
df_daily['日期'] = pd.to_datetime(df_daily['日期'])
df_daily = df_daily.rename(columns={
    '日期': 'Date', '开盘': 'Open', '最高': 'High', 
    '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'
})
df_daily = df_daily[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
df_daily.to_csv('/mnt/kimi/output/sh_1day.csv', index=False)
print(f"日线: {len(df_daily)}条, 最新: {df_daily['Date'].iloc[-1].strftime('%Y-%m-%d')}")

# 5分钟数据（最近1个月）
df_5m = ef.stock.get_quote_history('000001', klt=5)  # 5分钟
df_5m['日期'] = pd.to_datetime(df_5m['日期'] + ' ' + df_5m['时间'])
df_5m = df_5m.rename(columns={
    '日期': 'Date', '开盘': 'Open', '最高': 'High', 
    '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'
})
df_5m = df_5m[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
df_5m.to_csv('/mnt/kimi/output/sh_5min_full.csv', index=False)
print(f"5分钟: {len(df_5m)}条, 最新: {df_5m['Date'].iloc[-1].strftime('%Y-%m-%d %H:%M')}")

# 1分钟数据（最近1天）
try:
    df_1m = ef.stock.get_quote_history('000001', klt=1)  # 1分钟
    df_1m['日期'] = pd.to_datetime(df_1m['日期'] + ' ' + df_1m['时间'])
    df_1m = df_1m.rename(columns={
        '日期': 'Date', '开盘': 'Open', '最高': 'High', 
        '最低': 'Low', '收盘': 'Close', '成交量': 'Volume'
    })
    df_1m = df_1m[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
    df_1m.to_csv('/mnt/kimi/output/sh_1min.csv', index=False)
    print(f"1分钟: {len(df_1m)}条, 最新: {df_1m['Date'].iloc[-1].strftime('%Y-%m-%d %H:%M')}")
except Exception as e:
    print(f"1分钟数据获取失败: {e}")
    df_1m = None

# 运行v3.3分析
print("\n" + "="*60)
print("运行缠论分析 v3.3...")
print("="*60)

from chan_analysis_v33 import ChanAnalysisV33

analyzer = ChanAnalysisV33(
    df_1m=df_1m if df_1m is not None and len(df_1m) > 0 else None,
    df_5m=df_5m,
    df_daily=df_daily
)

report = analyzer.generate_report()

# 输出分析报告
print("\n" + "="*60)
print("【缠论多级别联立分析报告 v3.3】")
print(f"分析日期: 2026-05-28")
print("="*60)

# 1. 数据完整性
print("\n📊 【数据完整性检查】")
all_ok = True
for level, data in report['data_integrity'].items():
    status = "✅" if data['usable'] else "❌"
    if not data['usable']:
        all_ok = False
    print(f"  {status} {level}: {data['total_rows']}根 {data.get('warning', '')}")

# 2. 假突破识别
print("\n🔍 【假突破/骗炮识别】")
for level, data in report['fake_breakout'].items():
    if data.get('type') in ['假突破(骗炮)', '假跌破', '真突破', '真跌破']:
        icon = "⚠️" if data.get('is_fake') else ("✅" if "真突破" in data.get('type','') else ("❌" if "真跌破" in data.get('type','') else ""))
        print(f"  {icon} {level}: {data['type']} → {data['action']}")

# 3. 联合支撑/压制区
print("\n🔗 【联合支撑/联合压制区】")
uz = report['unified_zone']
if uz['count'] > 0:
    for z in uz['unified_zones']:
        icon = "🛡️" if '支撑' in z['type'] else "⛰️"
        print(f"  {icon} {z['strength']}: {z['description']}")
else:
    print("  无显著联合区")

# 4. 二买/二卖
print("\n🎯 【二买/二卖结构】")
for level, data in report['second_buy'].items():
    if data.get('usable', True):
        icon = "✅" if data.get('is_valid') else ("❌" if "失败" in data.get('type','') else "⏳")
        print(f"  {icon} {level}: {data.get('type','')} → {data.get('action','')}")

# 5. 级别传导链
print("\n⚡ 【级别传导链】")
tc = report['transmission_chain']
dir_icon = "🔴" if tc['direction'] == 'down' else ("🟢" if tc['direction'] == 'up' else "⚪")
print(f"  {dir_icon} 方向: {tc['direction'].upper()} | 风险: {tc['risk_level'].upper()}")
print(f"  📌 {tc['description']}")

# 6. 双日级别
print("\n📅 【双日级别分析】")
dd = report['dual_day']
if dd.get('usable', True):
    icon = "❌" if dd.get('death_risk') else ("✅" if dd.get('trend') == 'bull' else "⚠️")
    print(f"  {icon} {dd['description']}")
    print(f"     操作: {dd['action']}")

# 7. 时间窗口
print("\n⏰ 【时间窗口】")
tw = report['time_window']
icon = "✅ 窗口开放" if tw['is_window_open'] else "⛔ 窗口关闭"
print(f"  {icon}: {tw['description']}")
print(f"  建议: {tw['action']}")

# 8. 55线状态
print("\n📈 【55线思维分析】")
for level, data in report['55line_analysis'].items():
    icon = "✅" if "主涨段" in data['structure'] else ("❌" if "主跌段" in data['structure'] else "⚠️")
    print(f"  {icon} {level}: {data['price']:.2f} vs MA55={data['ma55']:.2f} | {data['structure']}")

# 9. MACD极强期
print("\n🔥 【MACD极强期】")
has_extreme = False
for level, data in report['macd_extreme'].items():
    if data['is_extreme']:
        has_extreme = True
        print(f"  🔥 {level}: {data['description']} (强度{data['strength']:.0f}%)")
if not has_extreme:
    print("  无极强形态")

# 10. 复合风控
print("\n🛡️ 【复合风控】")
for pair, risk in report['composite_risk'].items():
    icon = "🔴" if risk['risk_level'] == 'high' else ("🟡" if risk['risk_level'] == 'medium' else "🟢")
    print(f"  {icon} {pair}: {risk['risk_level'].upper()}({risk['risk_score']}分)")
    print(f"     信号: {', '.join(risk['signals']) if risk['signals'] else '无'}")
    print(f"     操作: {risk['action']}")

# 11. 补偿性买点
print("\n💰 【补偿性买点】")
has_buy = False
for level, data in report['compensation_buy'].items():
    if data.get('is_compensation_zone'):
        has_buy = True
        print(f"  ✅ {level}: 区域{data['zone'][0]:.0f}-{data['zone'][1]:.0f} | {data['confirmation']}")
        print(f"     {data['action']}")
if not has_buy:
    print("  暂无补偿性买点")

# 12. 目标价
print("\n🎯 【目标价推导】")
for level, data in report['target_price'].items():
    print(f"  {level}: 支撑{data['nearest_support']:.2f} | 压力{data['nearest_resistance']:.2f}")

print("\n" + "="*60)
print("【核心结论】")
print("="*60)

# 综合判断
dual_day_trend = report['dual_day'].get('trend', 'unknown')
transmission_dir = report['transmission_chain'].get('direction', 'neutral')
time_window_open = report['time_window'].get('is_window_open', False)

print(f"""
1. 战略级别(双日): {'多头 ✅' if dual_day_trend in ['bull', 'golden_cross'] else '空头 ❌' if dual_day_trend in ['bear', 'death_cross'] else '临界 ⚠️'}
2. 传导链方向: {'下跌 🔴' if transmission_dir == 'down' else '上涨 🟢' if transmission_dir == 'up' else '震荡 ⚪'}
3. 时间窗口: {'开放 ✅' if time_window_open else '关闭 ⛔'} → {report['time_window'].get('action', '观望')}
4. 联合区: {uz['count']}个显著联合区
5. 二买状态: {sum(1 for v in report['second_buy'].values() if v.get('is_valid'))}个成立
""")

print("="*60)
print("分析完成")
