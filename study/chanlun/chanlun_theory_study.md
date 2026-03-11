# 缠论 (Chan Lun) 学习笔记

> 研究目的: 优化支撑压力位计算，提升实盘跟踪Pro的准确性
> 创建时间: 2026-03-11

---

## 一、缠论核心概念

### 1. 走势类型

| 类型 | 定义 | 特征 |
|:---|:---|:---|
| **上涨** | 高点不断抬高，低点也不断抬高 | N字形向上 |
| **下跌** | 高点不断降低，低点也不断降低 | N字形向下 |
| **盘整** | 高点基本水平，低点也基本水平 | 区间震荡 |

### 2. 中枢 (核心概念)

**定义**: 连续三个次级别走势类型的重叠区间

```
中枢区间 = [max(三个低点), min(三个高点)]

        高点1 ──┐
                │
        低点1 ──┼──┐
                 │  │
        高点2 ──┼──┼──┐
                 │  │  │
        低点2 ──┴──┼──┘
                    │
        高点3 ──────┘
        
        中枢 = [max(低1,低2), min(高1,高2,高3)]
```

**意义**: 
- 中枢是多空双方激烈争夺的区域
- 突破中枢 = 趋势延续信号
- 跌破中枢 = 趋势反转信号

### 3. 笔与线段

**笔的构成** (至少5根K线):
1. 顶分型 + 底分型 + 中间至少1根K线
2. 或者 底分型 + 顶分型 + 中间至少1根K线

**线段**: 至少3笔构成一个线段

```
顶分型:  第二根K线高点最高，且低点也最高
        │
       ╱╲
      ╱  ╲
     ╱    ╲
    ╱      ╲
   
底分型:  第二根K线低点最低，且高点也最低
    
    ╲      ╱
     ╲    ╱
      ╲  ╱
       ╲╱
        │
```

---

## 二、缠论买卖点 (三类)

### 第一类买卖点 (趋势背驰点)

| 类型 | 条件 | 操作 |
|:---|:---|:---|
| **一买** | 下跌趋势背驰 + 跌破最后一个中枢 | 买入 |
| **一卖** | 上涨趋势背驰 + 突破最后一个中枢 | 卖出 |

**背驰判断**:
- 价格新低/新高，但MACD不新低/新高
- 成交量不配合

### 第二类买卖点

| 类型 | 条件 | 操作 |
|:---|:---|:---|
| **二买** | 一买后回落不创新低 | 加仓/买入 |
| **二卖** | 一卖后反弹不创新高 | 减仓/卖出 |

### 第三类买卖点

| 类型 | 条件 | 操作 |
|:---|:---|:---|
| **三买** | 突破中枢后回踩不进入中枢 | 加仓 |
| **三卖** | 跌破中枢后反抽不进入中枢 | 清仓 |

```
三买示意图:

            突破中枢
               │
               ▼
    ┌──────────┬─────────┐
    │          │         │
    │   中枢   │  回踩   │  ← 不进入中枢 = 三买
    │          │         │
    └──────────┴─────────┘
               ▲
               │
            买入点

三卖示意图:

    ┌──────────┬─────────┐
    │          │         │
    │  反抽    │   中枢  │  ← 不进入中枢 = 三卖
    │          │         │
    └──────────┴─────────┘
               │
               ▼
            跌破中枢
               │
               ▼
            卖出点
```

---

## 三、缠论支撑压力位计算

### 1. 中枢支撑压力

```python
def calculate_zhongshu_sr(df, n=20):
    '''
    计算中枢支撑压力
    找最近n根K线中，连续3个走势类型的重叠区间
    '''
    highs = df['high'].tail(n).values
    lows = df['low'].tail(n).values
    
    # 简化版: 找高点密集区和低点密集区
    from scipy import stats
    
    # 价格分布
    price_levels = np.linspace(lows.min(), highs.max(), 50)
    
    # 计算每个价位的"停留时间"
    time_at_level = []
    for level in price_levels:
        mask = (lows <= level) & (highs >= level)
        time_at_level.append(mask.sum())
    
    # 找成交量最大的区间 (中枢)
    max_idx = np.argmax(time_at_level)
    zhongshu_center = price_levels[max_idx]
    
    # 中枢上下轨
    zhongshu_high = price_levels[min(max_idx+5, len(price_levels)-1)]
    zhongshu_low = price_levels[max(max_idx-5, 0)]
    
    return {
        'zhongshu_high': zhongshu_high,  # 压力
        'zhongshu_center': zhongshu_center,
        'zhongshu_low': zhongshu_low,    # 支撑
    }
```

### 2. 分型支撑压力

```python
def calculate_fenxing_sr(df):
    '''
    分型支撑压力
    找最近的分型作为关键价位
    '''
    highs = df['high'].values
    lows = df['low'].values
    
    # 找顶分型 (压力位)
    resistance_levels = []
    for i in range(2, len(df)-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            resistance_levels.append(highs[i])
    
    # 找底分型 (支撑位)
    support_levels = []
    for i in range(2, len(df)-2):
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            support_levels.append(lows[i])
    
    return {
        'fenxing_resistance': max(resistance_levels) if resistance_levels else None,
        'fenxing_support': min(support_levels) if support_levels else None,
    }
```

### 3. 走势类型压力支撑

```python
def calculate_zoushi_sr(df):
    '''
    基于走势类型的支撑压力
    '''
    highs = df['high'].values
    lows = df['low'].values
    
    # 最近的高点连线 (下降趋势线)
    pivots_high = []
    for i in range(5, len(df)-5):
        if highs[i] == max(highs[i-5:i+6]):
            pivots_high.append((i, highs[i]))
    
    # 最近的低点连线 (上升趋势线)
    pivots_low = []
    for i in range(5, len(df)-5):
        if lows[i] == min(lows[i-5:i+6]):
            pivots_low.append((i, lows[i]))
    
    # 趋势线和通道线
    if len(pivots_high) >= 2:
        # 下降趋势线 (压力)
        x1, y1 = pivots_high[-2]
        x2, y2 = pivots_high[-1]
        trend_resistance = y2 + (y2 - y1) / (x2 - x1) * (len(df) - 1 - x2)
    else:
        trend_resistance = None
    
    if len(pivots_low) >= 2:
        # 上升趋势线 (支撑)
        x1, y1 = pivots_low[-2]
        x2, y2 = pivots_low[-1]
        trend_support = y2 + (y2 - y1) / (x2 - x1) * (len(df) - 1 - x2)
    else:
        trend_support = None
    
    return {
        'trend_resistance': trend_resistance,
        'trend_support': trend_support,
        'pivots_high': pivots_high,
        'pivots_low': pivots_low
    }
```

---

## 四、应用于实盘跟踪

### 增强版支撑压力位计算

```python
def calculate_chanlun_sr(df):
    '''
    缠论综合支撑压力计算
    '''
    results = {}
    
    # 1. 中枢支撑压力
    zhongshu = calculate_zhongshu_sr(df)
    results.update(zhongshu)
    
    # 2. 分型支撑压力
    fenxing = calculate_fenxing_sr(df)
    results.update(fenxing)
    
    # 3. 走势类型支撑压力
    zoushi = calculate_zoushi_sr(df)
    results.update(zoushi)
    
    # 综合判断
    current = df.iloc[-1]['close']
    
    # 最强支撑 = 分型支撑 + 趋势支撑 + 中枢下轨 的加权平均
    support_candidates = [
        results.get('fenxing_support'),
        results.get('trend_support'),
        results.get('zhongshu_low')
    ]
    support_candidates = [s for s in support_candidates if s is not None]
    
    if support_candidates:
        results['strong_support'] = np.mean(support_candidates)
    
    # 最强压力 = 分型压力 + 趋势压力 + 中枢上轨 的加权平均
    resistance_candidates = [
        results.get('fenxing_resistance'),
        results.get('trend_resistance'),
        results.get('zhongshu_high')
    ]
    resistance_candidates = [r for r in resistance_candidates if r is not None]
    
    if resistance_candidates:
        results['strong_resistance'] = np.mean(resistance_candidates)
    
    return results
```

### 关键价位识别

| 价位类型 | 计算方法 | 交易意义 |
|:---|:---|:---|
| **三买确认位** | 中枢上轨 + 回踩不破 | 加仓信号 |
| **三卖确认位** | 中枢下轨 - 反抽不过 | 清仓信号 |
| **趋势反转位** | 背驰点 ± 3% | 止损/止盈 |
| **中枢震荡位** | 中枢上下轨 | 高抛低吸 |

---

## 五、实践要点

### 1. 多周期共振

- 日线级别中枢 + 30分钟级别三买 = 高胜率买点
- 日线级别背驰 + 5分钟级别确认 = 趋势反转信号

### 2. 量能验证

- 突破中枢必须放量
- 背驰必须缩量
- 三买/三卖必须有量能配合

### 3. 风险控制

- 一买失败率较高，仓位要轻
- 三买成功率最高，可重仓
- 跌破中枢必须止损

---

## 六、下一步优化方向

1. **自动识别中枢**: 用代码自动画出中枢区间
2. **分型自动识别**: 自动标记顶分型/底分型
3. **背驰自动检测**: MACD背驰 + 量价背驰
4. **买卖点自动提示**: 三买/三卖信号自动预警
5. **多周期联立**: 日线+30分钟+5分钟同时分析

---

*学习完成时间: 2026-03-11*
*应用到: 实盘跟踪Pro V4*
