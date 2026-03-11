---
name: portfolio-tracker-pro
description: |
  实盘跟踪Pro V4 - 缠论增强版
  
  核心升级:
  1. 缠论支撑压力位 (中枢/分型/走势类型)
  2. 超详细操作建议 (含具体价位)
  3. 关键价位清单 (买入/止损/止盈/关注)
  4. 实时分钟级数据
  
  执行时间: 9:30/11:00/13:30/14:50
  输出: 分批发送至个人飞书 (每只1条详细消息)
---

# 实盘跟踪Pro V4 Skill (缠论增强版)

## 缠论学习文档

📚 **详细学习笔记**: `study/chanlun/chanlun_theory_study.md`

包含:
- 走势类型 (上涨/下跌/盘整)
- 中枢概念与计算
- 笔与线段
- 三类买卖点
- 缠论支撑压力位计算方法

---

## 每只股票的报告包含

### 1. 价格与盈亏
- 当前价、涨跌幅
- 今日区间
- 持仓市值
- **实际盈亏金额和百分比**

### 2. 缠论支撑压力位
- **中枢区间**: [下轨, 上轨] + 中心
- **分型支撑**: 底分型低点
- **分型压力**: 顶分型高点
- **⚡强支撑**: 多方法验证的综合支撑位
- **⚡强压力**: 多方法验证的综合压力位

### 3. 均线支撑压力
- MA5/MA10/MA20
- 每根均线的支撑/压力状态

### 4. 量能分析
- 量比 (放量⚡/缩量💧/正常➡️)
- 资金流向 (流入📈/流出📉)

### 5. 关键价位清单 (核心!)

#### 💰 买入价位
- 建议买入价位 (预设)
- 缠论支撑位
- 枢轴S1

#### 🛑 止损价位
- 预设止损位
- 枢轴S2 (强支撑跌破清仓)
- 分型低点

#### ✅ 止盈价位
- 第一止盈位
- 第二止盈位
- 强压力位

#### 👀 关注价位 (实时监控)
- 中枢上轨 (突破加仓)
- 中枢下轨 (跌破减仓)
- 枢轴R1/R2
- 枢轴点位置

### 6. 操作建议 (核心!)

#### 技术评分
- 评分范围: -3 ~ +3分
- 判断依据列举

#### 具体操作
- **操作类型**: 立即止损/加仓持有/持有观望/减仓避险/清仓止损
- **详细说明**: 为什么给出这个建议
- **下一步操作清单**: 1/2/3步骤

---

## 输出格式示例

```
📊 金盘科技 (688676.SH) - 电力设备
⏰ 数据时间: 09:35:12

【价格与盈亏】
  当前价: 96.60元
  涨跌幅: -4.59% | 今日: -1.23%
  今日区间: 94.80 - 100.20
  持仓: 2000股 = 19.32万
  📉 盈亏: -2800元 (-2.83%)

【缠论支撑压力位】
  中枢区间: [94.50, 99.80]
  中枢中心: 97.15元
  分型支撑: 91.01元
  分型压力: 105.65元
  ⚡ 强支撑: 93.20元 (多方法验证)
  ⚡ 强压力: 102.80元 (多方法验证)

【均线支撑压力】
  MA5:  97.20元 📉压力
  MA10: 98.50元 📉压力
  MA20: 99.80元 📉压力

【量能分析】
  量比: 1.85 ⚡放量
  资金: 📉流出 35万手

【关键价位清单】

💰 买入价位:
  建议买入: ≤95.00元 (✅已跌破，可买入)
  缠论支撑: 93.20元 (回调至此关注)
  枢轴S1: 94.50元

🛑 止损价位:
  预设止损: 90.00元 (还有7.8%空间)
  枢轴S2: 91.50元 (强支撑跌破则清仓)
  分型低点: 91.01元

✅ 止盈价位:
  第一止盈: 105.00元 (还需涨8.7%)
  第二止盈: 110.00元 (还需涨13.9%)
  强压力位: 102.80元 (突破后可持有)

👀 关注价位 (实时监控):
  中枢上轨: 99.80元 (未突破) - 突破加仓
  中枢下轨: 94.50元 (已跌破🔴) - 跌破减仓
  枢轴R1: 101.20元 - 短期压力
  枢轴点: 97.50元 (当前下方📉)

【操作建议】
  技术评分: -1.5分
  判断依据: 均线空头排列;放量下跌;资金流出;接近止损位

  🎯 操作建议: ⚠️ 减仓避险
  📝 详细说明: 走弱信号明显，减仓保护本金

  📋 下一步操作:
    1. 立即减仓至半仓以下
    2. 反弹至98.50元清仓
    3. 严格止损90.00元

--------------------------------------------------
```

---

## 使用方法

```bash
# 手动执行
./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py morning   # 9:30
./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py noon      # 11:00
./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py afternoon # 13:30
./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py close     # 14:50
./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py all       # 完整分析
```

---

## Linux Cron配置

```bash
# 实盘跟踪Pro V4 - 缠论增强版 (每日4次)

# 9:30 早盘分析
30 9 * * 1-5 cd /root/.openclaw/workspace && ./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py morning >> /tmp/portfolio_v4_morning.log 2>&1

# 11:00 午盘分析
0 11 * * 1-5 cd /root/.openclaw/workspace && ./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py noon >> /tmp/portfolio_v4_noon.log 2>&1

# 13:30 下午分析
30 13 * * 1-5 cd /root/.openclaw/workspace && ./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py afternoon >> /tmp/portfolio_v4_afternoon.log 2>&1

# 14:50 尾盘分析
50 14 * * 1-5 cd /root/.openclaw/workspace && ./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v4.py close >> /tmp/portfolio_v4_close.log 2>&1
```

---

## 持仓配置 (含关键价位)

```python
PORTFOLIO = {
    "300750.SZ": {
        "name": "宁德时代", "shares": 1000, "sector": "新能源", "cost": 380.0,
        "buy_below": 390,      # 建议买入价位
        "stop_loss": 370,      # 止损价位
        "take_profit_1": 420,  # 第一止盈
        "take_profit_2": 450   # 第二止盈
    },
    "300274.SZ": {
        "name": "阳光电源", "shares": 1500, "sector": "新能源", "cost": 155.0,
        "buy_below": 165, "stop_loss": 150, "take_profit_1": 185, "take_profit_2": 200
    },
    # ... 其他股票
}
```

---

## 缠论支撑压力计算方法

### 1. 中枢计算
```python
# 找价格密集区 (停留时间最长的区间)
price_range = np.linspace(lows.min(), highs.max(), 20)
time_at_level = []
for level in price_range:
    mask = (lows <= level) & (highs >= level)
    time_at_level.append(mask.sum())

# 中枢中心 = 停留时间最长的价位
zhongshu_center = price_range[np.argmax(time_at_level)]
```

### 2. 分型计算
```python
# 顶分型 (压力位)
if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
    highs[i] > highs[i+1] and highs[i] > highs[i+2]):
    resistance_levels.append(highs[i])

# 底分型 (支撑位)
if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
    lows[i] < lows[i+1] and lows[i] < lows[i+2]):
    support_levels.append(lows[i])
```

### 3. 综合强支撑/压力
```python
# 多方法验证，取中位数
strong_support = np.median([fenxing_support, zhongshu_low, ma20, s1])
strong_resistance = np.median([fenxing_resistance, zhongshu_high, r1])
```

---

## 发送方式

- **发送目标**: 个人飞书 (`user:ou_efbad805767f4572e8f93ebafa8d5402`)
- **发送方式**: 分批发送 (每只1条详细消息)
- **消息数**: 9只股票 = 9条消息 + 1条开头 + 1条结尾 = 共11条

---

## 风险提示

- 缠论支撑压力基于历史数据计算，仅供参考
- 关键价位需结合实时市场情况判断
- 操作建议不构成投资建议

---
*版本: 4.0 (缠论增强版) | 创建日期: 2026-03-11*
*学习文档: study/chanlun/chanlun_theory_study.md*
