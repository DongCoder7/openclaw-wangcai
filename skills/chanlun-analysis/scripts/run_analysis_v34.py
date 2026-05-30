#!/root/.openclaw/workspace/venv/bin/python3
"""运行缠论v3.4分析 - 2026-05-28上证指数"""
import sys
sys.path.insert(0, '/root/.openclaw/skills/chanlun-analysis/scripts')

import pandas as pd
from chan_analysis_v34 import ChanAnalysisV34

# 读取数据
df_1m = pd.read_csv('/mnt/kimi/output/sh_1min.csv')
df_1m['Date'] = pd.to_datetime(df_1m['Date'])
df_5m = pd.read_csv('/mnt/kimi/output/sh_5min_full.csv')
df_5m['Date'] = pd.to_datetime(df_5m['Date'])
df_daily = pd.read_csv('/mnt/kimi/output/sh_1day.csv')
df_daily['Date'] = pd.to_datetime(df_daily['Date'])

analyzer = ChanAnalysisV34(df_1m=df_1m, df_5m=df_5m, df_daily=df_daily)
report = analyzer.generate_report()

print()
print('='*60)
print('【缠论多级别联立分析报告 v3.4】')
print('分析日期: 2026-05-28 (周四)')
print('标的: 上证指数(000001.SH)')
print('收盘: %.2f' % df_daily['Close'].iloc[-1])
print('='*60)

# 1. 数据完整性
print()
print('📊 【数据完整性检查】')
for level, data in report['data_integrity'].items():
    status = "✅" if data['usable'] else "❌"
    print(f'  {status} {level}: {data["total_rows"]}根')

# 2. 底背离/顶背离 - v3.4核心
print()
print('🔍 【底背离/顶背离检测 - v3.4核心】')
has_div = False
for level, data in report['divergence'].items():
    if level in ['1F','3F','5F','15F','30F','60F','日线','双日']:
        if data.get('has_bottom_divergence'):
            has_div = True
            print(f'  🟢 {level}: {data["bottom"]["description"]}')
        if data.get('has_top_divergence'):
            has_div = True
            print(f'  🔴 {level}: {data["top"]["description"]}')
if not has_div:
    print('  各级别未检测到显著背离')

# 3. 信号优先级 - v3.4核心
print()
print('⚖️ 【信号优先级判定 - v3.4核心】')
sp = report['signal_priority']
icon = '🟢' if sp['final_signal'] == '买点' else ('🔴' if sp['final_signal'] == '卖点' else '⚪')
print(f'  {icon} 最终信号: {sp["final_signal"]} ({sp["priority"]})')
print(f'  📌 裁决原因: {sp["reason"]}')
print(f'  📌 裁决来源: {sp["source"]}')
print(f'  📌 操作: {sp["action"]}')
if sp.get('override_second_sell'):
    print('  ⚠️ 底背离+联合支撑区信号优先于二卖成立!')

# 4. 情景推演 - v3.4核心
print()
print('📈 【情景推演/路径分析 - v3.4核心】')
sc = report['scenario']
print(f'  主推情景: {sc["primary_scenario"]}')
print(f'  {sc["recommendation"]}')
for s in sc['scenarios']:
    ic = '🟢' if s['name'] == '强势情景' else ('🟡' if s['name'] == '中性情景' else '🔴')
    print(f'\n  {ic} {s["name"]} (概率{s["probability"]})')
    print(f'     条件: {s["condition"]}')
    print(f'     路径: {s["path"]}')
    print(f'     操作: {s["action"]}')
    print(f'     止损: {s["stop_loss"]}')

# 5. 联合区
print()
print('🔗 【联合支撑/联合压制区】')
uz = report['unified_zone']
if uz.get('unified_zones'):
    for z in uz['unified_zones']:
        ic = '🛡️' if '支撑' in z['type'] else '⛰️'
        print(f'  {ic} {z["strength"]}: {z["description"]}')
else:
    print('  无显著联合区')

# 6. 二买/二卖
print()
print('🎯 【二买/二卖结构】')
for level, data in report['second_buy'].items():
    if level in ['15F','30F','日线']:
        ic = '✅' if data.get('is_valid') else '❌'
        print(f'  {ic} {level}: {data.get("type","")} → {data.get("action","")}')

# 7. 55线状态
print()
print('📈 【55线思维分析 - 关键级别】')
for level, data in report['55line_analysis'].items():
    if level in ['1F','3F','5F','15F','30F','60F','日线','双日']:
        ic = '✅' if '主涨段' in data['structure'] else ('❌' if '主跌段' in data['structure'] else '⚠️')
        print(f'  {ic} {level}: 价{data["price"]:.2f} vs MA55={data["ma55"]:.2f} | {data["structure"]}')

# 8. 传导链
print()
print('⚡ 【级别传导链】')
tc = report['transmission_chain']
ic = '🔴' if tc['direction'] == 'down' else ('🟢' if tc['direction'] == 'up' else '⚪')
print(f'  {ic} {tc["direction"].upper()} | {tc["description"]}')

# 9. 双日
print()
print('📅 【双日级别分析】')
dd = report['dual_day']
if dd.get('usable', True):
    ic = '❌' if dd.get('death_risk') else ('✅' if dd.get('trend') == 'bull' else '⚠️')
    print(f'  {ic} {dd["description"]}')
    print(f'  操作: {dd["action"]}')

# 10. 目标价
print()
print('🎯 【目标价推导】')
for level, data in report['target_price'].items():
    if level in ['30F','日线']:
        print(f'  {level}: 支撑{data["nearest_support"]:.2f} | 压力{data["nearest_resistance"]:.2f}')

# 核心结论
print()
print('='*60)
print('【核心结论 - 2026-05-28 v3.4】')
print('='*60)

sp = report['signal_priority']
scen = report['scenario']
dd = report['dual_day']
daily = report['55line_analysis'].get('日线', {})

print()
print(f'📌 最终裁决信号: {sp["final_signal"]} ({sp["priority"]})')
print(f'📌 裁决原因: {sp["reason"]}')
print(f'📌 主推情景: {scen["primary_scenario"]}')
print()
print(f'📌 战略级别(双日):')
print(f'   {dd.get("description", "")}')
print()
print(f'📌 战术级别(日线):')
print(f'   收盘{daily.get("price", 0):.2f} vs MA55={daily.get("ma55", 0):.2f}')
print(f'   {daily.get("structure", "")}')
print()
print(f'📌 v3.4 vs v3.3 关键差异:')
print(f'   · 底背离检测: {"✅ 检测到" if has_div else "❌ 未检测到"}')
print(f'   · 信号优先级: {sp["source"]}')
print(f'   · 情景推演: {len(scen["scenarios"])}种路径')

print()
print('='*60)
