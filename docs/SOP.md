# 📚 OpenClaw投资策略系统 SOP

## 一、系统概览

本系统集成了长桥API、知识星球、v26因子模型等多个数据源，用于A股/H股/美股投资决策。

---

## 二、核心配置

### 2.1 长桥API配置
**文件**: `~/.openclaw/workspace/.longbridge.env`

```bash
LONGPORT_APP_KEY="68f2e2a62a7911943bd05db4bd584b6c"
LONGPORT_APP_SECRET="ede99d5e90a810122983f159f2bc947aa962a0844f13f6e540b90981937a26dd"
LONGPORT_ACCESS_TOKEN="m_eyJhbGciOiJSUzI1NiIsImtpZCI6ImQ5YWRiMGIxYTdlNzYxNzEiLCJ0eXAiOiJKV1QifQ..."
```

**使用方式**:
```python
from longbridge_api import get_longbridge_api
api = get_longbridge_api()
quote = api.get_quote("002371.SZ")
```

### 2.2 知识星球配置
**文件**: `~/.openclaw/workspace/config/zsxq_source.md`

```bash
# 获取调研纪要
python3 tools/zsxq_fetcher.py search 存储芯片
python3 tools/zsxq_fetcher.py latest 5
```

---

## 三、定时任务配置

### 3.1 Crontab配置
```bash
# 编辑crontab
crontab -e

# 添加以下任务
# 美股隔夜总结 (每日8:30)
30 8 * * * cd ~/.openclaw/workspace && export $(cat .longbridge.env | xargs) && python3 skills/us-market-analysis/scripts/generate_report_longbridge.py >> logs/us_market.log 2>&1

# A+H开盘前瞻 (每日9:15)
15 9 * * * cd ~/.openclaw/workspace && export $(cat .longbridge.env | xargs) && python3 skills/ah-market-preopen/scripts/generate_report_longbridge.py >> logs/ah_market.log 2>&1

# 知识星球信息 (每2小时)
0 */2 * * * cd ~/.openclaw/workspace && python3 tools/heartbeat_zsxq_fetch.py >> logs/zsxq.log 2>&1

# 策略优化器 (每15分钟)
*/15 * * * * cd ~/.openclaw/workspace && python3 tools/auto_optimizer.py >> logs/optimizer.log 2>&1
```

### 3.2 Heartbeat任务
**文件**: `~/.openclaw/workspace/HEARTBEAT.md`

每次心跳执行:
1. 整点状态汇报
2. 模拟盘跟踪
3. Git同步

---

## 四、核心Skills

### 4.1 产业链深度分析
**路径**: `skills/industry-chain-analysis/`

**功能**:
- 产业链结构拆解
- v26全因子评分
- 价格周期分析
- 知识星球信息集成

**使用**:
```bash
# 分析存储芯片产业链
python3 -c "
from tools.zsxq_fetcher import search_industry_info
search_industry_info('存储芯片')
"
```

### 4.2 美股市场分析
**路径**: `skills/us-market-analysis/`

**功能**:
- 主要指数行情
- 板块强弱排序
- 中概股监控
- 对A股策略启示

**使用**:
```bash
source .longbridge.env
python3 skills/us-market-analysis/scripts/generate_report_longbridge.py
```

### 4.3 A+H开盘前瞻
**路径**: `skills/ah-market-preopen/`

**功能**:
- A股核心标的监控
- 港股核心标的监控
- 开盘策略建议

**使用**:
```bash
source .longbridge.env
python3 skills/ah-market-preopen/scripts/generate_report_longbridge.py
```

### 4.4 个股深度分析
**路径**: `skills/a-stock-analysis/`

**功能**:
- v26全因子评分
- 财务分析
- 建仓位置建议

**使用**:
```bash
python3 skills/a-stock-analysis/scripts/v26_factor_analyzer.py --code 002371
```

---

## 五、常用操作SOP

### 5.1 获取实时行情
```bash
# 加载配置
export $(cat ~/.openclaw/workspace/.longbridge.env | xargs)

# 获取单个股票
python3 -c "
from longbridge_api import get_longbridge_api
api = get_longbridge_api()
print(api.get_quote('002371.SZ'))
"
```

### 5.2 获取知识星球信息
```bash
# 搜索行业信息
python3 tools/zsxq_fetcher.py search 存储芯片

# 获取最新内容
python3 tools/zsxq_fetcher.py latest 10
```

### 5.3 运行策略优化器
```bash
# 手动运行
python3 tools/auto_optimizer.py

# 查看结果
cat quant/optimizer/latest_report.txt
```

### 5.4 生成投资组合报告
```bash
# 存储芯片产业链分析
python3 -c "
from longbridge_api import get_longbridge_api
api = get_longbridge_api()

stocks = ['002371.SZ', '688012.SH', '688072.SH', '688120.SH', '688019.SH']
quotes = api.get_quotes(stocks)

for q in quotes:
    print(f\"{q['symbol']}: {q['price']:.2f} ({q['change']:+.2f}%)\")
"
```

---

## 六、文件结构

```
~/.openclaw/workspace/
├── .longbridge.env              # 长桥API密钥
├── .tushare.env                 # Tushare密钥
├── config/
│   └── zsxq_source.md          # 知识星球配置
├── tools/
│   ├── longbridge_api.py       # 长桥API封装
│   ├── zsxq_fetcher.py         # 知识星球获取
│   ├── heartbeat_zsxq_fetch.py # Heartbeat任务
│   └── auto_optimizer.py       # 自动优化器
├── skills/
│   ├── industry-chain-analysis/  # 产业链分析
│   ├── us-market-analysis/       # 美股分析
│   ├── ah-market-preopen/        # A+H开盘前瞻
│   └── a-stock-analysis/         # 个股分析
├── data/
│   ├── us_market_daily_*.md     # 美股报告
│   ├── ah_market_preopen_*.md   # A+H报告
│   └── zsxq_updates.log         # 知识星球日志
└── quant/
    └── optimizer/
        └── latest_report.txt    # 优化器报告
```

---

## 七、故障排查

### 7.1 长桥API连接失败
```bash
# 检查环境变量
echo $LONGPORT_APP_KEY

# 测试连接
python3 -c "
from longbridge_api import get_longbridge_api
api = get_longbridge_api()
print(api.get_quote('00700.HK'))
"
```

### 7.2 知识星球获取失败
```bash
# 检查Token是否过期
python3 tools/zsxq_fetcher.py latest 1

# Token过期需重新获取
```

### 7.3 优化器运行失败
```bash
# 检查数据库连接
python3 -c "import sqlite3; conn = sqlite3.connect('historical.db'); print('OK')"

# 检查日志
tail -100 logs/optimizer.log
```

---

## 八、更新记录

| 日期 | 更新内容 |
|:-----|:---------|
| 2026-02-25 | 集成longport SDK，完善美股/A+H报告模块 |
| 2026-02-25 | 添加知识星球自动获取功能 |
| 2026-02-25 | 更新产业链分析skill，集成信息源 |

---

## 九、联系方式

如有问题，请检查:
1. 环境变量是否正确配置
2. API密钥是否过期
3. 日志文件是否有错误信息
