# 数据源使用规范

## 数据源区分原则

根据数据的实时性要求和用途，严格区分使用不同的数据源：

| 场景 | 数据源 | 原因 |
|------|--------|------|
| **实时行情** (10分钟级监控) | 长桥API | 毫秒级延迟，实时性高 |
| **历史回测** (2018-2025) | Tushare | 数据完整，成本低 |
| **盘中决策** (9:15/14:30) | 长桥API | 需要最新价格 |
| **财务数据** | Tushare/AkShare | 低频更新，本地存储 |

---

## 1. 长桥API (Longbridge)

### 用途
- ✅ 10分钟级VQM持仓监控 (`vqm_trading_monitor.py`)
- ✅ 开盘前瞻报告 (`ah_market_preopen.py`)
- ✅ 实时止损检查
- ✅ 盘中交易提醒

### 配置
```bash
# Token已保存在 ~/.openclaw/workspace/.longbridge.env
export LONGBRIDGE_APP_KEY="68f2e2a62a7911943bd05db4bd584b6c"
export LONGBRIDGE_APP_SECRET="ede99d5e90a810122983f159f2bc947aa962a0844f13f6e540b90981937a26dd"
export LONGBRIDGE_ACCESS_TOKEN="..."
```

### 使用示例
```python
from tools.longbridge_provider import LongbridgeDataProvider

provider = LongbridgeDataProvider()
quote = provider.get_realtime_quote('600519', market='CN')
```

---

## 2. Tushare

### 用途
- ✅ 历史数据本地化 (2018-2025)
- ✅ 策略回测 (`vqm_backtest_engine.py`)
- ✅ 财务指标计算 (PE/ROE/PB)
- ✅ 选股模型训练

### 配置
```bash
# 需自行申请Tushare Token
export TUSHARE_TOKEN="your_token_here"
```

### 使用示例
```python
from tools.tushare_data_manager import TushareDataManager

manager = TushareDataManager()
# 下载历史数据
manager.batch_download()
# 读取数据
df = manager.get_daily_data('000001.SZ', start_date='20180101')
```

---

## 3. 腾讯API (回退)

### 用途
- ⚠️ 长桥API失败时的回退
- ⚠️ 免费备用数据源

### 使用示例
```python
from tools.data_utils import StockDataProvider

provider = StockDataProvider(use_longbridge=False)  # 不使用长桥
quote = provider.get_realtime_quote('600519')
```

---

## 模块对应关系

| 模块 | 主要数据源 | 回退数据源 | 用途 |
|------|-----------|-----------|------|
| `longbridge_provider.py` | 长桥API | - | 实时行情封装 |
| `tushare_data_manager.py` | Tushare | - | 历史数据管理 |
| `data_utils.py` | 长桥(可选) | 腾讯→AKShare | 通用数据接口 |
| `vqm_trading_monitor.py` | 长桥API | 腾讯API | 交易监控 |
| `ah_market_preopen.py` | 长桥API | 腾讯API | 开盘前瞻 |
| `vqm_backtest_engine.py` | Tushare本地 | - | 策略回测 |

---

## 数据流向图

```
┌─────────────────────────────────────────────────────────────┐
│                      实时场景                                │
│  ┌──────────────┐     ┌──────────────┐                     │
│  │ 10分钟监控   │     │ 开盘前瞻     │                     │
│  └──────┬───────┘     └──────┬───────┘                     │
│         │                    │                              │
│         ▼                    ▼                              │
│  ┌──────────────┐     ┌──────────────┐                     │
│  │ 长桥API      │────▶│ 失败时回退   │                     │
│  │ (毫秒级)     │     │ 腾讯API      │                     │
│  └──────────────┘     └──────────────┘                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      回测场景                                │
│  ┌──────────────┐                                          │
│  │ 策略回测     │                                          │
│  └──────┬───────┘                                          │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐     ┌──────────────┐                     │
│  │ Tushare API  │────▶│ 本地SQLite   │                     │
│  │ (下载历史)   │     │ (2018-2025)  │                     │
│  └──────────────┘     └──────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 任务配置建议

### Cron任务 (实时)
```json
{
  "name": "vqm-trading-monitor",
  "schedule": "*/10 9-15 * * 1-5",  // 交易日每10分钟
  "command": "python3 tools/vqm_trading_monitor.py",
  "model": "kimi-coding/k2p5"
}
```

### 一次性任务 (数据下载)
```bash
# 下载Tushare历史数据
python3 tools/tushare_data_manager.py
```

### 定期回测
```bash
# 运行策略回测
python3 quant/vqm_backtest_engine.py
```

---

## 注意事项

1. **长桥API限制**: 注意频率限制，合理使用缓存
2. **Tushare积分**: 高级数据需要积分，注意用量
3. **数据一致性**: 实时数据和历史数据可能存在差异
4. **本地存储**: 历史数据存储在 `~/.openclaw/workspace/data/tushare/`
