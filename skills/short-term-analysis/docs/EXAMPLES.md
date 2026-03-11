# 短期走势分析 Skill - 使用示例

## 快速开始

### 分析单只股票

```bash
cd /root/.openclaw/workspace
./venv_runner.sh skills/short-term-analysis/scripts/analyze_short_term.py 688008.SH
```

### 分析多只股票

```bash
./venv_runner.sh skills/short-term-analysis/scripts/analyze_short_term.py \
  688008.SH 603986.SH 002384.SZ
```

## 完整示例: 分析7只半导体股票

```bash
./venv_runner.sh skills/short-term-analysis/scripts/analyze_short_term.py \
  688008.SH \
  603986.SH \
  002384.SZ \
  688019.SH \
  603920.SH \
  300548.SZ \
  688048.SH
```

## Python代码调用示例

### 基础用法

```python
#!/root/.openclaw/workspace/venv/bin/python3

import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/short-term-analysis/scripts')

from analyze_short_term import ShortTermAnalyzer

# 初始化
analyzer = ShortTermAnalyzer()

# 分析单只股票
result = analyzer.analyze('688008.SH')

print(f"股票: {result['symbol']}")
print(f"价格: {result['price']:.2f}")
print(f"支撑: {result['support']:.2f}")
print(f"压力: {result['resistance']:.2f}")
print(f"预测: {result['outlook']}")
print(f"预期收益: {result['expected_return']}")
print(f"综合评分: {result['score']:.1f}")
```

### 批量分析并排序

```python
# 分析多只股票
symbols = [
    '688008.SH',  # 澜起科技
    '603986.SH',  # 兆易创新
    '002384.SZ',  # 东山精密
    '688019.SH',  # 安集科技
    '603920.SH',  # 世运电路
    '300548.SZ',  # 长芯博创
    '688048.SH',  # 长光华芯
]

results = analyzer.analyze_multiple(symbols)

# 输出排名
print("\n=== 短期走势排名 ===")
for i, r in enumerate(results, 1):
    print(f"{i}. {r['symbol']}: {r['outlook']} (评分: {r['score']:.1f})")

# 筛选强烈看涨的股票
strong_bullish = [r for r in results if r['score'] >= 2.0]
print(f"\n强烈看涨: {[r['symbol'] for r in strong_bullish]}")
```

### 自定义分析参数

```python
# 获取详细数据
import pandas as pd

df_60, df_day = analyzer.fetch_data('688008.SH', days=90)

# 计算指标
df_60, df_day = analyzer.calculate_indicators(df_60, df_day)

# 自定义支撑压力位分析
sr = analyzer.analyze_support_resistance(df_60)
print(f"强支撑: {sr['support']:.2f}")
print(f"强压力: {sr['resistance']:.2f}")

# 自定义触碰验证 (调整容忍度)
touch = analyzer.count_touch_points(df_60, sr['support'], 
                                     tolerance=0.03,  # 3%容忍度
                                     lookback=80)     # 看80根K线
print(f"触碰次数: {touch['count']}, 反弹率: {touch['bounce_rate']:.1%}")
```

## 结果解读

### 典型输出示例

```
🥇 长光华芯 (688048.SH)
   价格: 160.21 | 支撑: 135.38 | 压力: 180.87
   触碰验证: 17次/65%反弹
   形态: W底
   POC: 137.93
   评分: 2.0 | 🚀 强烈看涨 | 预期收益: +15~25%
   因素: 日线上涨(+1), 强支撑(+1), W底(+1), M顶(-1)
```

### 关键指标说明

| 指标 | 说明 | 判断标准 |
|:-----|:-----|:---------|
| 触碰验证 | 价格触碰支撑的次数和反弹率 | ≥3次/≥50%反弹 = 强支撑 |
| 形态 | 识别的技术形态 | W底看涨, M顶看跌 |
| POC | 成交量最大价格 | 强支撑/压力参考 |
| 评分 | 综合评分 | ≥2强烈看涨, 1~2看涨, -1~1震荡 |
| 预期收益 | 预测20日收益区间 | 基于历史回测 |

## 实战策略示例

### 选股策略

```python
# 筛选优质标的
candidates = analyzer.analyze_multiple(symbols)

# 条件1: 评分 ≥ 1.0 (看涨以上)
# 条件2: 支撑验证 ≥ 3次
# 条件3: 有看涨形态
selected = [
    r for r in candidates 
    if r['score'] >= 1.0 
    and r['touch_count'] >= 3
    and 'W底' in r['patterns']
]

print("\n精选标的:")
for r in selected:
    print(f"  {r['symbol']}: {r['outlook']}")
```

### 止损策略

```python
def get_stop_loss(result, method='technical'):
    """
    计算止损位
    
    method:
      - technical: 技术止损 (支撑下方2%)
      - atr: ATR止损
      - fixed: 固定百分比
    """
    if method == 'technical':
        return result['support'] * 0.98
    elif method == 'fixed':
        return result['price'] * 0.95  # 5%止损
    else:
        return result['support']

# 使用示例
for r in results[:3]:  # 前3名
    stop = get_stop_loss(r, 'technical')
    risk = (r['price'] - stop) / r['price']
    print(f"{r['symbol']}: 止损位 {stop:.2f}, 风险 {risk:.2%}")
```

## 常见问题

### Q: 为什么我的股票分析失败？

可能原因:
1. 股票代码格式错误 (应使用 '688008.SH' 格式)
2. 该股票在长桥API不可交易
3. 网络连接问题

解决方法:
```python
# 检查股票代码格式
symbol = '688008.SH'  # 正确
symbol = '688008'     # 错误，缺少后缀

# 常见后缀
# .SH - 上海交易所
# .SZ - 深圳交易所
```

### Q: 如何获取更长的历史数据？

```python
# 修改days参数 (默认60天)
df_60, df_day = analyzer.fetch_data('688008.SH', days=120)
```

### Q: 如何提高分析准确性？

1. **多周期验证**: 结合日线、60分钟、15分钟
2. **人工复核**: 自动形态识别可能有误差
3. **结合基本面**: 技术面+基本面双重验证
4. **严格止损**: 技术分析准确率有限，需风控

## 进阶用法

### 定时分析

```bash
# 添加到crontab，每天收盘后自动分析
# crontab -e
# 30 15 * * 1-5 cd /root/.openclaw/workspace && ./venv_runner.sh skills/short-term-analysis/scripts/analyze_short_term.py 688008.SH 603986.SH >> /tmp/daily_analysis.log
```

### 结果存储到数据库

```python
import sqlite3

# 保存结果
def save_to_db(results, db_path='analysis.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_results (
            date TEXT,
            symbol TEXT,
            price REAL,
            support REAL,
            resistance REAL,
            score REAL,
            outlook TEXT,
            expected_return TEXT
        )
    ''')
    
    today = datetime.now().strftime('%Y-%m-%d')
    for r in results:
        cursor.execute('''
            INSERT INTO analysis_results 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (today, r['symbol'], r['price'], r['support'], 
              r['resistance'], r['score'], r['outlook'], r['expected_return']))
    
    conn.commit()
    conn.close()
```

---

*更多示例请参考源码: scripts/analyze_short_term.py*
