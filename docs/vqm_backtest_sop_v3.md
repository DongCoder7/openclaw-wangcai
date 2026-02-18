# VQM策略完整回测SOP（线上环境模拟版）

> **版本**: v3.0 - 完整版  
> **更新日期**: 2026-02-14  
> **核心要求**: 完全模拟线上环境 + 本地数据存储 + 逐步优化

---

## 一、系统架构

### 1.1 整体流程

```
阶段1: 数据采集（一次性）
├── 股票池：沪深300 + 中证500 + 中证1000 = 1000只
├── 数据类型：日线（开高低收量）+ 估值（PE/PB）+ 财务（ROE）
├── 时间跨度：2018-01-01 ~ 2024-12-31
└── 存储方式：SQLite本地数据库

阶段2: 回测执行（迭代优化）
├── 每月第一个交易日建仓
├── 持仓3年或触发止损
├── 日级调仓决策
└── 逐步优化策略参数

阶段3: 结果分析
├── 胜率/盈亏比/夏普比率
├── 最大回撤/年化收益
├── 参数稳健性检验
└── 生成优化建议
```

### 1.2 数据存储结构

```sql
-- 股票日度数据表
stock_daily (
    date TEXT,           -- 日期
    code TEXT,           -- 股票代码
    name TEXT,           -- 股票名称
    open REAL,           -- 开盘价
    high REAL,           -- 最高价
    low REAL,            -- 最低价
    close REAL,          -- 收盘价（前复权）
    volume REAL,         -- 成交量
    pe REAL,             -- 市盈率
    pb REAL,             -- 市净率
    market_cap REAL,     -- 市值
    PRIMARY KEY (date, code)
)

-- 宏观数据表
macro_data (
    date TEXT PRIMARY KEY,
    cpi_yoy REAL,        -- CPI同比
    ppi_yoy REAL,        -- PPI同比
    pmi REAL,            -- PMI
    m2_yoy REAL,         -- M2同比
    lpr_1y REAL,         -- 1年期LPR
    lpr_5y REAL,         -- 5年期LPR
    sh_index REAL,       -- 上证指数
    sz_index REAL        -- 深证指数
)

-- 回测结果表
backtest_results (
    id INTEGER PRIMARY KEY,
    start_date TEXT,     -- 建仓日期
    entry_date TEXT,     -- 入场日期
    exit_date TEXT,      -- 出场日期
    initial_capital REAL,-- 初始资金
    final_value REAL,    -- 最终市值
    total_return REAL,   -- 总收益
    annual_return REAL,  -- 年化收益
    max_drawdown REAL,   -- 最大回撤
    sharpe_ratio REAL,   -- 夏普比率
    stocks_selected TEXT,-- 选中股票JSON
    trades TEXT,         -- 交易记录JSON
    params TEXT          -- 策略参数JSON
)
```

---

## 二、数据采集SOP

### 2.1 股票数据获取

```python
def download_stock_data(code: str, start_date: str, end_date: str):
    """
    下载单只股票历史数据
    
    API: ak.stock_zh_a_hist()
    参数:
        - symbol: 股票代码
        - period: daily
        - adjust: qfq (前复权)
    """
    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq"
    )
    return df
```

### 2.2 估值数据获取

```python
def download_valuation_data(date: str):
    """
    下载全市场估值数据
    
    API: ak.stock_zh_a_spot_em()
    获取字段:
        - 市盈率-动态 (PE)
        - 市净率 (PB)
        - 总市值
    """
    df = ak.stock_zh_a_spot_em()
    return df[['代码', '名称', '最新价', '市盈率-动态', '市净率', '总市值']]
```

### 2.3 财务数据获取

```python
def download_financial_data(code: str):
    """
    下载财务指标数据
    
    API: ak.stock_financial_analysis_indicator()
    获取字段:
        - 净资产收益率 (ROE)
        - 每股收益
        - 营业收入
    """
    df = ak.stock_financial_analysis_indicator(symbol=code)
    return df
```

### 2.4 宏观数据获取

```python
def download_macro_data():
    """
    下载宏观数据
    
    CPI: ak.macro_china_cpi_monthly()
    PPI: ak.macro_china_ppi_yearly()
    PMI: ak.macro_china_pmi_yearly()
    M2: ak.macro_china_m2_yearly()
    LPR: ak.macro_china_lpr()
    """
    data = {
        'cpi': ak.macro_china_cpi_monthly(),
        'ppi': ak.macro_china_ppi_yearly(),
        'pmi': ak.macro_china_pmi_yearly(),
        'm2': ak.macro_china_m2_yearly(),
        'lpr': ak.macro_china_lpr()
    }
    return data
```

---

## 三、回测执行SOP

### 3.1 每月建仓流程

```python
def monthly_backtest_step(year: int, month: int, params: Dict):
    """
    单月回测步骤
    
    流程:
    1. 确定建仓日期（每月第一个交易日）
    2. 读取当日股票数据（从本地数据库）
    3. 计算VQM得分
    4. 选出前10只股票
    5. 等权重建仓（分批买入）
    6. 模拟持仓3年或触发止损
    7. 记录交易和收益
    """
    
    # 步骤1: 建仓日期
    entry_date = get_first_trading_day(year, month)
    
    # 步骤2: 读取数据
    stocks = read_stock_data_from_db(entry_date)
    
    # 步骤3: VQM选股
    selected = select_stocks_vqm(stocks, params)
    
    # 步骤4: 模拟交易
    result = simulate_trading(selected, entry_date, params)
    
    # 步骤5: 保存结果
    save_result(result)
    
    return result
```

### 3.2 VQM选股逻辑

```python
def select_stocks_vqm(stocks_df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """
    VQM选股
    
    公式:
    - PE排名 = PE在股票池中的百分位排名（越低越好）
    - ROE排名 = ROE在股票池中的百分位排名（越高越好）
    - VQM得分 = PE排名 × PE权重 + ROE排名 × ROE权重
    """
    df = stocks_df.copy()
    
    # 计算排名
    df['pe_rank'] = df['pe'].rank(pct=True, ascending=True)
    df['roe_rank'] = df['roe'].rank(pct=True, ascending=False)
    
    # 计算VQM得分
    df['vqm_score'] = (
        df['pe_rank'] * params['pe_weight'] + 
        df['roe_rank'] * params['roe_weight']
    )
    
    # 选出前N名
    return df.nlargest(params['position_count'], 'vqm_score')
```

### 3.3 交易模拟

```python
def simulate_trading(selected_stocks: pd.DataFrame, 
                     entry_date: str, 
                     params: Dict) -> Dict:
    """
    模拟交易
    
    策略:
    1. 等权重分配资金
    2. 分批建仓（3批，间隔5天）
    3. 个股止损-8%
    4. 组合止损-10%
    5. 最大回撤控制-15%
    6. 持仓3年或触发止损清仓
    """
    
    capital = params['initial_capital']
    positions = {}
    
    # 建仓
    for code in selected_stocks['code']:
        position_value = capital / len(selected_stocks)
        positions[code] = {
            'entry_price': get_price(code, entry_date),
            'shares': position_value / get_price(code, entry_date),
            'entry_date': entry_date
        }
    
    # 模拟持仓
    for day in get_trading_days(entry_date, days=252*3):  # 3年
        # 检查止损
        for code, pos in positions.items():
            current_price = get_price(code, day)
            loss_pct = (current_price - pos['entry_price']) / pos['entry_price']
            
            if loss_pct < -0.08:  # 个股止损
                sell_position(code, day, reason='stop_loss')
        
        # 检查组合回撤
        portfolio_value = calculate_portfolio_value(positions, day)
        if portfolio_value < capital * 0.85:  # 回撤15%
            reduce_all_positions(positions, day, ratio=0.5)
    
    # 清仓计算收益
    final_value = calculate_portfolio_value(positions, exit_date)
    
    return {
        'entry_date': entry_date,
        'exit_date': exit_date,
        'initial_capital': capital,
        'final_value': final_value,
        'total_return': (final_value - capital) / capital,
        'trades': get_trade_history()
    }
```

---

## 四、逐步优化SOP

### 4.1 参数优化流程

```python
def optimize_params_iteration(results: List[Dict]):
    """
    根据回测结果优化参数
    
    优化维度:
    1. PE权重 (0.5 ~ 0.8)
    2. ROE权重 (0.2 ~ 0.5)
    3. 持仓数量 (5 ~ 20)
    4. 止损线 (0.88 ~ 0.95)
    
    优化目标:
    - 最大化夏普比率
    - 控制最大回撤 < 20%
    - 胜率 > 60%
    """
    
    # 分析当前参数表现
    current_metrics = analyze_results(results)
    
    # 识别问题
    issues = identify_issues(current_metrics)
    
    # 调整参数
    new_params = adjust_params(current_metrics, issues)
    
    return new_params
```

### 4.2 迭代优化循环

```
迭代1: 初始参数 (PE=0.6, ROE=0.4, 持仓=10)
    ↓
回测结果: 年化8%, 回撤18%, 夏普1.1
    ↓
问题识别: 回撤偏大，波动较高
    ↓
参数调整: PE=0.7, ROE=0.3, 持仓=15 (更分散)
    ↓
迭代2: 新参数回测
    ↓
回测结果: 年化7%, 回撤14%, 夏普1.3
    ↓
继续优化...
```

---

## 五、汇报机制

### 5.1 整点汇报内容

```python
def hourly_report():
    """
    整点汇报格式
    """
    report = f"""
    {'='*70}
    📊 VQM回测进度汇报 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]
    {'='*70}
    
    阶段: 数据采集 / 回测执行 / 结果分析
    进度: 已完成 {completed}/{total} ({completed/total*100:.1f}%)
    
    当前状态:
    - 数据下载: {data_download_status}
    - 回测进度: {backtest_progress}
    - 优化迭代: {optimization_iteration}
    
    最新结果:
    - 平均年化收益: {avg_annual_return:.2%}
    - 平均最大回撤: {avg_max_drawdown:.2%}
    - 平均夏普比率: {avg_sharpe:.2f}
    - 胜率: {win_rate:.1%}
    
    预计完成时间: {estimated_completion}
    {'='*70}
    """
    return report
```

### 5.2 关键节点汇报

| 节点 | 汇报内容 |
|:-----|:---------|
| **数据下载完成** | 下载股票数、数据时间范围、文件大小 |
| **单次回测完成** | 建仓日期、选中股票、初步收益 |
| **优化迭代完成** | 新旧参数对比、性能提升 |
| **全部完成** | 最终报告、最优参数、建议 |

---

## 六、执行检查清单

### 6.1 数据准备检查

- [ ] SQLite数据库创建成功
- [ ] 股票池获取完整（1000只）
- [ ] 日线数据下载完整（2018-2024）
- [ ] 估值数据补充完整
- [ ] 宏观数据下载完整
- [ ] 数据质量检查通过

### 6.2 回测执行检查

- [ ] 每月第一个交易日正确识别
- [ ] VQM选股逻辑正确
- [ ] 分批建仓逻辑正确
- [ ] 止损逻辑正确
- [ ] 交易记录完整
- [ ] 收益计算正确

### 6.3 结果分析检查

- [ ] 年化收益计算正确
- [ ] 最大回撤计算正确
- [ ] 夏普比率计算正确
- [ ] 胜率统计正确
- [ ] 参数优化逻辑正确

---

## 七、问题处理预案

### 7.1 数据缺失处理

| 问题 | 处理方案 |
|:-----|:---------|
| 某只股票数据缺失 | 从股票池移除，用备选股票补充 |
| 某日数据缺失 | 使用前一日数据前向填充 |
| PE/ROE数据缺失 | 使用最近可用数据 |
| 宏观数据缺失 | 使用上月数据或插值 |

### 7.2 API限制处理

| 问题 | 处理方案 |
|:-----|:---------|
| API调用频率限制 | 添加sleep(0.5)控制频率 |
| API临时不可用 | 重试3次，失败后记录跳过 |
| 数据返回异常 | 记录错误，使用备用数据源 |

---

## 八、交付物

### 8.1 数据文件

```
data/backtest/
├── vqm_backtest.db          # SQLite数据库
├── stock_daily.csv          # 股票日度数据（备份）
├── macro_data.csv           # 宏观数据（备份）
└── backtest_results.json    # 回测结果（备份）
```

### 8.2 报告文件

```
reports/
├── vqm_backtest_report.md       # 完整回测报告
├── optimization_history.md      # 参数优化历史
├── case_studies.md              # 典型案例分析
└── final_recommendation.md      # 最终建议
```

---

**开始执行回测！**
