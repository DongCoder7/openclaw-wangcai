---
name: sector-analysis
description: |
  板块投资分析Skill - 全自动发现标的，零硬编码
  
  核心能力:
  1. 自动扫描板块内所有标的（不硬编码任何股票代码）
  2. 5维动态评分模型（动量/基本面/催化剂/风险/流动性）
  3. 多源数据交叉验证（Exa+知识星球+行情数据）
  4. 自动计算买卖点（基于技术面和催化剂强度）
  5. 支持任意板块分析（只需提供板块名称和关键词）
  
  使用方法:
  - 分析单个板块: analyze_sector("板块名称", ["关键词1", "关键词2"])
  - 分析多个板块: analyze_multiple_sectors({"板块1": ["关键词"], "板块2": ["关键词"]})
  
  触发条件: 用户要求分析板块投资、比较板块、选择标的、生成投资策略

# 板块投资分析 Skill v1.0

## 🎯 核心特点

**零硬编码，全自动发现** - 不再写死任何股票代码，所有标的通过实时数据动态发现。

## 📊 分析流程（4步法）

```
Step 1: 板块热度扫描 → 自动发现板块内所有标的
Step 2: 实时行情获取 → 获取价格/市值/涨跌幅
Step 3: 5维动态评分 → 按多维度指标排序
Step 4: 深度验证分析 → 搜索催化剂+计算买卖点
```

## 🔧 使用方法

### 1. 分析单个板块

```python
from skills.sector_analysis.scripts.sector_analyzer import analyze_sector

# 分析AI电源板块
report = analyze_sector(
    sector_name="AI电源",
    keywords=["AI电源", "数据中心电源", "服务器电源", "UPS电源"]
)

print(report)  # 输出完整分析报告
```

### 2. 分析多个板块

```python
from skills.sector_analysis.scripts.sector_analyzer import analyze_multiple_sectors

# 定义要分析的板块
sectors = {
    "AI电源": ["AI电源", "数据中心电源", "服务器电源"],
    "液冷": ["液冷", "数据中心散热", "服务器液冷"],
    "光芯片": ["光芯片", "光模块", "800G", "1.6T"],
    "PCB": ["PCB", "覆铜板", "高速PCB", "AI服务器PCB"],
    "燃气轮机": ["燃气轮机", "发电设备", "分布式能源"],
    "半导体设备": ["半导体设备", "刻蚀机", "薄膜沉积", "国产替代"]
}

# 批量分析
results = analyze_multiple_sectors(sectors)

# results 包含每个板块的分析报告
for sector, report in results.items():
    print(f"\n{'='*60}")
    print(f"【{sector}】分析报告")
    print(f"{'='*60}")
    print(report[:1000])  # 打印前1000字符
```

## 📈 5维评分模型

| 维度 | 权重 | 计算方式 | 说明 |
|:-----|:---:|:---|:---|
| **动量** | 25% | 1日/5日/20日涨幅 + 量比 | 技术面强度 |
| **催化剂** | 35% | 新闻搜索（政策/订单/技术/业绩/并购） | 事件驱动 |
| **基本面** | 15% | PE/PB + 营收/利润增速 | 估值水平 |
| **风险** | 15% | 波动率 + 最大回撤 | 风险控制 |
| **流动性** | 10% | 市值 + 成交额 + 换手率 | 交易便利 |

## 🔍 数据来源

| 来源 | 类型 | 用途 |
|:-----|:-----|:-----|
| **Exa全网搜索** | AI语义搜索 | 发现板块内公司、搜索催化剂 |
| **知识星球** | 调研纪要 | 发现热门标的、产业验证 |
| **腾讯财经API** | 实时行情 | 股价、市值、涨跌幅 |
| **Tushare** | 基本面数据 | PE、PB、财务数据（可选） |

## 📋 报告输出格式

```markdown
# 【板块名称】投资分析报告
> 生成时间: YYYY-MM-DD HH:MM
> 分析标的: 动态发现 N 只重点标的
> 搜索关键词: 关键词1, 关键词2, 关键词3

---

## 📊 板块热度
| 指标 | 数值 |
|:-----|:-----|
| 分析标的数 | N 只 |
| 平均涨跌幅 | +X.XX% |
| 板块总市值 | XXXX 亿元 |

---

## 🏆 投资排序（按综合评分）

### 第1名: 标的名称 (代码)
| 指标 | 数值 |
|:-----|:-----|
| 当前价 | XX.XX 元 |
| 今日涨跌 | +X.XX% |
| 综合评分 | XX.X/100 |
| 目标价 | XX.XX 元 |
| 预期涨幅 | +XX.X% |
| 止损价 | XX.XX 元 |
| 买入区间 | XX.XX-XX.XX |
| 提及次数 | X 次 |
| 信息来源 | Exa, 知识星球 |

### 第2-5名: ...

---

## 💰 投资组合建议
| 标的 | 仓位 | 核心逻辑 |
|:-----|:---:|:---------|
| 标的1 | 30% | 政策+订单驱动 |
| 标的2 | 25% | 技术突破 |
| ... | ... | ... |

---

## ⚠️ 风险提示
1. 短期涨幅过大存在回调风险
2. 催化剂不及预期导致股价调整
3. 大盘系统性风险
```

## 💡 使用示例

### 示例1: 分析新板块（固态电池）

```python
report = analyze_sector(
    sector_name="固态电池",
    keywords=["固态电池", "半固态电池", "电解质", "锂电", "宁德时代"]
)
```

### 示例2: 分析热门板块（人形机器人）

```python
report = analyze_sector(
    sector_name="人形机器人",
    keywords=["人形机器人", "特斯拉Optimus", "机器人", "减速器", "电机"]
)
```

### 示例3: 比较多个板块

```python
sectors = {
    "AI算力": ["AI算力", "GPU", "服务器", "数据中心"],
    "新能源": ["新能源", "锂电", "光伏", "储能"],
    "军工": ["军工", "导弹", "卫星", "航空航天"]
}

results = analyze_multiple_sectors(sectors)

# 比较各板块TOP1标的
for sector, report in results.items():
    # 提取TOP1标的得分
    pass
```

## ⚙️ 核心类说明

### SectorAnalyzer 类

```python
analyzer = SectorAnalyzer()

# 扫描板块标的
stocks = analyzer.scan_sector_stocks("板块名称", ["关键词"])

# 获取实时行情
stocks = analyzer.get_realtime_data(stocks)

# 评分排序
for stock in stocks:
    stock['score'] = analyzer.score_stock(stock, keywords)

# 分析催化剂
for stock in stocks:
    stock['catalysts'] = analyzer.analyze_catalysts(stock, keywords)

# 计算买卖点
for stock in stocks:
    stock['trade_points'] = analyzer.calculate_trade_points(stock)

# 生成报告
report = analyzer.generate_sector_report("板块名称", ["关键词"])
```

## 🛡️ 风险控制

1. **自动过滤**: 市值<50亿、PE>200、ST股票自动排除
2. **止损计算**: 自动计算8%止损位
3. **仓位建议**: 根据评分自动分配仓位（30%/25%/20%/15%/10%）
4. **风险提示**: 报告中自动包含风险提示

## 📁 文件结构

```
skills/sector-analysis/
├── SKILL.md                          # 本文件
├── scripts/
│   └── sector_analyzer.py            # 核心分析脚本
└── examples/
    └── analyze_6_sectors.py          # 分析6大板块示例
```

## 🔄 更新日志

| 版本 | 时间 | 更新内容 |
|:-----|:-----|:---------|
| v1.0 | 2026-03-02 | 初始版本，实现4步分析流程 |

## 📞 注意事项

1. **需要环境变量**: 确保设置了必要的API密钥
2. **搜索频率限制**: Exa和知识星球有频率限制，大量分析时请控制速度
3. **数据时效性**: 报告基于实时数据，建议在交易时间内使用
4. **投资建议仅供参考**: 不构成实际投资建议，请结合自身情况决策

---

*Skill版本: v1.0*  
*创建时间: 2026-03-02*  
*核心原则: 零硬编码，全自动发现*
