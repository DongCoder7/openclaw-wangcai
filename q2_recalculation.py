#!/root/.openclaw/workspace/venv/bin/python3
"""
北京君正Q2利润重新计算（用户质疑：Q1已3.19亿，Q2涨价继续，为什么Q2更低？）
"""
print("=" * 70)
print("Q2利润重新计算 — 回应用户质疑")
print("=" * 70)

# Q1实际数据（2026Q1财报）
q1_revenue = 15.60
q1_profit = 3.19
q1_gp = 6.72  # 毛利（来自财报：营收15.60 - 成本8.81 = 6.79亿，取6.72亿）
q1_margin = 0.431
q1_expense = q1_gp - q1_profit  # 3.53亿（含所得税）

print(f"\n【Q1实际数据】")
print(f"  营收: {q1_revenue:.2f}亿")
print(f"  毛利: {q1_gp:.2f}亿 (毛利率{q1_margin*100:.1f}%)")
print(f"  净利润: {q1_profit:.2f}亿")
print(f"  净利率: {q1_profit/q1_revenue*100:.1f}%")

# Q1费用拆解（从财报提取）
# 2026Q1费用：销售0.92 + 管理0.57 + 研发1.72 + 税金0.04 = 3.25亿
# 财务费用-1.41亿（利息收入）+ 其他收益0.22 + 投资收益0.04 + 公允价值0.03 = -1.12亿
# 实际费用 = 3.25 - 1.12 = 2.13亿（主营费用）
# 但利润总额 = 3.63亿，所得税0.43亿，净利润3.20亿

# 更精确：Q1主营业务费用
q1_main_expense = 3.25  # 销售+管理+研发+税金（不含财务/其他收益）
q1_non_main = -1.12     # 财务+其他收益+投资收益+公允价值（净收益）
q1_pre_tax = q1_gp - q1_main_expense + q1_non_main  # 6.72 - 3.25 + 1.12 = 4.59亿？
# 但财报利润总额 = 0.84亿？不对

# 从Exa获取的数据：
# 营业利润 = 363,081,692.10 = 3.63亿
# 利润总额 = 363,512,454.69 = 3.64亿
# 所得税 = 43,164,137.66 = 0.43亿
# 净利润 = 320,348,317.03 = 3.20亿
# 少数股东 = 1,368,999.48 = 0.01亿
# 归母净利润 = 318,979,317.55 = 3.19亿

q1_op_profit = 3.63  # 营业利润
q1_total_profit = 3.64  # 利润总额
q1_tax = 0.43
q1_net = 3.20  # 净利润
q1_parent_net = 3.19  # 归母净利润

print(f"\n【Q1利润表拆解】")
print(f"  营业利润: {q1_op_profit:.2f}亿")
print(f"  利润总额: {q1_total_profit:.2f}亿")
print(f"  所得税: {q1_tax:.2f}亿")
print(f"  净利润: {q1_net:.2f}亿")
print(f"  归母净利润: {q1_parent_net:.2f}亿")

# Q1主营业务费用（反向推导）
q1_main_cost = q1_gp - q1_op_profit  # 6.72 - 3.63 = 3.09亿
print(f"\n  主营业务费用: {q1_main_cost:.2f}亿")
print(f"  费用率: {q1_main_cost/q1_revenue*100:.1f}%")

# 这个费用率（19.8%）远低于2025年的27.8%，说明Q1费用异常低
# 原因：Q1研发费用1.72亿 vs 2025年Q1的1.76亿，基本持平
# 但2025年Q1营收只有10.60亿，费用率 = 3.25/10.60 = 30.7%
# 2026Q1费用率 = 3.25/15.60 = 20.8%
# 差异主要来自：营收增长导致费用率被摊薄（规模效应）

# ========== Q2重新预测（更合理） ==========
print(f"\n{'='*70}")
print("【Q2重新预测】")
print(f"{'='*70}")

# Q2产品拆分（涨价继续，毛利率提升）
# 存储：Q1 10.18亿 → Q2 11.20亿（+10%），毛利率从38.9%→42%（涨价+3.1pct）
# 计算：Q1 4.03亿 → Q2 4.23亿（+5%），毛利率从51.9%→53%（+1.1pct）
# 模拟：Q1 1.32亿 → Q2 1.39亿（+5%），毛利率从50.9%→52%（+1.1pct）

q2_dram_rev = 10.18 * 0.60 * 1.10 * 1.05  # 6.11 * 1.10 * 1.05 = 7.07亿
q2_sram_rev = 10.18 * 0.20 * 1.15 * 1.05  # 2.04 * 1.15 * 1.05 = 2.46亿
q2_nor_rev = 10.18 * 0.20 * 1.12 * 1.05   # 2.04 * 1.12 * 1.05 = 2.40亿
q2_compute_rev = 4.03 * 1.05 * 1.03       # 4.03 * 1.05 * 1.03 = 4.36亿
q2_analog_rev = 1.32 * 1.05 * 1.02         # 1.32 * 1.05 * 1.02 = 1.41亿

q2_revenue = q2_dram_rev + q2_sram_rev + q2_nor_rev + q2_compute_rev + q2_analog_rev

# Q2毛利率（涨价传导）
q2_dram_gp = q2_dram_rev * 0.42  # 毛利率42%
q2_sram_gp = q2_sram_rev * 0.42
q2_nor_gp = q2_nor_rev * 0.42
q2_compute_gp = q2_compute_rev * 0.53
q2_analog_gp = q2_analog_rev * 0.52

q2_gp = q2_dram_gp + q2_sram_gp + q2_nor_gp + q2_compute_gp + q2_analog_gp
q2_margin = q2_gp / q2_revenue

print(f"\n  Q2产品拆分:")
print(f"    DRAM: 营收{q2_dram_rev:.2f}亿, 毛利率42%, 毛利{q2_dram_gp:.2f}亿")
print(f"    SRAM: 营收{q2_sram_rev:.2f}亿, 毛利率42%, 毛利{q2_sram_gp:.2f}亿")
print(f"    NOR: 营收{q2_nor_rev:.2f}亿, 毛利率42%, 毛利{q2_nor_gp:.2f}亿")
print(f"    计算: 营收{q2_compute_rev:.2f}亿, 毛利率53%, 毛利{q2_compute_gp:.2f}亿")
print(f"    模拟: 营收{q2_analog_rev:.2f}亿, 毛利率52%, 毛利{q2_analog_gp:.2f}亿")
print(f"\n  Q2总营收: {q2_revenue:.2f}亿 (vs Q1 {q1_revenue:.2f}亿, +{(q2_revenue/q1_revenue-1)*100:.1f}%)")
print(f"  Q2总毛利: {q2_gp:.2f}亿 (毛利率{q2_margin*100:.1f}%)")

# Q2费用（关键：用户说得对，Q2费用不应该比Q1高太多）
# Q1主营业务费用3.09亿（销售+管理+研发+税金）
# Q2如果费用率与Q1持平（约20%），则：
q2_expense_rate = 0.20  # 假设Q2费用率与Q1持平（20%）
q2_expense = q2_revenue * q2_expense_rate

print(f"\n  Q2费用假设:")
print(f"    Q1费用率: {q1_main_cost/q1_revenue*100:.1f}%")
print(f"    Q2费用率: {q2_expense_rate*100:.1f}%（假设与Q1持平）")
print(f"    Q2费用: {q2_expense:.2f}亿")

# Q2利润
q2_op = q2_gp - q2_expense
q2_tax = q2_op * 0.15
q2_net = q2_op - q2_tax - 0.01

print(f"\n  Q2利润计算:")
print(f"    营业利润 = 毛利 - 费用 = {q2_gp:.2f} - {q2_expense:.2f} = {q2_op:.2f}亿")
print(f"    所得税 = {q2_tax:.2f}亿")
print(f"    少数股东 = 0.01亿")
print(f"\n  ████████████████████████████████████████")
print(f"  █   Q2预测净利润: {q2_net:.2f}亿          █")
print(f"  █   Q2净利率: {q2_net/q2_revenue*100:.1f}%              █")
print(f"  ████████████████████████████████████████")

# 对比
print(f"\n【Q2 vs Q1对比】")
print(f"  Q1实际: 营收{q1_revenue:.2f}亿, 净利润{q1_parent_net:.2f}亿, 净利率{q1_parent_net/q1_revenue*100:.1f}%")
print(f"  Q2预测: 营收{q2_revenue:.2f}亿, 净利润{q2_net:.2f}亿, 净利率{q2_net/q2_revenue*100:.1f}%")
print(f"  营收变化: {(q2_revenue/q1_revenue-1)*100:+.1f}%")
print(f"  净利润变化: {(q2_net/q1_parent_net-1)*100:+.1f}%")

# 全年预测（基于Q1实际 + Q2-Q4预测）
print(f"\n{'='*70}")
print("【2026年全年净利润预测】")
print(f"{'='*70}")

# Q1实际: 3.19亿
# Q2预测: q2_net亿
# Q3预测: 假设与Q2持平（涨价放缓）
# Q4预测: 假设与Q2持平（涨价趋缓）

q3_net = q2_net * 1.05  # Q3涨价继续，微增5%
q4_net = q2_net * 1.02  # Q4涨价趋缓，微增2%

annual_net = q1_parent_net + q2_net + q3_net + q4_net

print(f"\n  Q1（实际）: {q1_parent_net:.2f}亿")
print(f"  Q2（预测）: {q2_net:.2f}亿")
print(f"  Q3（预测）: {q3_net:.2f}亿（Q2 × 1.05）")
print(f"  Q4（预测）: {q4_net:.2f}亿（Q2 × 1.02）")
print(f"\n  ████████████████████████████████████████")
print(f"  █   2026年全年预测净利润: {annual_net:.2f}亿 █")
print(f"  ████████████████████████████████████████")

# 全年营收预测
annual_revenue = q1_revenue + q2_revenue + q2_revenue*1.05 + q2_revenue*1.02
print(f"\n  2026年全年预测营收: {annual_revenue:.2f}亿")
print(f"  2026年全年预测净利率: {annual_net/annual_revenue*100:.1f}%")

# 估值
print(f"\n{'='*70}")
print("【估值】")
print(f"{'='*70}")
price = 236.02
shares = 4.8366
cap = price * shares
pe = cap / annual_net

print(f"  当前市值: {cap:.2f}亿")
print(f"  2026E净利润: {annual_net:.2f}亿")
print(f"  当前PE（2026E）: {pe:.1f}x")

target_pe = 80
target_price = annual_net * target_pe / shares
print(f"\n  目标PE: {target_pe}x")
print(f"  目标价: {target_price:.2f}元")
print(f"  空间: {(target_price-price)/price*100:+.1f}%")

print(f"\n{'='*70}")
print("计算完成")
print(f"{'='*70}")
