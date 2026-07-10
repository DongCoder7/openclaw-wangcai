#!/root/.openclaw/workspace/venv/bin/python3
"""
北京君正Q2重新计算（用户纠正：涨价是Q2对比Q1的季度环比）
"""

print("=" * 70)
print("Q2利润计算 — 基于Q1实际数据，应用Q2季度环比变化")
print("=" * 70)

# ========== Q1实际数据（2026Q1财报）==========
print("\n【Q1实际数据（基期）】")
print("-" * 50)

q1_dram_rev = 10.18 * 0.60   # 6.11亿，毛利率38.9%
q1_sram_rev = 10.18 * 0.20   # 2.04亿，毛利率38.9%
q1_nor_rev = 10.18 * 0.20    # 2.04亿，毛利率38.9%
q1_compute_rev = 4.03         # 4.03亿，毛利率51.9%
q1_analog_rev = 1.32          # 1.32亿，毛利率50.9%

q1_total_rev = q1_dram_rev + q1_sram_rev + q1_nor_rev + q1_compute_rev + q1_analog_rev
q1_dram_gp = q1_dram_rev * 0.389
q1_sram_gp = q1_sram_rev * 0.389
q1_nor_gp = q1_nor_rev * 0.389
q1_compute_gp = q1_compute_rev * 0.519
q1_analog_gp = q1_analog_rev * 0.509
q1_total_gp = q1_dram_gp + q1_sram_gp + q1_nor_gp + q1_compute_gp + q1_analog_gp

q1_net = 3.19  # 实际净利润

print(f"  DRAM: 营收{q1_dram_rev:.2f}亿, 毛利{q1_dram_gp:.2f}亿 (毛利率38.9%)")
print(f"  SRAM: 营收{q1_sram_rev:.2f}亿, 毛利{q1_sram_gp:.2f}亿 (毛利率38.9%)")
print(f"  NOR: 营收{q1_nor_rev:.2f}亿, 毛利{q1_nor_gp:.2f}亿 (毛利率38.9%)")
print(f"  计算: 营收{q1_compute_rev:.2f}亿, 毛利{q1_compute_gp:.2f}亿 (毛利率51.9%)")
print(f"  模拟: 营收{q1_analog_rev:.2f}亿, 毛利{q1_analog_gp:.2f}亿 (毛利率50.9%)")
print(f"\n  Q1总营收: {q1_total_rev:.2f}亿")
print(f"  Q1总毛利: {q1_total_gp:.2f}亿 (毛利率{q1_total_gp/q1_total_rev*100:.1f}%)")
print(f"  Q1净利润: {q1_net:.2f}亿 (净利率{q1_net/q1_total_rev*100:.1f}%)")

# ========== Q2预测（Q2对比Q1的季度环比涨价+出货）==========
print("\n" + "=" * 70)
print("【Q2预测 — Q2对比Q1的季度变化】")
print("=" * 70)

# 用户纠正：涨价是Q2对比Q1的季度环比
# 基于调研纪要的Q2变化：
# DRAM: Q2继续涨价+5%（Q1已调价，Q2国内外跟涨）
# SRAM: Q2量价齐升，出货+8%，涨价+5%
# NOR: Q2连续涨价，出货+6%，涨价+5%
# 计算: KGD持续缺货，出货+3%，涨价+3%
# 模拟: 稳定增长，出货+5%，涨价+2%

q2_changes = [
    ("DRAM", q1_dram_rev, 0.389, 0.05, 0.05, "Q2涨价+5%（Q1已调，Q2跟涨）"),
    ("SRAM", q1_sram_rev, 0.389, 0.08, 0.05, "Q2出货+8%，涨价+5%（替代需求）"),
    ("NOR", q1_nor_rev, 0.389, 0.06, 0.05, "Q2出货+6%，涨价+5%"),
    ("计算", q1_compute_rev, 0.519, 0.03, 0.03, "Q2出货+3%，涨价+3%（KGD缺货）"),
    ("模拟", q1_analog_rev, 0.509, 0.05, 0.02, "Q2出货+5%，涨价+2%"),
]

q2_total_rev = 0
q2_total_gp = 0

print(f"\n{'产品':<10} {'Q1营收':>8} {'出货变化':>8} {'价格变化':>8} {'Q2营收':>8} {'Q2毛利率':>8} {'Q2毛利':>8}")
print("-" * 70)

for name, base_rev, base_margin, vol_chg, price_chg, evidence in q2_changes:
    # Q2营收 = Q1营收 × (1+出货变化) × (1+价格变化)
    q2_rev = base_rev * (1 + vol_chg) * (1 + price_chg)
    
    # Q2毛利率 = Q1毛利率 + 价格变化 × (1-Q1毛利率)
    # 涨价传导，成本不变
    q2_margin = base_margin + price_chg * (1 - base_margin)
    
    # Q2毛利
    q2_gp = q2_rev * q2_margin
    
    q2_total_rev += q2_rev
    q2_total_gp += q2_gp
    
    print(f"{name:<10} {base_rev:>8.2f} {vol_chg:>+7.1%} {price_chg:>+7.1%} {q2_rev:>8.2f} {q2_margin:>7.1%} {q2_gp:>8.2f}")
    print(f"{'':10} {evidence}")

print("-" * 70)
print(f"{'合计':<10} {q1_total_rev:>8.2f} {'':8} {'':8} {q2_total_rev:>8.2f} {q2_total_gp/q2_total_rev:>7.1%} {q2_total_gp:>8.2f}")

# ========== Q2费用和净利润 ==========
print("\n" + "=" * 70)
print("【Q2费用和净利润】")
print("=" * 70)

# Q1费用拆解（从财报）
# Q1营业利润 = 3.63亿
# Q1毛利 = 6.72亿
# Q1主营业务费用 = 6.72 - 3.63 = 3.09亿
q1_expense = q1_total_gp - 3.63  # 3.09亿
q1_expense_rate = q1_expense / q1_total_rev

print(f"\n  Q1主营业务费用: {q1_expense:.2f}亿 (费用率{q1_expense_rate*100:.1f}%)")

# Q2费用假设：费用率与Q1持平（约19.8%）
# 但Q2营收增长，费用有规模效应
# 保守假设：Q2费用率 = 19.5%（略低于Q1）
q2_expense_rate = 0.195
q2_expense = q2_total_rev * q2_expense_rate

# 或者更精确：固定费用季度均摊 + 变动费用
# 2025年固定费用6.82亿，季度均摊1.71亿
# 2026年固定费用增长8% = 7.37亿，季度均摊1.84亿
# 变动费用 = 营收 × 13.9%
q2_fixed = 6.82 * 1.08 / 4  # 1.84亿
q2_variable = q2_total_rev * 0.139
q2_total_expense = q2_fixed + q2_variable
q2_expense_rate_calc = q2_total_expense / q2_total_rev

print(f"\n  费用计算方式1（费用率法）：")
print(f"    Q2费用率: {q2_expense_rate*100:.1f}%")
print(f"    Q2费用: {q2_expense:.2f}亿")

print(f"\n  费用计算方式2（固定+变动）：")
print(f"    固定费用: {q2_fixed:.2f}亿")
print(f"    变动费用: {q2_variable:.2f}亿 (费率13.9%)")
print(f"    总费用: {q2_total_expense:.2f}亿")
print(f"    费用率: {q2_expense_rate_calc*100:.1f}%")

# 使用方式2（更精确）
q2_pre_tax = q2_total_gp - q2_total_expense
q2_tax = q2_pre_tax * 0.15
q2_net = q2_pre_tax - q2_tax - 0.0125

print(f"\n  Q2利润计算（使用固定+变动方式）：")
print(f"    Q2营收: {q2_total_rev:.2f}亿")
print(f"    Q2毛利: {q2_total_gp:.2f}亿 (毛利率{q2_total_gp/q2_total_rev*100:.1f}%)")
print(f"    Q2费用: {q2_total_expense:.2f}亿")
print(f"    税前利润: {q2_pre_tax:.2f}亿")
print(f"    所得税: {q2_tax:.2f}亿")
print(f"    少数股东: 0.01亿")

print(f"\n  ████████████████████████████████████████")
print(f"  █                                      █")
print(f"  █   Q2预测净利润: {q2_net:.2f}亿          █")
print(f"  █   Q2净利率: {q2_net/q2_total_rev*100:.1f}%              █")
print(f"  █                                      █")
print(f"  ████████████████████████████████████████")

# ========== Q2 vs Q1对比 ==========
print("\n" + "=" * 70)
print("【Q2 vs Q1对比】")
print("=" * 70)

print(f"\n  营收: {q1_total_rev:.2f}亿 → {q2_total_rev:.2f}亿 (+{(q2_total_rev/q1_total_rev-1)*100:.1f}%)")
print(f"  毛利: {q1_total_gp:.2f}亿 → {q2_total_gp:.2f}亿 (+{(q2_total_gp/q1_total_gp-1)*100:.1f}%)")
print(f"  费用: {q1_expense:.2f}亿 → {q2_total_expense:.2f}亿 (+{(q2_total_expense/q1_expense-1)*100:.1f}%)")
print(f"  净利润: {q1_net:.2f}亿 → {q2_net:.2f}亿 (+{(q2_net/q1_net-1)*100:.1f}%)")

# ========== 全年预测 ==========
print("\n" + "=" * 70)
print("【2026年全年净利润预测】")
print("=" * 70)

# Q1实际: 3.19亿
# Q2预测: q2_net亿
# Q3预测: 假设Q3涨价放缓，与Q2持平或微增
# Q4预测: 假设Q4涨价趋缓，与Q2持平

q3_net = q2_net * 1.03  # Q3微增3%
q4_net = q2_net * 1.00  # Q4持平

annual_net = q1_net + q2_net + q3_net + q4_net

print(f"\n  Q1（实际）: {q1_net:.2f}亿")
print(f"  Q2（预测）: {q2_net:.2f}亿")
print(f"  Q3（预测）: {q3_net:.2f}亿（Q2 × 1.03）")
print(f"  Q4（预测）: {q4_net:.2f}亿（Q2 × 1.00）")

print(f"\n  ████████████████████████████████████████")
print(f"  █   2026年全年预测净利润: {annual_net:.2f}亿 █")
print(f"  ████████████████████████████████████████")

# ========== 估值 ==========
print("\n" + "=" * 70)
print("【估值】")
print("=" * 70)

price = 236.02
shares = 4.8366
cap = price * shares
pe = cap / annual_net

target_pe = 80
target_price = annual_net * target_pe / shares

print(f"\n  当前股价: {price}元")
print(f"  当前市值: {cap:.2f}亿")
print(f"  2026E净利润: {annual_net:.2f}亿")
print(f"  当前PE（2026E）: {pe:.1f}x")
print(f"\n  目标PE: {target_pe}x")
print(f"  目标价: {target_price:.2f}元")
print(f"  空间: {(target_price-price)/price*100:+.1f}%")

print("\n" + "=" * 70)
print("计算完成")
print("=" * 70)
