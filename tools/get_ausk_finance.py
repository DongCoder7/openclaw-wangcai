#!/root/.openclaw/workspace/venv/bin/python3
"""获取奥士康财务数据 - 使用Tushare"""
import tushare as ts
import json
import os

# 设置Tushare token
ts.set_token('6a0eb5838a403ee4f96002f8bda70eb7c57a7e9db23f00d0c004af2e')
pro = ts.pro_api()

stock_code = '002913.SZ'

# 获取最新财务数据
print("=== 获取财务数据 ===")

# 1. 获取利润表（最近4个季度）
income = pro.income(ts_code=stock_code, period='20240930')
if not income.empty:
    q3_revenue = income.iloc[0]['total_revenue'] / 1e8  # 转为亿元
    q3_profit = income.iloc[0]['n_income'] / 1e8
    print(f"2024年Q3营收: {q3_revenue:.2f}亿元")
    print(f"2024年Q3净利润: {q3_profit:.2f}亿元")

# 2. 获取2023年年报数据
income_2023 = pro.income(ts_code=stock_code, period='20231231')
if not income_2023.empty:
    rev_2023 = income_2023.iloc[0]['total_revenue'] / 1e8
    profit_2023 = income_2023.iloc[0]['n_income'] / 1e8
    print(f"2023年营收: {rev_2023:.2f}亿元")
    print(f"2023年净利润: {profit_2023:.2f}亿元")

# 3. 获取2024年三季报累计数据
fina = pro.fina_indicator(ts_code=stock_code, period='20240930')
if not fina.empty:
    roe = fina.iloc[0]['roe']
    grossprofit = fina.iloc[0]['grossprofit_margin']
    netprofit = fina.iloc[0]['netprofit_margin']
    print(f"ROE: {roe:.2f}%")
    print(f"毛利率: {grossprofit:.2f}%")
    print(f"净利率: {netprofit:.2f}%")

# 4. 获取公司基本信息
basic = pro.stock_basic(ts_code=stock_code)
if not basic.empty:
    print(f"\n公司全称: {basic.iloc[0]['name']}")
    print(f"所属行业: {basic.iloc[0]['industry']}")
    print(f"主营业务: {basic.iloc[0]['area']}")

print("\n=== 基础数据汇总 ===")
result = {
    "stock_code": stock_code,
    "name": "奥士康",
    "industry": basic.iloc[0]['industry'] if not basic.empty else "PCB",
    "2023_revenue": round(rev_2023, 2) if 'rev_2023' in locals() else None,
    "2023_profit": round(profit_2023, 2) if 'profit_2023' in locals() else None,
    "q3_revenue": round(q3_revenue, 2) if 'q3_revenue' in locals() else None,
    "q3_profit": round(q3_profit, 2) if 'q3_profit' in locals() else None,
    "roe": round(roe, 2) if 'roe' in locals() else None,
    "gross_margin": round(grossprofit, 2) if 'grossprofit' in locals() else None,
    "net_margin": round(netprofit, 2) if 'netprofit' in locals() else None,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
