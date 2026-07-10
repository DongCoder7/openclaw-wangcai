#!/root/.openclaw/workspace/venv/bin/python3
"""
北京君正2026年全年净利润计算（基于v4.0产品拆分 + 费用扣除）
"""
print("=" * 60)
print("北京君正 2026年全年净利润计算")
print("=" * 60)

# ========== Step 1: 2025年全年基期（来自年报）==========
print("\n【Step 1】2025年全年基期（年报数据）")
print("-" * 50)

# 2025年产品拆分（年报）
storage_2025 = 29.11    # 存储芯片全年
storage_dram_2025 = storage_2025 * 0.60   # 17.47亿
storage_sram_2025 = storage_2025 * 0.20   # 5.82亿
storage_nor_2025 = storage_2025 * 0.20    # 5.82亿
compute_2025 = 12.90    # 计算芯片全年
analog_2025 = 5.06      # 模拟芯片全年
other_2025 = 0.45       # 其他

revenue_2025 = 47.41    # 2025年总营收
profit_2025 = 3.76      # 2025年净利润
margin_2025 = 0.358     # 2025年毛利率

print(f"2025年总营收: {revenue_2025:.2f}亿")
print(f"2025年净利润: {profit_2025:.2f}亿")
print(f"2025年净利率: {profit_2025/revenue_2025*100:.1f}%")
print(f"\n分产品基期:")
print(f"  DRAM: {storage_dram_2025:.2f}亿")
print(f"  SRAM: {storage_sram_2025:.2f}亿")
print(f"  NOR Flash: {storage_nor_2025:.2f}亿")
print(f"  计算芯片: {compute_2025:.2f}亿")
print(f"  模拟与互联: {analog_2025:.2f}亿")

# ========== Step 2: 2026年全年预测（v4.0产品拆分）==========
print("\n【Step 2】2026年全年预测（产品拆分）")
print("-" * 50)

# 涨价+出货量假设（evidence来源见上文）
products = [
    ("DRAM", storage_dram_2025, 0.335, 0.10, 0.25),      # 毛利率33.5%，出货+10%，涨价+25%
    ("SRAM", storage_sram_2025, 0.335, 0.15, 0.20),      # 毛利率33.5%，出货+15%，涨价+20%
    ("NOR Flash", storage_nor_2025, 0.335, 0.12, 0.18),  # 毛利率33.5%，出货+12%，涨价+18%
    ("计算芯片", compute_2025, 0.324, 0.05, 0.35),       # 毛利率32.4%，出货+5%，涨价+35%
    ("模拟与互联", analog_2025, 0.511, 0.05, 0.05),      # 毛利率51.1%，出货+5%，涨价+5%
]

total_revenue_2026 = 0
total_gp_2026 = 0

for name, base, margin, vol, price in products:
    # 预测营收 = 基期 × (1+出货) × (1+涨价)
    revenue = base * (1 + vol) * (1 + price)
    
    # 预测毛利率 = 原毛利率 + 涨价 × (1-原毛利率)（成本不变时）
    margin_new = margin + price * (1 - margin)
    margin_new = max(0.05, min(0.95, margin_new))
    
    # 毛利
    gp = revenue * margin_new
    
    total_revenue_2026 += revenue
    total_gp_2026 += gp
    
    print(f"  {name}: {base:.2f}亿 → {revenue:.2f}亿 (×{(1+vol)*(1+price):.2f}), 毛利率{margin_new*100:.1f}%, 毛利{gp:.2f}亿")

print(f"\n  2026年预测总营收: {total_revenue_2026:.2f}亿")
print(f"  2026年预测总毛利: {total_gp_2026:.2f}亿")
print(f"  2026年预测毛利率: {total_gp_2026/total_revenue_2026*100:.1f}%")

# ========== Step 3: 费用扣除（从2025年财报推导）==========
print("\n【Step 3】费用扣除（成本结构分解）")
print("-" * 50)

# 2025年费用结构（从财报推导）
# 2025年：营收47.41亿，毛利16.96亿，净利润3.76亿
# 总费用 = 16.96 - 3.76 = 13.20亿
# 固定费用（年化）= 6.82亿（研发+管理+销售的固定部分）
# 变动费用率 = 13.9%

fixed_cost_2025 = 6.82      # 亿，年化固定费用
variable_rate = 0.139       # 变动费用率

# 2026年费用预测
# 固定费用增长+8%（人员扩张+股权激励）
fixed_cost_2026 = fixed_cost_2025 * 1.08   # 7.37亿
variable_cost_2026 = total_revenue_2026 * variable_rate  # 变动费用随营收增长
total_cost_2026 = fixed_cost_2026 + variable_cost_2026

print(f"  固定费用（2026E）: {fixed_cost_2026:.2f}亿 (2025年{fixed_cost_2025}亿 × 1.08)")
print(f"  变动费用（2026E）: {variable_cost_2026:.2f}亿 (营收{total_revenue_2026:.2f}亿 × {variable_rate*100:.1f}%)")
print(f"  总费用（2026E）: {total_cost_2026:.2f}亿")

# ========== Step 4: 净利润计算 ==========
print("\n【Step 4】净利润计算")
print("-" * 50)

# 税前利润
pre_tax_profit = total_gp_2026 - total_cost_2026
print(f"  税前利润 = 总毛利 - 总费用")
print(f"         = {total_gp_2026:.2f}亿 - {total_cost_2026:.2f}亿")
print(f"         = {pre_tax_profit:.2f}亿")

# 所得税（高新技术企业15%）
tax = pre_tax_profit * 0.15
print(f"\n  所得税（15%）: {tax:.2f}亿")

# 少数股东损益
minority = 0.05
print(f"  少数股东损益: {minority:.2f}亿")

# 最终净利润
net_profit = pre_tax_profit - tax - minority
net_margin = net_profit / total_revenue_2026

print(f"\n  ████████████████████████████████████████")
print(f"  █                                      █")
print(f"  █   2026年预测净利润: {net_profit:.2f}亿        █")
print(f"  █   2026年预测净利率: {net_margin*100:.1f}%          █")
print(f"  █   2026年预测营收: {total_revenue_2026:.2f}亿        █")
print(f"  █                                      █")
print(f"  ████████████████████████████████████████")

# ========== Step 5: 与2025年对比 ==========
print("\n【Step 5】同比对比")
print("-" * 50)

profit_growth = (net_profit - profit_2025) / profit_2025
revenue_growth = (total_revenue_2026 - revenue_2025) / revenue_2025

print(f"  2025年实际: 营收{revenue_2025:.2f}亿, 净利润{profit_2025:.2f}亿, 净利率{profit_2025/revenue_2025*100:.1f}%")
print(f"  2026年预测: 营收{total_revenue_2026:.2f}亿, 净利润{net_profit:.2f}亿, 净利率{net_margin*100:.1f}%")
print(f"\n  营收增长: {revenue_growth*100:+.1f}%")
print(f"  净利润增长: {profit_growth*100:+.1f}%")
print(f"  净利率提升: {(net_margin - profit_2025/revenue_2025)*100:+.1f}pct")

# ========== Step 6: Q2单季预测 ==========
print("\n【Step 6】2026年Q2单季净利润预测")
print("-" * 50)

# Q2产品拆分（基于Q1实际和涨价趋势）
q2_products = [
    ("DRAM", 10.18 * 0.60, 0.389, 0.05, 0.05),    # Q1 DRAM 6.11亿，Q2涨价+5%
    ("SRAM", 10.18 * 0.20, 0.389, 0.08, 0.05),    # Q1 SRAM 2.04亿，Q2出货+8%
    ("NOR Flash", 10.18 * 0.20, 0.389, 0.06, 0.05), # Q1 NOR 2.04亿，Q2出货+6%
    ("计算芯片", 4.03, 0.519, 0.03, 0.02),         # Q1计算4.03亿，Q2出货+3%
    ("模拟与互联", 1.32, 0.509, 0.05, 0.02),       # Q1模拟1.32亿，Q2出货+5%
]

q2_revenue = 0
q2_gp = 0
for name, base, margin, vol, price in q2_products:
    rev = base * (1 + vol) * (1 + price)
    margin_q2 = margin + price * (1 - margin)
    gp = rev * margin_q2
    q2_revenue += rev
    q2_gp += gp

# Q2费用
q2_fixed = fixed_cost_2026 / 4  # 固定费用季度均摊
q2_variable = q2_revenue * variable_rate
q2_pre_tax = q2_gp - q2_fixed - q2_variable
q2_tax = q2_pre_tax * 0.15
q2_net = q2_pre_tax - q2_tax - 0.0125

print(f"  Q2预测营收: {q2_revenue:.2f}亿")
print(f"  Q2预测毛利: {q2_gp:.2f}亿 (毛利率{q2_gp/q2_revenue*100:.1f}%)")
print(f"  Q2固定费用: {q2_fixed:.2f}亿")
print(f"  Q2变动费用: {q2_variable:.2f}亿")
print(f"  Q2税前利润: {q2_pre_tax:.2f}亿")
print(f"\n  ████████████████████████████████████████")
print(f"  █   2026年Q2预测净利润: {q2_net:.2f}亿    █")
print(f"  █   Q2净利率: {q2_net/q2_revenue*100:.1f}%              █")
print(f"  ████████████████████████████████████████")

print(f"\n  Q2同比验证:")
print(f"    2025Q2实际: 1.292亿")
print(f"    2026Q2预测: {q2_net:.2f}亿")
print(f"    同比增长: {(q2_net/1.292-1)*100:.1f}%")

# ========== Step 7: 估值 ==========
print("\n【Step 7】估值计算")
print("-" * 50)

price = 236.02
shares = 4.8366
cap = price * shares
pe = cap / net_profit

target_pe = 80
target_cap = net_profit * target_pe
target_price = target_cap / shares

print(f"  当前股价: {price}元")
print(f"  当前市值: {cap:.2f}亿")
print(f"  2026E净利润: {net_profit:.2f}亿")
print(f"  当前PE（2026E）: {pe:.1f}x")
print(f"\n  目标PE: {target_pe}x")
print(f"  目标市值: {target_cap:.2f}亿")
print(f"  目标价: {target_price:.2f}元")
print(f"  空间: {(target_price-price)/price*100:+.1f}%")

print("\n" + "=" * 60)
print("计算完成")
print("=" * 60)
