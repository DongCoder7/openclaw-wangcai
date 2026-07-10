#!/root/.openclaw/workspace/venv/bin/python3
"""
北京君正Q2重新计算（用户纠正：涨价是Q2对比Q1的季度环比）

核心理解：
- v4.0的基期是Q1（15.53亿营收，6.72亿毛利）
- price_change和volume_growth是Q2对比Q1的季度变化
- 不是全年变化，不是2025→2026的年同比
"""

print("=" * 70)
print("Q2利润重新计算 — 涨价是Q2对比Q1的季度环比")
print("=" * 70)

# ========== Q1实际数据（2026Q1财报）==========
print("\n【Q1实际数据（基期）】")
print("-" * 50)

q1_dram_rev = 10.18 * 0.60   # 6.11亿
q1_sram_rev = 10.18 * 0.20   # 2.04亿
q1_nor_rev = 10.18 * 0.20    # 2.04亿
q1_compute_rev = 4.03         # 4.03亿
q1_analog_rev = 1.32          # 1.32亿

q1_total_rev = q1_dram_rev + q1_sram_rev + q1_nor_rev + q1_compute_rev + q1_analog_rev
q1_total_gp = q1_dram_rev*0.389 + q1_sram_rev*0.389 + q1_nor_rev*0.389 + q1_compute_rev*0.519 + q1_analog_rev*0.509

q1_net = 3.19  # 实际净利润

print(f"  Q1总营收: {q1_total_rev:.2f}亿")
print(f"  Q1总毛利: {q1_total_gp:.2f}亿 (毛利率{q1_total_gp/q1_total_rev*100:.1f}%)")
print(f"  Q1净利润: {q1_net:.2f}亿 (净利率{q1_net/q1_total_rev*100:.1f}%)")

# ========== Q2预测（Q2对比Q1的季度环比）==========
print("\n" + "=" * 70)
print("【Q2预测 — Q2对比Q1的季度变化】")
print("=" * 70)

# v4.0的涨价和出货量假设（季度环比）
q2_products = [
    ("DRAM", q1_dram_rev, 0.389, 0.10, 0.25),      # 出货+10%，涨价+25%
    ("SRAM", q1_sram_rev, 0.389, 0.15, 0.20),      # 出货+15%，涨价+20%
    ("NOR", q1_nor_rev, 0.389, 0.12, 0.18),        # 出货+12%，涨价+18%
    ("计算", q1_compute_rev, 0.519, 0.05, 0.35),    # 出货+5%，涨价+35%
    ("模拟", q1_analog_rev, 0.509, 0.05, 0.05),     # 出货+5%，涨价+5%
]

q2_total_rev = 0
q2_total_gp = 0

print(f"\n{'产品':<8} {'Q1营收':>8} {'出货':>6} {'涨价':>6} {'Q2营收':>8} {'毛利率':>8} {'Q2毛利':>8}")
print("-" * 60)

for name, base_rev, base_margin, vol, price in q2_products:
    # Q2营收 = Q1营收 × (1+出货) × (1+涨价)
    q2_rev = base_rev * (1 + vol) * (1 + price)
    
    # Q2毛利率 = 原毛利率 + 涨价×(1-原毛利率)
    q2_margin = base_margin + price * (1 - base_margin)
    
    # Q2毛利
    q2_gp = q2_rev * q2_margin
    
    q2_total_rev += q2_rev
    q2_total_gp += q2_gp
    
    print(f"{name:<8} {base_rev:>8.2f} {vol:>+5.0%} {price:>+5.0%} {q2_rev:>8.2f} {q2_margin:>7.1%} {q2_gp:>8.2f}")

print("-" * 60)
print(f"{'合计':<8} {q1_total_rev:>8.2f} {'':6} {'':6} {q2_total_rev:>8.2f} {q2_total_gp/q2_total_rev:>7.1%} {q2_total_gp:>8.2f}")

print(f"\n  Q2营收增长: {(q2_total_rev/q1_total_rev-1)*100:.1f}%")
print(f"  Q2毛利增长: {(q2_total_gp/q1_total_gp-1)*100:.1f}%")

# ========== Q2费用和净利润 ==========
print("\n" + "=" * 70)
print("【Q2费用和净利润】")
print("=" * 70)

# 2025年固定费用6.82亿，2026年增长8% = 7.37亿，季度均摊1.84亿
q2_fixed = 6.82 * 1.08 / 4
# 变动费用 = Q2营收 × 13.9%
q2_variable = q2_total_rev * 0.139
q2_total_expense = q2_fixed + q2_variable

print(f"\n  固定费用: {q2_fixed:.2f}亿")
print(f"  变动费用: {q2_variable:.2f}亿 (营收{q2_total_rev:.2f} × 13.9%)")
print(f"  总费用: {q2_total_expense:.2f}亿")

q2_pre_tax = q2_total_gp - q2_total_expense
q2_tax = q2_pre_tax * 0.15
q2_net = q2_pre_tax - q2_tax - 0.05

print(f"\n  税前利润: {q2_pre_tax:.2f}亿")
print(f"  所得税: {q2_tax:.2f}亿")
print(f"  少数股东: 0.05亿")

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
print(f"  费用: 3.53亿 → {q2_total_expense:.2f}亿 (+{(q2_total_expense/3.53-1)*100:.1f}%)")
print(f"  净利润: {q1_net:.2f}亿 → {q2_net:.2f}亿 (+{(q2_net/q1_net-1)*100:.1f}%)")

# ========== 全年预测 ==========
print("\n" + "=" * 70)
print("【2026年全年净利润预测】")
print("=" * 70)

q3_net = q2_net * 0.95  # Q3涨价放缓，略低于Q2
q4_net = q2_net * 0.90  # Q4涨价趋缓

annual_net = q1_net + q2_net + q3_net + q4_net

print(f"\n  Q1（实际）: {q1_net:.2f}亿")
print(f"  Q2（预测）: {q2_net:.2f}亿")
print(f"  Q3（预测）: {q3_net:.2f}亿（Q2 × 0.95）")
print(f"  Q4（预测）: {q4_net:.2f}亿（Q2 × 0.90）")

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
