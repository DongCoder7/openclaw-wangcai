---
name: a-sector-analysis
description: |
  A股板块分析与轮动监控Skill。当用户要求分析板块、查看行业轮动、判断市场风格、进行板块配置、查看板块强弱排序、五维景气度评分、板块资金流向或轮动信号时触发。适用于AI算力、半导体、新能源、高股息、创新药等板块的轮动监控和配置决策场景。
---

# A股板块分析Skill (可执行版)

## 核心能力

本Skill整合以下分析方法：
- **五维景气度评分** → 政策/订单/业绩/估值/资金
- **板块轮动信号** → 买入/卖出/中性信号识别
- **市场风格判断** → 成长vs价值风格识别
- **板块配置方案** → 动态仓位建议

## 使用方法

### Python API调用

```python
from skills.a_sector_analysis import SectorRotationAnalyzer, analyze_sector

# 方式1: 使用分析器类
analyzer = SectorRotationAnalyzer()

# 分析单个板块
result = analyzer.analyze_sector("AI算力")
print(analyzer.format_report(result))

# 对比多个板块
compare = analyzer.compare_sectors(['AI算力', '半导体设备', '储能'])

# 获取全市场轮动信号
signals = analyzer.get_rotation_signals()

# 判断市场风格
style = analyzer.detect_market_style()

# 生成配置方案
portfolio = analyzer.generate_portfolio_config(risk_level='medium')

# 方式2: 便捷函数
from skills.a_sector_analysis import (
    analyze_sector,           # 分析单个板块
    compare_sectors,          # 对比多个板块
    get_rotation_signals,     # 获取轮动信号
    detect_market_style,      # 判断市场风格
    generate_portfolio        # 生成配置方案
)

result = analyze_sector("AI算力")
```

### 命令行调用

```bash
# 分析单个板块
cd ~/.openclaw/workspace && python3 -c "from skills.a_sector_analysis import analyze_sector; print(analyze_sector('AI算力'))"

# 对比板块
cd ~/.openclaw/workspace && python3 -c "from skills.a_sector_analysis import compare_sectors; import json; print(json.dumps(compare_sectors(['AI算力', '半导体设备']), indent=2, ensure_ascii=False))"
```

## 板块分级体系

### T0级 - 核心持仓（必配，长期景气）

|板块|权重建议|核心逻辑|代表标的|
|:-----|:--------:|:---------|:---------|
|**AI算力**|15-20%|AI革命基础设施|中际旭创、天孚通信|
|**算力租赁**|8-10%|AI时代"卖水人"|润泽科技、奥飞数据|
|**半导体设备**|10-12%|国产替代最确定|北方华创、中微公司|
|**储能**|8-10%|新能源高景气|阳光电源、宁德时代|
|**高股息红利**|20-25%|防御底仓|长江电力、中国神华|

### T1级 - 进攻持仓（轮动，政策/事件驱动）

|板块|权重建议|催化因素|代表标的|
|:-----|:--------:|:---------|:---------|
|**人形机器人**|5-8%|特斯拉Optimus量产|绿的谐波、三花智控|
|**自动驾驶**|4-6%|FSD入华、城市NOA|德赛西威、伯特利|
|**低空经济**|3-5%|政策放开|万丰奥威、亿航智能|
|**卫星互联网**|3-5%|星网发射|中国卫星、海格通信|
|**创新药**|5-8%|出海加速|百济神州、信达生物|

### T2级 - 卫星持仓（主题博弈）

- 氢能源、商业航天、脑机接口、量子计算
- 权重：2-3%，分散配置

### T3级 - 周期/防御（逆向布局）

- 白酒、光伏、锂电材料、生猪养殖
- 权重：0-10%，估值低位左侧布局

## 五维景气度评分

### 评分维度与权重

|维度|权重|评估内容|
|:-----|:----:|:---------|
|**政策**|30%|国家级政策、地方跟进、监管态度|
|**订单**|25%|龙头订单、产能扩张、pipeline|
|**业绩**|25%|季度业绩、增速变化、超预期程度|
|**估值**|10%|PE历史分位、相对估值|
|**资金**|10%|北向流入、主力资金、连续天数|

### 评分标准

- 5分：极强利好
- 4分：利好
- 3分：中性
- 2分：偏空
- 1分：利空

### 操作信号

- **买入信号**：4个以上维度向好 → 加仓至目标仓位
- **卖出信号**：2个以上维度恶化 → 启动减仓

## 轮动信号识别

### 买入信号（五维共振）

```
触发条件（满足4项以上）：
✓ 政策：国家级政策出台
✓ 订单：龙头订单超预期
✓ 业绩：季度业绩超预期
✓ 估值：PE处于历史30%分位以下
✓ 资金：北向连续3日净流入
```

### 卖出信号（风险警示）

```
触发条件（满足2项以上）：
✗ 政策：政策转向/监管趋严 → 减仓50%
✗ 业绩：季度业绩miss → 减仓30%
✗ 估值：PE处于历史90%分位以上 → 减仓30%
✗ 资金：北向连续5日净流出 → 减仓20%
✗ 技术：跌破60日均线 → 减仓20%
```

## 仓位动态调整

### 基础配置（总仓位上限90%）

```
T0级板块（核心）：60-70%
├── AI算力：15-20%
├── 算力租赁：8-10%
├── 半导体设备：10-12%
├── 储能：8-10%
└── 高股息红利：20-25%

T1级板块（进攻）：15-25%
T2级板块（卫星）：5-10%
T3级板块（逆向）：0-10%
```

### 市场风格调整

|风格|调整策略|
|:-----|:---------|
|**成长风格占优**|T0级AI算力↑至25%，T1级加仓，T3级减仓|
|**价值风格占优**|T0级高股息↑至30%，T1级减仓，T3级加仓|
|**震荡市**|均衡配置，增加高股息比重，T1/T2减仓|

## 输出示例

### 单个板块分析报告

```
================================================================================
📊 AI算力 板块分析报告
================================================================================

分析时间: 2026-02-27 09:30:00
板块分级: T0
建议仓位: 15-20%

【五维景气度评分】
  政策维度: ⭐⭐⭐⭐⭐
  订单维度: ⭐⭐⭐⭐⭐
  业绩维度: ⭐⭐⭐⭐
  估值维度: ⭐⭐⭐
  资金维度: ⭐⭐⭐⭐
  总分: 4.3/5 🟢推荐

【轮动信号】
  信号类型: buy
  信号强度: 4.3
  原因: 4个维度向好，五维共振

【操作建议】
  加仓至目标仓位，🟢推荐

【成分股行情】
  🟢 300308.SZ: 156.80 (+3.25%)
  🟢 300394.SZ: 98.50 (+2.10%)
================================================================================
```

### 板块对比报告

```
板块强弱排序:
1. 🟢 AI算力 - 4.3分
2. 🟢 半导体设备 - 4.1分
3. 🟡 储能 - 3.5分

最强板块: AI算力
```

## 数据结构

### SectorScore 数据类

```python
@dataclass
class SectorScore:
    sector: str      # 板块名称
    policy: int      # 政策维度 1-5
    orders: int      # 订单维度 1-5
    earnings: int    # 业绩维度 1-5
    valuation: int   # 估值维度 1-5
    fund_flow: int   # 资金维度 1-5
    
    @property
    def total_score(self) -> int:  # 加权总分
    @property
    def rating(self) -> str:       # 评级 🟢/🟡/🔴
```

### 分析结果字典

```python
{
    'sector': 'AI算力',
    'tier': 'T0',
    'weight_range': (15, 20),
    'score': {
        'sector': 'AI算力',
        'policy': 5,
        'orders': 5,
        'earnings': 4,
        'valuation': 3,
        'fund_flow': 4,
        'total_score': 4.3,
        'rating': '🟢推荐'
    },
    'quotes': [...],  # 成分股行情
    'rotation_signal': {
        'type': 'buy',
        'strength': 4.3,
        'reason': '4个维度向好，五维共振'
    },
    'recommendation': '加仓至目标仓位，🟢推荐',
    'timestamp': '2026-02-27T09:30:00'
}
```

## 集成到DounaiSystem

```python
# 在 dounai-investment-system/__init__.py 中添加

from skills.a_sector_analysis import SectorRotationAnalyzer

class DounaiSystem:
    def __init__(self):
        self.sector_analyzer = SectorRotationAnalyzer()
    
    def analyze_sector(self, sector: str) -> Dict:
        """板块分析入口"""
        return self.sector_analyzer.analyze_sector(sector)
    
    def compare_sectors(self, sectors: List[str]) -> Dict:
        """板块对比入口"""
        return self.sector_analyzer.compare_sectors(sectors)
    
    def get_sector_rotation_signals(self) -> List[Dict]:
        """轮动信号入口"""
        return self.sector_analyzer.get_rotation_signals()
```

## 配套脚本

|脚本|用途|
|:-----|:-----|
|`__init__.py`|核心模块，SectorRotationAnalyzer类|
|`scripts/sector_daily_report.py`|生成每日板块监控报告|
|`scripts/rotation_scanner.py`|扫描全市场轮动信号|

## 监控流程

### 每日监控

**早盘（9:25-9:30）**：
- [ ] 检查T0板块龙头竞价
- [ ] 确认板块高开/低开幅度

**盘中（10:00/11:00/14:00）**：
- [ ] 跟踪板块涨跌幅排名
- [ ] 监控板块资金净流入
- [ ] 检查北向资金流向

**尾盘（14:30-14:50）**：
- [ ] 决策是否调仓
- [ ] 更新板块评分

### 每周监控

- [ ] 更新板块景气度评分
- [ ] 检查轮动信号
- [ ] 调整下周仓位配置

### 每月监控

- [ ] 更新全板块估值表
- [ ] 更新板块轮动模型
- [ ] 制定下月配置计划

## 更新日志

|日期|更新内容|
|:-----|:---------|
|2026-02-27|创建可执行模块，集成五维评分与轮动信号|
|2026-02-18|初始版本，方法论文档|
