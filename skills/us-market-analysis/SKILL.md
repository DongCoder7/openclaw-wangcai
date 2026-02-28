---
name: us-market-analysis
description: |
  美股市场深度分析，每日生成美股板块、个股行情报告。
  使用场景：
  1. 定时生成美股隔夜分析报告（每日8:30）
  2. 手动触发美股市场分析
  3. 获取美股板块强弱排序、亮点个股、拖累因素
  4. 为A股开盘提供策略启示

  分析内容包括：
  - 主要指数表现（道琼斯、纳斯达克、标普500）
  - 10大板块强弱排序（光通讯、半导体、AI算力、科技巨头等）
  - 核心驱动因子识别（技术面+新闻面→A股传导）
  - 应对策略建议
  - 市场展望与风险提示

  数据源（严格标注）：
  - 个股行情: 长桥API (Longbridge OpenAPI)
  - 个股市值: 长桥API静态数据 (总股本×当前股价)
  - 美股指数: 腾讯财经API (qt.gtimg.cn)
  - 国际新闻: Exa MCP全网语义搜索（P1高优先级）+ 新浪财经 + 华尔街见闻 + 第一财经
  - 新闻分析: 70+关键词映射 + 影响强度评估
  - 市值过滤: >500亿美元

  触发关键词：美股分析、美股报告、US market、us-market-summary
---

# 美股市场深度分析

## 功能

生成完整的美股市场分析报告，包括：

1. **主要指数表现** - 道琼斯、纳斯达克、标普500
2. **板块强弱排序** - 10大板块按涨跌幅排名（市值>500亿美元）
3. **核心驱动因子** - 技术面+新闻面双重分析（70+关键词）
4. **应对策略** - 板块级别操作建议
5. **市场展望** - 趋势判断、风险提示

## 数据源说明（重要）

### 行情数据
| 数据类型 | 数据源 | 获取方式 |
|---------|--------|---------|
| 个股实时行情 | 长桥API | `QuoteContext.quote()` |
| 个股市值 | 长桥API | `QuoteContext.static_info()` (总股本×股价) |
| 美股指数 | 腾讯财经API | `https://qt.gtimg.cn/q=usDJI` |
| 涨跌幅计算 | 本地计算 | `(现价-昨收)/昨收 × 100%` |

### 新闻数据（多源聚合 - 已集成Exa全网搜索）
| 优先级 | 数据源 | 类型 | 说明 |
|:------:|--------|------|------|
| **P1** | **Exa全网搜索** | AI语义搜索 | `mcporter call exa.web_search_exa()` |
| P2 | 新浪财经 | API | `https://feed.mix.sina.com.cn/api/roll/get` |
| P3 | 华尔街见闻 | API | `https://api-one.wallstcn.com/apiv1/content/information-flow` |
| P4 | 第一财经 | API | `https://www.yicai.com/api/ajax/getlatest` |
| P5 | 东方财富 | API | `https://np-anotice-stock.eastmoney.com/api/security/ann` |
| P6 | 财联社 | RSS | `https://www.cls.cn/telegraph` |
| P7 | 和讯网 | RSS | `http://rss.hexun.com/finance.xml` |
| P8 | FT中文网 | RSS | `https://www.ftchinese.com/rss/news` |
| P9 | Agent Reach | 工具集 | YouTube + RSS + Jina Reader |
| - | 腾讯财经 | API | 备用（API常返回空数据） |
| - | 网易财经 | 网页 | 备用（页面改版中） |

**Exa搜索配置**:
```bash
# 安装mcporter
npm install -g mcporter

# 配置Exa MCP
mcporter config add exa https://mcp.exa.ai/mcp

# 验证配置
mcporter config list
```

**搜索调用示例**（已在脚本中自动集成）:
```python
# 美股新闻搜索
mcporter call 'exa.web_search_exa({"query": "美股科技股最新动态", "numResults": 5})'

# 美联储相关
mcporter call 'exa.web_search_exa({"query": "美联储利率决议", "numResults": 5})'

# 中概股相关
mcporter call 'exa.web_search_exa({"query": "中概股最新动态", "numResults": 5})'
```

**市值过滤规则**：
- 市值 = 股价 × 总股本
- 只保留市值 > 500亿美元的股票
- 避免小市值股票噪音干扰

**新闻分析规则**：
- 关键词库：70+财经关键词（地缘政治、AI、利率、贸易、疫情等）
- 影响强度：1-5星评级（⭐-⭐⭐⭐⭐⭐）
- 驱动因子标注：技术面 / 新闻面
- 去重机制：标题相似度去重 + 关键词合并

## 使用方法

### 定时任务 (长桥API版 - 推荐)
```bash
# 每日8:30自动运行
30 8 * * * cd ~/.openclaw/workspace && source .longbridge.env && python3 skills/us-market-analysis/scripts/generate_report_longbridge.py
```

### 手动触发 (长桥API版)
```bash
cd ~/.openclaw/workspace
source .longbridge.env
python3 skills/us-market-analysis/scripts/generate_report_longbridge.py
```

### 环境变量配置
长桥API密钥已配置在 `~/.openclaw/workspace/.longbridge.env`
```
LONGPORT_APP_KEY=xxx
LONGPORT_APP_SECRET=xxx
LONGPORT_ACCESS_TOKEN=xxx
```

### 用户指令
- "生成美股报告"
- "分析美股市场"
- "美股隔夜总结"
- "US market summary"

## 报告结构

### 一、主要指数表现
- 道琼斯、纳斯达克、标普500涨跌幅
- 趋势判断、风险等级

### 二、板块强弱排序
- 10大板块平均涨跌幅
- 板块内个股数量（市值>500亿）
- 领涨股、A股映射标的

### 三、核心驱动因子（美股→A股传导）
| 驱动因子 | 重要度 | 美股现象 | A股影响 | 来源 |

来源分为：
- **技术面**: 基于行情数据计算（指数/板块/个股异动）
- **新闻面**: 基于多源财经新闻关键词分析

**影响强度评级**：
- ⭐⭐⭐⭐⭐ 极高：重大事件/政策/财报
- ⭐⭐⭐⭐ 高：板块异动>5%或重大新闻
- ⭐⭐⭐ 中：板块异动>3%或中等新闻
- ⭐⭐ 低：一般性市场波动

### 四、应对策略
| 板块 | 操作 | 建议 | A股关注标的 |

### 五、重点个股
- 🔥 亮点个股 TOP5（市值>500亿）
- 🔻 拖累因素 TOP5（市值>500亿）

### 六、市场展望与总结
- 美股趋势判断
- 风险等级
- A股影响
- 操作建议
- 核心风险

### 七、数据来源
- 行情数据：长桥API + 腾讯财经API
- 新闻数据：新浪财经 + 腾讯财经 + 网易财经
- 新闻分析：70+关键词映射 + 影响强度评估
- 映射关系：人工梳理
- 风险提示

## 关键词库（部分）

| 分类 | 关键词 | 映射板块 | 影响 |
|------|--------|---------|------|
| 地缘政治 | 战争、冲突、制裁、伊朗、中东 | 能源 | 利好⭐⭐⭐⭐ |
| AI科技 | 英伟达、人工智能、芯片、大模型 | AI算力/半导体 | 关联⭐⭐⭐⭐⭐ |
| 货币政策 | 通胀、加息、降息、美联储 | 金融/科技 | 利空/利好⭐⭐⭐⭐ |
| 贸易 | 关税、中美、脱钩 | 中概互联 | 利空⭐⭐⭐⭐ |
| 生物医药 | 疫情、疫苗、减肥药 | 生物医药 | 利好⭐⭐⭐ |
| 光通讯 | 光模块、5G、通信 | 光通讯 | 利好⭐⭐⭐ |
| 能源 | 原油、OPEC、新能源 | 能源 | 关联⭐⭐⭐⭐ |

完整关键词库见脚本 `generate_report_longbridge.py` 中 `keyword_mapping` 字典。

## 板块列表

| 板块 | 代表个股 | A股映射 |
|------|----------|---------|
| AI算力 | NVDA, AVGO, AMD, MRVL | 寒武纪、海光信息、浪潮信息 |
| 半导体 | NVDA, AMD, TSM, ASML | 中芯国际、北方华创、中微公司 |
| 科技巨头 | AAPL, MSFT, GOOGL, META | 小米集团、美团、比亚迪 |
| 光通讯 | ANET, LITE, CIEN, AAOI | 中际旭创、新易盛、天孚通信 |
| 生物医药 | LLY, NVO, JNJ, MRK | 恒瑞医药、迈瑞医疗、药明康德 |
| 存储/数据中心 | WDC, SNOW, NET, DDOG | 兆易创新、澜起科技、江波龙 |
| 能源 | XOM, CVX, COP, OXY | 中国石油、中国海油、陕西煤业 |
| 金融 | V, MA, JPM, BAC, GS | 招商银行、中国平安、东方财富 |
| 消费 | WMT, COST, HD, NKE | 贵州茅台、五粮液、美的集团 |
| 中概互联 | BABA, JD, PDD, NIO | 阿里巴巴、京东、拼多多 |

## 产出文件

- 报告保存：`~/.openclaw/workspace/data/us_market_daily_YYYYMMDD.md`
- 发送记录：`~/.openclaw/workspace/tools/us_market_send.log`

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| 2.2 | 2026-02-28 | 扩展新闻关键词（70+）、多新闻源聚合、影响强度评估 |
| 2.1 | 2026-02-28 | 新增国际新闻分析模块（新浪财经API） |
| 2.0 | 2026-02-28 | 新增市值过滤(>500亿)、核心驱动因子、应对策略、市场展望 |
| 1.1 | 2026-02-28 | 修复数据错位问题、新增指数显示 |
| 1.0 | 2026-02-24 | 初始版本，基础板块分析 |

## 风险提示

⚠️ 本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。

- 数据可能存在延迟（T-1日数据）
- 市值数据基于上一交易日收盘价计算
- A股映射关系基于业务关联性，可能存在偏差
- 新闻分析基于关键词匹配，可能遗漏或误判
- 多新闻源可能重复报道同一事件
