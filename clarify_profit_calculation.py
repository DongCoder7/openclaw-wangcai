#!/root/.openclaw/workspace/venv/bin/python3
"""
北京君正Q2利润重新计算 — 用户质疑：毛利增长大但净利增长小？

用户的质疑："q2毛利润增加了79% 净利润只增加了0.9亿也就3%？你觉得合理吗？"

我需要澄清：
1. 用户可能混淆了全年和季度数据
2. 或者混淆了营收和毛利
3. 需要做一个最清晰的表格

全年数据 vs Q2数据的对比
"""

print("=" * 70)
print("全年数据对比（2025年 vs 2026年预测）")
print("=" * 70)

# 2025年全年实际（年报）
rev_2025 = 47.41
gp_2025 = 16.96  # 毛利（存储29.11*0.335 + 计算12.90*0.324 + 模拟5.06*0.511）
fixed_2025 = 6.82
variable_rate = 0.139
variable_2025 = rev_2025 * variable_rate
total_cost_2025 = fixed_2025 + variable_2025
tax_2025 = (gp_2025 - total_cost_2025) * 0.15
net_2025 = gp_2025 - total_cost_2025 - tax_2025 - 0.05

print(f"\n2025年全年（实际）：")
print(f"  营收: {rev_2025:.2f}亿")
print(f"  毛利: {gp_2025:.2f}亿 (毛利率{gp_2025/rev_2025*100:.1f}%)")
print(f"  固定费用: {fixed_2025:.2f}亿")
print(f"  变动费用: {variable_2025:.2f}亿 (费率{variable_rate*100:.1f}%)")
print(f"  总费用: {total_cost_2025:.2f}亿")
print(f"  税前利润: {gp_2025 - total_cost_2025:.2f}亿")
print(f"  所得税: {tax_2025:.2f}亿")
print(f"  净利润: {net_2025:.2f}亿 (净利率{net_2025/rev_2025*100:.1f}%)")

# 2026年全年预测（产品拆分）
# DRAM: 17.47 * 1.10 * 1.25 = 24.02亿, 毛利率50.1%
# SRAM: 5.82 * 1.15 * 1.20 = 8.03亿, 毛利率46.8%
# NOR: 5.82 * 1.12 * 1.18 = 7.69亿, 毛利率45.5%
# 计算: 12.90 * 1.05 * 1.35 = 18.29亿, 毛利率56.1%
# 模拟: 5.06 * 1.05 * 1.05 = 5.58亿, 毛利率53.5%

rev_2026 = 24.02 + 8.03 + 7.69 + 18.29 + 5.58
gp_2026 = 24.02*0.501 + 8.03*0.468 + 7.69*0.455 + 18.29*0.561 + 5.58*0.535
fixed_2026 = fixed_2025 * 1.08
variable_2026 = rev_2026 * variable_rate
total_cost_2026 = fixed_2026 + variable_2026
tax_2026 = (gp_2026 - total_cost_2026) * 0.15
net_2026 = gp_2026 - total_cost_2026 - tax_2026 - 0.05

print(f"\n2026年全年（预测）：")
print(f"  营收: {rev_2026:.2f}亿")
print(f"  毛利: {gp_2026:.2f}亿 (毛利率{gp_2026/rev_2026*100:.1f}%)")
print(f"  固定费用: {fixed_2026:.2f}亿")
print(f"  变动费用: {variable_2026:.2f}亿")
print(f"  总费用: {total_cost_2026:.2f}亿")
print(f"  税前利润: {gp_2026 - total_cost_2026:.2f}亿")
print(f"  所得税: {tax_2026:.2f}亿")
print(f"  净利润: {net_2026:.2f}亿 (净利率{net_2026/rev_2026*100:.1f}%)")

print(f"\n全年变化：")
print(f"  营收: {rev_2025:.2f}亿 → {rev_2026:.2f}亿 (+{(rev_2026/rev_2025-1)*100:.1f}%)")
print(f"  毛利: {gp_2025:.2f}亿 → {gp_2026:.2f}亿 (+{(gp_2026/gp_2025-1)*100:.1f}%)")
print(f"  费用: {total_cost_2025:.2f}亿 → {total_cost_2026:.2f}亿 (+{(total_cost_2026/total_cost_2025-1)*100:.1f}%)")
print(f"  净利润: {net_2025:.2f}亿 → {net_2026:.2f}亿 (+{(net_2026/net_2025-1)*100:.1f}%)")

print("\n" + "=" * 70)
print("Q2单季数据对比（Q1实际 vs Q2预测）")
print("=" * 70)

# Q1实际（2026Q1财报）
q1_rev = 15.60
q1_gp = 6.72
q1_fixed = fixed_2025 / 4  # 1.71亿（季度均摊）
q1_variable = q1_rev * variable_rate  # 2.17亿
q1_total_cost = q1_fixed + q1_variable
q1_tax = (q1_gp - q1_total_cost) * 0.15
q1_net = q1_gp - q1_total_cost - q1_tax - 0.0125

print(f"\n2026年Q1（实际）：")
print(f"  营收: {q1_rev:.2f}亿")
print(f"  毛利: {q1_gp:.2f}亿 (毛利率{q1_gp/q1_rev*100:.1f}%)")
print(f"  固定费用: {q1_fixed:.2f}亿")
print(f"  变动费用: {q1_variable:.2f}亿")
print(f"  总费用: {q1_total_cost:.2f}亿")
print(f"  税前利润: {q1_gp - q1_total_cost:.2f}亿")
print(f"  所得税: {(q1_gp - q1_total_cost)*0.15:.2f}亿")
print(f"  净利润: {q1_net:.2f}亿 (净利率{q1_net/q1_rev*100:.1f}%)")

# Q2预测（产品拆分）
# 存储Q1=10.18亿 → Q2=10.18*1.05*1.05=11.22亿（出货+5%，涨价+5%）
# 计算Q1=4.03亿 → Q2=4.03*1.03*1.03=4.28亿
# 模拟Q1=1.32亿 → Q2=1.32*1.05*1.02=1.41亿

q2_rev = 11.22 + 4.28 + 1.41
# Q2毛利率提升：存储42%（vs Q1 38.9%），计算53%（vs Q1 51.9%），模拟52%（vs Q1 50.9%）
q2_gp_detail = 11.22*0.42 + 4.28*0.53 + 1.41*0.52
q2_fixed = fixed_2026 / 4  # 1.84亿
q2_variable = q2_rev * variable_rate
q2_total_cost = q2_fixed + q2_variable
q2_tax = (q2_gp_detail - q2_total_cost) * 0.15
q2_net = q2_gp_detail - q2_total_cost - q2_tax - 0.0125

print(f"\n2026年Q2（预测）：")
print(f"  营收: {q2_rev:.2f}亿")
print(f"  毛利: {q2_gp_detail:.2f}亿 (毛利率{q2_gp_detail/q2_rev*100:.1f}%)")
print(f"  固定费用: {q2_fixed:.2f}亿")
print(f"  变动费用: {q2_variable:.2f}亿")
print(f"  总费用: {q2_total_cost:.2f}亿")
print(f"  税前利润: {q2_gp_detail - q2_total_cost:.2f}亿")
print(f"  所得税: {(q2_gp_detail - q2_total_cost)*0.15:.2f}亿")
print(f"  净利润: {q2_net:.2f}亿 (净利率{q2_net/q2_rev*100:.1f}%)")

print(f"\nQ2变化：")
print(f"  营收: {q1_rev:.2f}亿 → {q2_rev:.2f}亿 (+{(q2_rev/q1_rev-1)*100:.1f}%)")
print(f"  毛利: {q1_gp:.2f}亿 → {q2_gp_detail:.2f}亿 (+{(q2_gp_detail/q1_gp-1)*100:.1f}%)")
print(f"  费用: {q1_total_cost:.2f}亿 → {q2_total_cost:.2f}亿 (+{(q2_total_cost/q1_total_cost-1)*100:.1f}%)")
print(f"  净利润: {q1_net:.2f}亿 → {q2_net:.2f}亿 (+{(q2_net/q1_net-1)*100:.1f}%)")

print("\n" + "=" * 70)
print("关键结论")
print("=" * 70)

print(f"""
全年：
  毛利增长 +{(gp_2026/gp_2025-1)*100:.1f}%（+{gp_2026-gp_2025:.2f}亿）
  费用增长 +{(total_cost_2026/total_cost_2025-1)*100:.1f}%（+{total_cost_2026-total_cost_2025:.2f}亿）
  净利润增长 +{(net_2026/net_2025-1)*100:.1f}%（+{net_2026-net_2025:.2f}亿）

Q2：
  毛利增长 +{(q2_gp_detail/q1_gp-1)*100:.1f}%（+{q2_gp_detail-q1_gp:.2f}亿）
  费用增长 +{(q2_total_cost/q1_total_cost-1)*100:.1f}%（+{q2_total_cost-q1_total_cost:.2f}亿）
  净利润增长 +{(q2_net/q1_net-1)*100:.1f}%（+{q2_net-q1_net:.2f}亿）

解释：
  1. 毛利增长快于费用增长（固定费用不随营收线性增长）
  2. 毛利率提升（涨价传导）+ 费用率摊薄（规模效应）
  3. 净利润增速 > 毛利增速，这是合理的经营杠杆效应
""")

print("=" * 70)
