# VQM策略回测SOP（严格版）

> **版本**: v2.0  
> **更新日期**: 2026-02-14  
> **核心要求**: 真实数据 + 严格验证 + 无未来函数

---

## 一、数据来源规范

### 1.1 必须使用真实数据源

| 数据类型 | 推荐API | 备用API | 检查项 |
|:---------|:--------|:--------|:-------|
| **股票价格** | AKShare | Tushare | 复权价格 |
| **财务报表** | AKShare | 同花顺 | 发布时间 |
| **PE/PB数据** | AKShare | Wind | 计算日期 |
| **ROE数据** | AKShare | 东方财富 | 报告期 |

### 1.2 数据获取SOP

```python
# ✅ 正确做法：使用历史数据，避免未来函数
def get_stock_data_correct(symbol, date):
    """
    获取某股票在某日期的历史数据
    关键：只能使用当日及之前的数据
    """
    # 获取历史价格（前复权）
    df = ak.stock_zh_a_hist(symbol=symbol, start_date="20180101", end_date=date)
    
    # 获取财务数据（使用最近已发布财报）
    # 注意：不能用未发布的财报数据！
    financial_date = get_last_report_date(date)  # 获取最近的已发布财报日期
    pe = get_pe_on_date(symbol, financial_date)
    roe = get_roe_on_date(symbol, financial_date)
    
    return {
        'price': df.iloc[-1]['close'],
        'pe': pe,
        'roe': roe,
        'data_date': financial_date  # 记录数据实际日期
    }

# ❌ 错误做法：使用未来数据
def get_stock_data_wrong(symbol, date):
    """这是错误的！使用了未来数据"""
    df = ak.stock_zh_a_hist(symbol=symbol, start_date="20180101", end_date="20241231")
    pe = get_pe_on_date(symbol, date)  # 如果date是当天，可能用到未收盘数据
    return df  # 错误：包含了未来的价格数据
```

---

## 二、未来函数检查清单

### 2.1 严格禁止的未来函数

| 类型 | 错误示例 | 正确做法 |
|:-----|:---------|:---------|
| **使用未来价格** | 用当日收盘价买卖 | 用次日开盘价或当日成交均价 |
| **使用未发布财报** | 8月用Q2财报（未发布） | 8月只能用Q1财报 |
| **使用未来排名** | 月末用当月最后一天数据排名 | 月末用上月最后一个交易日数据 |
| **使用未来指标** | 用MA20计算当日信号（包含当日） | 用前一日MA20 |
| **参数优化泄露** | 用全周期数据优化参数 | 用滚动窗口优化，Holdout测试 |

### 2.2 财报发布时间对照表

| 报告期 | 发布截止日 | 可使用时间 | 不可用时间 |
|:-------|:-----------|:-----------|:-----------|
| Q1一季报 | 4月30日 | 5月1日起 | 4月30日前 |
| 半年报 | 8月31日 | 9月1日起 | 8月31日前 |
| Q3三季报 | 10月31日 | 11月1日起 | 10月31日前 |
| 年报 | 次年4月30日 | 次年5月1日起 | 当年及次年4月30日前 |

### 2.3 交易时点检查

```python
def check_trading_timing():
    """
    交易时点检查清单
    """
    checks = {
        '买入价格': '使用次日开盘价或当日成交均价（非收盘价）',
        '卖出价格': '使用次日开盘价或当日成交均价（非收盘价）',
        '调仓时点': '月度调仓使用上月最后一个交易日的数据',
        '财报数据': '使用最近已发布财报，不能用未发布数据',
        '参数优化': '滚动窗口优化，当前窗口不能用未来数据',
    }
    return checks
```

---

## 三、VQM选股SOP（严格版）

### 3.1 选股流程

```
Step 1: 确定选股日期（如2023-03-01）
    ↓
Step 2: 获取该日期可用的最新财务数据
    - 检查：2023年3月1日可用的最新财报是2022Q3（2022-10-31发布）
    - 不能使用：2022年报（2023-04才发布）
    ↓
Step 3: 获取该日期的历史价格数据（前复权）
    - 只能用到2023-03-01的数据
    - 不能用2023-03-02及之后的价格
    ↓
Step 4: 计算PE/ROE并排名
    - PE = 股价 / 最近财报EPS（TTM）
    - ROE = 最近财报ROE
    ↓
Step 5: 计算VQM得分
    - VQM = PE排名×60% + ROE排名×40%
    ↓
Step 6: 选出前N只股票
    ↓
Step 7: 次日开盘建仓（或当日均价）
```

### 3.2 代码实现模板

```python
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

def vqm_select_stocks_strict(select_date: str, stock_pool: list) -> pd.DataFrame:
    """
    VQM严格版选股函数
    
    Args:
        select_date: 选股日期 '2023-03-01'
        stock_pool: 股票池列表 ['000001', '000002', ...]
    
    Returns:
        DataFrame with VQM score
    """
    results = []
    
    # 1. 确定可用的最新财报日期
    report_date = get_available_report_date(select_date)
    print(f"选股日期: {select_date}, 可用财报: {report_date}")
    
    for symbol in stock_pool:
        try:
            # 2. 获取历史价格（只能用到select_date）
            hist_df = ak.stock_zh_a_hist(
                symbol=symbol, 
                start_date="20180101", 
                end_date=select_date  # 关键：不能包含未来数据
            )
            
            if len(hist_df) == 0:
                continue
            
            current_price = hist_df.iloc[-1]['close']
            
            # 3. 获取财务数据（只能用已发布的财报）
            pe = get_pe_strict(symbol, report_date)  # 使用report_date的PE
            roe = get_roe_strict(symbol, report_date)  # 使用report_date的ROE
            
            if pe is None or roe is None or pe <= 0:
                continue
            
            results.append({
                'symbol': symbol,
                'price': current_price,
                'pe': pe,
                'roe': roe,
                'select_date': select_date,
                'report_date': report_date
            })
            
        except Exception as e:
            print(f"获取{symbol}数据失败: {e}")
            continue
    
    df = pd.DataFrame(results)
    
    # 4. 计算VQM得分
    df['pe_rank'] = df['pe'].rank(pct=True, ascending=True)  # PE越低排名越高
    df['roe_rank'] = df['roe'].rank(pct=True, ascending=False)  # ROE越高排名越高
    df['vqm_score'] = df['pe_rank'] * 0.6 + df['roe_rank'] * 0.4
    
    return df.sort_values('vqm_score', ascending=False)


def get_available_report_date(select_date: str) -> str:
    """
    获取选股日期可用的最新财报日期
    严格遵循财报发布时间规则
    """
    date = datetime.strptime(select_date, '%Y-%m-%d')
    year = date.year
    month = date.month
    
    # 根据月份确定可用的最新财报
    if month >= 5:  # 5月及以后，可用上年年报
        return f"{year-1}-12-31"
    elif month >= 11:  # 11月及以后，可用当年三季报
        return f"{year}-09-30"
    elif month >= 9:  # 9-10月，可用当年半年报
        return f"{year}-06-30"
    else:  # 1-8月，只能用上年三季报
        return f"{year-1}-09-30"


def get_pe_strict(symbol: str, report_date: str) -> float:
    """
    获取指定财报日期的PE（严格版）
    """
    # 使用AKShare获取历史估值数据
    try:
        df = ak.stock_a_pe(symbol=symbol)
        # 找到report_date对应的PE
        # 实际实现需要根据数据源调整
        return df[df['date'] <= report_date].iloc[-1]['pe']
    except:
        return None


def get_roe_strict(symbol: str, report_date: str) -> float:
    """
    获取指定财报日期的ROE（严格版）
    """
    try:
        df = ak.stock_financial_report_sina(stock=symbol)
        # 找到report_date对应的ROE
        return df[df['report_date'] == report_date].iloc[0]['roe']
    except:
        return None
```

---

## 四、回测执行SOP

### 4.1 三层验证体系

```
Layer 1: Walk-Forward Optimization (WFO)
├── 滚动窗口训练/验证
├── 避免未来函数
└── 验证参数稳健性

Layer 2: Holdout Test
├── 完全未见过的1年数据
├── 验证无过拟合
└── 模拟真实交易环境

Layer 3: Event Regression
├── 排除运气成分
├── 统计显著性检验
└── 控制混杂因素
```

### 4.2 WFO实现模板

```python
def walk_forward_optimization(data, train_years=3, test_years=1):
    """
    WFO滚动优化
    
    Example:
        Window 1: 2018-2020训练 → 2021测试
        Window 2: 2019-2021训练 → 2022测试
        Window 3: 2020-2022训练 → 2023测试
    """
    results = []
    
    for start_year in [2018, 2019, 2020]:
        train_start = f"{start_year}-01-01"
        train_end = f"{start_year + train_years - 1}-12-31"
        test_start = f"{start_year + train_years}-01-01"
        test_end = f"{start_year + train_years + test_years - 1}-12-31"
        
        print(f"\n=== Window: {train_start}~{train_end} → {test_start}~{test_end} ===")
        
        # 训练集：寻找最优参数
        best_params = optimize_params(data, train_start, train_end)
        print(f"训练集最优参数: {best_params}")
        
        # 测试集：验证参数
        test_result = backtest(data, test_start, test_end, best_params)
        print(f"测试集收益: {test_result['return']:.2%}, 夏普: {test_result['sharpe']:.2f}")
        
        results.append({
            'window': f"{test_start}~{test_end}",
            'best_params': best_params,
            'test_result': test_result
        })
    
    # 分析参数稳健性
    analyze_parameter_stability(results)
    
    return results
```

### 4.3 Holdout测试模板

```python
def holdout_test(data, stable_params, holdout_start, holdout_end):
    """
    Holdout样本外测试
    使用WFO选出的稳健参数，在完全未见过的数据上测试
    """
    print(f"\n=== Holdout Test: {holdout_start} ~ {holdout_end} ===")
    
    result = backtest(data, holdout_start, holdout_end, stable_params)
    
    print(f"Holdout收益: {result['return']:.2%}")
    print(f"Holdout夏普: {result['sharpe']:.2f}")
    print(f"Holdout最大回撤: {result['max_drawdown']:.2%}")
    
    # 过拟合检验
    wfo_avg = np.mean([r['test_result']['return'] for r in wfo_results])
    if abs(result['return'] - wfo_avg) > 0.05:
        print("⚠️ 警告: Holdout表现与WFO差距过大，可能存在过拟合")
    else:
        print("✅ 通过: Holdout表现与WFO一致，无过拟合")
    
    return result
```

---

## 五、风险控制SOP

### 5.1 个股止损

```python
def check_individual_stop_loss(positions, current_prices, stop_loss=0.92):
    """
    检查个股止损
    """
    sell_list = []
    for symbol, pos in positions.items():
        current_price = current_prices[symbol]
        if current_price <= pos['entry_price'] * stop_loss:
            sell_list.append({
                'symbol': symbol,
                'reason': f'止损触发: 当前价{current_price} <= 买入价{pos["entry_price"]} * {stop_loss}'
            })
    return sell_list
```

### 5.2 组合止损

```python
def check_portfolio_stop_loss(portfolio_value, peak_value, stop_loss=0.90):
    """
    检查组合止损
    """
    if portfolio_value <= peak_value * stop_loss:
        return True, f'组合止损触发: 当前市值{portfolio_value} <= 峰值{peak_value} * {stop_loss}'
    return False, ''
```

### 5.3 回撤控制

```python
def check_drawdown_control(portfolio_value, peak_value, max_drawdown=0.15):
    """
    回撤控制：回撤超过15%时减仓50%
    """
    current_drawdown = (peak_value - portfolio_value) / peak_value
    if current_drawdown > max_drawdown:
        return True, f'回撤控制: 当前回撤{current_drawdown:.1%} > 阈值{max_drawdown}'
    return False, ''
```

---

## 六、报告生成SOP

### 6.1 必须包含的内容

| 章节 | 内容 | 要求 |
|:-----|:-----|:-----|
| **数据说明** | 数据来源、时间范围、股票池 | 真实数据源 |
| **未来函数检查** | 检查清单及结果 | 逐项通过 |
| **回测设定** | 初始资金、交易成本、滑点 | 符合实际 |
| **WFO结果** | 各窗口参数及表现 | 参数稳健 |
| **Holdout结果** | 样本外表现 | 无过拟合 |
| **交易记录** | 每次买卖时间、价格、原因 | 可验证 |
| **风险指标** | 最大回撤、夏普、胜率 | 完整计算 |

### 6.2 报告模板

```markdown
# VQM策略回测报告（严格版）

## 1. 数据说明
- 数据来源: AKShare
- 时间范围: 2018-01-01 ~ 2024-12-31
- 股票池: 沪深300成分股
- 价格数据: 前复权收盘价

## 2. 未来函数检查
- [x] 未使用未来价格
- [x] 未使用未发布财报
- [x] 未使用未来排名
- [x] 参数优化无数据泄露

## 3. WFO滚动优化结果
| 窗口 | 最优PE权重 | 最优ROE权重 | 测试收益 | 测试夏普 |
|:-----|:----------:|:-----------:|:--------:|:--------:|
| 2019-2021 | 0.6 | 0.4 | +18.5% | 1.35 |
| 2020-2022 | 0.6 | 0.4 | +15.2% | 1.28 |
| 2021-2023 | 0.7 | 0.3 | +12.8% | 1.15 |

**参数稳健性**: PE权重标准差0.047，ROE权重标准差0.047 ✅

## 4. Holdout样本外测试
- 测试期: 2024-01-01 ~ 2024-12-31
- 总收益: +8.5%
- 年化收益: +8.5%
- 夏普比率: 0.95
- 最大回撤: 12.3%

**过拟合检验**: WFO平均收益15.5%，Holdout收益8.5%，差距7% ⚠️

## 5. 交易记录（节选）
| 日期 | 操作 | 股票 | 价格 | 数量 | 原因 |
|:-----|:----:|:----:|:----:|:----:|:-----|
| 2023-03-01 | BUY | 000001 | 10.50 | 1000 | VQM排名第1 |
| 2023-03-15 | ADD | 000001 | 10.20 | 500 | 加仓至目标权重 |
| 2023-04-20 | SELL | 000001 | 9.50 | 1500 | 止损触发(-9.5%) |

## 6. 风险指标
- 最大回撤: 18.5%
- 夏普比率: 1.25
- 胜率: 68%
- 盈亏比: 2.8:1

## 7. 结论
- 策略有效性: ✅ 有效
- 参数稳健性: ✅ 稳健
- 过拟合风险: ⚠️ 轻微（建议优化）
- 推荐采用: 🟡 谨慎采用
```

---

## 七、检查清单

### 回测前必须检查

- [ ] 使用真实数据源（AKShare/Tushare）
- [ ] 确认无未来函数（价格、财报、排名）
- [ ] 交易成本设置合理（佣金+印花税+滑点）
- [ ] 使用复权价格
- [ ] 财报数据发布时间正确

### WFO必须检查

- [ ] 滚动窗口划分正确
- [ ] 训练集与测试集无重叠
- [ ] 参数在不同窗口表现一致
- [ ] 无参数过拟合

### Holdout必须检查

- [ ] Holdout数据完全未参与训练
- [ ] Holdout表现与WFO差距<5%
- [ ] 统计显著性检验通过

### 报告必须包含

- [ ] 数据来源说明
- [ ] 未来函数检查清单
- [ ] 完整交易记录
- [ ] 风险指标计算
- [ ] 过拟合检验结果

---

**严格执行本SOP，确保回测结果真实可信！**
