#!/root/.openclaw/workspace/venv/bin/python3
"""
北京君正Q2重新计算（使用配置好的v4.0 skill：segmented_forecaster.py）
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/segmented-business-forecast/scripts')

from segmented_forecaster import V4Forecaster, FinancialData

# 创建分析器（v4.0主脚本）
f = V4Forecaster("300223.SZ", "北京君正", year=2026)

# 使用2026Q1实际数据作为基期
fin = FinancialData(
    year=2026, quarter=1,
    revenue=15.60,
    profit=3.19,
    margin=0.431,
    net_margin=0.204,
    source="Tushare Pro + 长桥API（已验证）"
)
f.financial_data = fin

# 验证数据
f.validate_data()

# Q2产品拆分（涨价继续，出货量增长）
# 存储芯片Q1=10.18亿，Q2涨价+5%，出货+5%
# 计算芯片Q1=4.03亿，Q2涨价+3%，出货+3%
# 模拟芯片Q1=1.32亿，Q2涨价+2%，出货+5%

# 产品拆分比例（与Q1一致）
storage_total_q1 = 10.18
compute_total_q1 = 4.03
analog_total_q1 = 1.32

# DRAM/SRAM/NOR占比（存储内部拆分）
dram_q1 = storage_total_q1 * 0.60  # 6.11
sram_q1 = storage_total_q1 * 0.20  # 2.04
nor_q1 = storage_total_q1 * 0.20   # 2.04

# Q2涨价+出货量（evidence来源已确认）
f.add_product("DRAM", dram_q1, 0.389, 0.05, 0.05,
    "7月2日调研：Q2涨价继续+5%，出货量+5%（分货模式）")
f.add_product("SRAM", sram_q1, 0.389, 0.08, 0.05,
    "7月2日调研：DRAM缺货替代，Q2量价齐升+8%出货")
f.add_product("NOR Flash", nor_q1, 0.389, 0.06, 0.05,
    "7月2日调研：Q2涨价+5%，AI服务器/光模块出货+6%")
f.add_product("计算芯片", compute_total_q1, 0.519, 0.03, 0.03,
    "6月22日调研：KGD持续缺货，Q2涨价+3%，出货+3%")
f.add_product("模拟与互联", analog_total_q1, 0.509, 0.05, 0.02,
    "7月2日调研：稳定增长，Q2出货+5%，涨价+2%")

# 预测（v4.0公式：营收×(1+出货)×(1+涨价)，毛利率=原毛利率+涨价×(1-原毛利率)）
f.forecast()

# 获取预测结果
result = f.summarize()
forecast_revenue = result['forecast_revenue']
forecast_profit = result['forecast_profit']

# 但v4.0的forecast_profit是毛利，不是净利润。需要扣除费用
# 从Q1推导：Q1营收15.60亿，毛利6.72亿，净利润3.19亿
# Q1费用 = 6.72 - 3.19 = 3.53亿（含所得税）
# Q1费用率 = 3.53/15.60 = 22.6%

# Q2费用预测（费用率与Q1持平约22.6%）
q2_expense_rate = 0.226
q2_expense = forecast_revenue * q2_expense_rate
q2_net = forecast_profit - q2_expense  # 简化：毛利-费用=净利润（近似）

print("\n" + "="*60)
print("Q2预测结果（v4.0 skill）")
print("="*60)
print(f"  Q2预测营收: {forecast_revenue:.2f}亿")
print(f"  Q2预测毛利: {forecast_profit:.2f}亿")
print(f"  Q2费用率: {q2_expense_rate*100:.1f}%")
print(f"  Q2费用: {q2_expense:.2f}亿")
print(f"  Q2预测净利润: {q2_net:.2f}亿")
print(f"  Q2净利率: {q2_net/forecast_revenue*100:.1f}%")

# 全年预测
print("\n" + "="*60)
print("2026年全年净利润预测（v4.0 skill）")
print("="*60)

q1_net = 3.19  # 实际
q2_net_final = q2_net  # 预测
q3_net = q2_net * 1.03  # Q3涨价放缓
q4_net = q2_net * 1.00  # Q4持平

annual_net = q1_net + q2_net_final + q3_net + q4_net

print(f"  Q1（实际）: {q1_net:.2f}亿")
print(f"  Q2（预测）: {q2_net_final:.2f}亿")
print(f"  Q3（预测）: {q3_net:.2f}亿")
print(f"  Q4（预测）: {q4_net:.2f}亿")
print(f"\n  ████████████████████████████████████████")
print(f"  █   2026年全年预测净利润: {annual_net:.2f}亿 █")
print(f"  ████████████████████████████████████████")

# 保存报告
report = f.generate_markdown()
with open('/root/.openclaw/workspace/data/beijing_junzheng_q2_v4_final.md', 'w', encoding='utf-8') as f_out:
    f_out.write(report)
    f_out.write(f"\n\n## Q2净利润修正\n\n")
    f_out.write(f"- Q2预测营收: {forecast_revenue:.2f}亿\n")
    f_out.write(f"- Q2预测毛利: {forecast_profit:.2f}亿\n")
    f_out.write(f"- Q2费用率: {q2_expense_rate*100:.1f}%\n")
    f_out.write(f"- Q2预测净利润: {q2_net:.2f}亿\n")
    f_out.write(f"\n## 全年净利润\n\n")
    f_out.write(f"- 2026年全年预测净利润: {annual_net:.2f}亿\n")

print(f"\n  报告已保存: data/beijing_junzheng_q2_v4_final.md")
