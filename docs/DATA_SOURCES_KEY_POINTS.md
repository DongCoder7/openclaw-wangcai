# 关键数据源使用说明

## 知识星球数据集成要点

### 1. 数据位置
- **原始数据**: `data/zsxq/raw/YYYY-MM-DD.json`
- **周统计**: `data/zsxq/weekly_stats.json`
- **日报**: `data/zsxq/daily_report_YYYYMMDD.txt`

### 2. 数据更新频率
- **实时抓取**: 每2小时拉取最新5条
- **日终抓取**: 每天23:30完整抓取当天数据
- **回补机制**: 支持断点续跑，累积历史数据

### 3. 个股分析使用知识星球数据

在 `skills/dounai-investment-system/scripts/` 中：

```python
# 方法1: 使用优化版多源搜索（推荐）
from multi_source_news_v2 import search_multi_source_news

news = search_multi_source_news(
    keyword="股票名称",
    stock_code="000001.SZ",
    stock_name="平安银行"
)
```

```python
# 方法2: 读取历史数据进行分析
from pathlib import Path
import json
from datetime import datetime, timedelta

def get_recent_zsxq_data(days=30):
    '''获取最近N天知识星球数据'''
    raw_dir = Path('/root/.openclaw/workspace/data/zsxq/raw')
    all_data = []
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        file_path = raw_dir / f"{date}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
                all_data.extend(data)
    
    return all_data

# 搜索特定股票相关内容
def search_stock_in_zsxq(stock_name, days=30):
    '''在知识星球历史数据中搜索股票'''
    data = get_recent_zsxq_data(days)
    results = []
    
    for topic in data:
        content = topic.get('content', '') + topic.get('title', '')
        if stock_name in content:
            results.append(topic)
    
    return results
```

### 4. 产业链/板块分析使用知识星球数据

```python
from multi_source_news_v2 import search_industry_chain_news

# 产业链上下游搜索
news = search_industry_chain_news(
    industry="半导体",
    upstream="硅片 光刻胶",
    downstream="芯片设计 封测"
)
```

### 5. 景气度分析数据来源

分析时应综合以下数据源：

| 数据源 | 用途 | 获取方式 |
|--------|------|----------|
| 知识星球 | 产业调研、专家观点、供需变化 | `multi_source_news_v2.py` |
| Exa全网 | 最新新闻、公告、研报 | Exa MCP |
| 新浪财经 | 财经新闻、市场动态 | API接口 |
| 行情数据 | 价格、成交量、资金流向 | 长桥API |

### 6. 数据质量保证

- **去重机制**: seen_ids.txt 全局去重
- **断点续跑**: checkpoint.json 保存进度
- **限流处理**: 5-10秒间隔，code=1059时30秒退避
- **入库口径**: 有标题或正文即入库（标题-only保留作线索）

### 7. 注意事项

1. **频率控制**: 知识星球API有严格限流，调用需间隔3秒以上
2. **数据时效**: 日终抓取在23:30执行，分析时优先使用当日数据
3. **搜索策略**: 个股分析时用股票名称搜索，板块分析时用行业关键词
4. **异常处理**: 网络错误或限流时自动重试，最大重试3次

### 8. 常用关键词库

```python
SECTOR_KEYWORDS = {
    'AI算力': ['AI', 'GPU', '英伟达', '算力', '服务器', 'GTC'],
    '半导体': ['半导体', '芯片', '光刻', '封测', '国产替代'],
    '新能源': ['新能源', '锂电', '光伏', '储能', '宁德时代'],
    '军工': ['军工', '军贸', '导弹', '航天', '卫星'],
    '资源': ['黄金', '铜', '锂', '稀土', '化工涨价'],
}
```
