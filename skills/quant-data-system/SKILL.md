---
name: quant-data-system
description: |
  量化数据系统 - 全栈量化投资平台
  
  核心功能:
  1. 数据补充 - 补充2018-2024年完整技术指标、财务因子、估值数据
  2. WFO回测 - 滚动窗口优化策略参数，防止过拟合
  3. 模拟盘 - 实时跟踪策略表现，生成交易信号
  4. 数据质量监控 - 检查数据完整性、一致性
  
  数据覆盖:
  - 技术指标: RSI, MACD, 收益率, 波动率 (2018-2024)
  - 财务因子: ROE, 杜邦分析, 净利率, 毛利率 (2018-2024)
  - 估值因子: PE, PB, PS (2018-2024)
  - 覆盖股票: 4500+只A股
  
  WFO策略:
  - 训练期: 3年滚动窗口
  - 验证期: 1年
  - 优化目标: 夏普比率 + 最大回撤
  
  模拟盘功能:
  - 每日收盘后生成持仓建议
  - 跟踪持仓收益
  - 记录交易记录
  
  触发方式:
  - 数据补充: 手动执行 supplement_data.py
  - WFO回测: 手动执行 wfo_backtest.py
  - 模拟盘: 每日收盘后自动运行 (由Heartbeat触发)
---

# 量化数据系统 (Quant Data System)

## 功能模块

### 1. 数据补充 (supplement_data.py)

**补充范围**: 2018-2024年完整数据

**技术指标** (stock_technical_factors):
- RSI (6, 14, 24)
- MACD (12, 26, 9)
- 收益率 (20, 60, 120日)
- 波动率 (20, 60, 120日)
- 价格位置 (20, 60日)

**财务因子** (stock_fina_tushare):
- ROE (净资产收益率)
- ROE杜邦分析
- 净利率、毛利率
- 资产周转率
- 营收增长率
- 净利润增长率
- 资产负债率
- 流动比率、速动比率

**估值因子** (stock_fina):
- PE_TTM (市盈率TTM)
- PB (市净率)
- PS (市销率)

### 2. WFO回测 (wfo_backtest.py)

**WFO (Walk-Forward Optimization)** 防止过拟合:
- 训练期: 3年滚动窗口
- 验证期: 1年
- 步长: 1年

**优化目标**:
- 最大化夏普比率
- 最小化最大回撤
- 约束条件: 年化波动率 < 30%

**策略框架**:
- 多因子打分模型
- 因子权重优化
- 动态调仓

### 3. 模拟盘 (sim_portfolio.py)

**功能**:
- 每日收盘后生成持仓建议
- 根据WFO最优参数选股
- 计算目标仓位
- 生成交易清单

**输出**:
- 持仓股票列表
- 每只股票的权重
- 买入/卖出建议
- 预期收益/风险

## 使用方法

### 数据补充
```bash
cd ~/.openclaw/workspace
python3 skills/quant-data-system/scripts/supplement_data.py
```

### WFO回测
```bash
cd ~/.openclaw/workspace
python3 skills/quant-data-system/scripts/wfo_backtest.py
```

### 模拟盘
```bash
# 手动执行
cd ~/.openclaw/workspace
python3 skills/quant-data-system/scripts/sim_portfolio.py

# 或由Heartbeat自动触发 (每日收盘后)
```

## 数据表结构

### stock_technical_factors
```sql
CREATE TABLE stock_technical_factors (
    ts_code TEXT,
    trade_date TEXT,
    close REAL,
    rsi_14 REAL,
    rsi_6 REAL,
    rsi_24 REAL,
    macd REAL,
    macd_signal REAL,
    macd_hist REAL,
    update_time TEXT,
    PRIMARY KEY (ts_code, trade_date)
);
```

### stock_fina_tushare
```sql
CREATE TABLE stock_fina_tushare (
    ts_code TEXT,
    year INTEGER,
    quarter INTEGER,
    report_date TEXT,
    roe REAL,
    roe_diluted REAL,
    roe_avg REAL,
    netprofit_yoy REAL,
    dt_netprofit_yoy REAL,
    revenue_yoy REAL,
    grossprofit_margin REAL,
    netprofit_margin REAL,
    assets_turn REAL,
    op_yoy REAL,
    ebit_yoy REAL,
    debt_to_assets REAL,
    current_ratio REAL,
    quick_ratio REAL,
    update_time TEXT,
    PRIMARY KEY (ts_code, year, quarter)
);
```

## 产出文件

- 数据补充日志: `reports/data_supplement_YYYYMMDD.log`
- WFO回测报告: `reports/wfo_backtest_YYYYMMDD.json`
- 模拟盘持仓: `reports/sim_portfolio_YYYYMMDD.json`
- 交易记录: `reports/trade_history.json`

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| 1.0 | 2026-02-28 | 初始版本，数据补充+WFO+模拟盘 |

## 风险提示

⚠️ 本系统仅供参考，不构成投资建议。股市有风险，投资需谨慎。
- 历史数据不代表未来表现
- WFO回测可能仍存在过拟合风险
- 模拟盘收益不等于实际收益
