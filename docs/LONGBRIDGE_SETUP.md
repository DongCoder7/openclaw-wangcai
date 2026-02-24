# 长桥API配置说明

## 简介

长桥API（Longbridge OpenAPI）提供A股、港股、美股的实时行情数据。

优势：
- 实时性高（毫秒级延迟）
- 覆盖A股/港股/美股
- 支持WebSocket实时推送

## 配置步骤

### 1. 注册长桥账户

访问 https://open.longbridge.com 注册开发者账户

### 2. 创建应用获取API密钥

在开发者控制台：
1. 创建新应用
2. 获取 **App Key** 和 **App Secret**
3. （可选）获取 **Access Token**

### 3. 配置环境变量

在 `~/.bashrc` 或 `~/.zshrc` 中添加：

```bash
export LONGBRIDGE_APP_KEY="your_app_key_here"
export LONGBRIDGE_APP_SECRET="your_app_secret_here"
# 可选：如果有Access Token
export LONGBRIDGE_ACCESS_TOKEN="your_access_token_here"
```

然后执行：
```bash
source ~/.bashrc
```

### 4. 验证配置

```bash
cd ~/.openclaw/workspace/tools
python3 longbridge_provider.py
```

## 使用方式

### 方式1：直接使用长桥API

```python
from longbridge_provider import LongbridgeDataProvider

provider = LongbridgeDataProvider()

# 获取A股实时行情
quote = provider.get_realtime_quote('600519', market='CN')
print(f"茅台: ¥{quote['price']}, 涨跌: {quote['change_pct']}%")

# 批量获取
quotes = provider.get_realtime_quotes(['000001', '600036'], market='CN')

# 获取港股
hk_quote = provider.get_realtime_quote('00700', market='HK')
```

### 方式2：使用DataSourceManager（自动回退）

```python
from vqm_trading_monitor import DataSourceManager

ds = DataSourceManager()
quotes = ds.get_realtime_quotes(['600519', '000001'])
# 优先长桥，失败自动回退到腾讯API
```

### 方式3：原有接口启用长桥

```python
from data_utils import StockDataProvider

# 启用长桥（需配置环境变量）
provider = StockDataProvider(use_longbridge=True)

# 原有接口不变
quote = provider.get_realtime_quote('600519')
```

## API限制

- 频率限制：请参考长桥官方文档
- 数据范围：A股、港股、美股
- 实时性：行情延迟约100-500ms

## 故障排查

### 问题1：连接失败

检查环境变量：
```bash
echo $LONGBRIDGE_APP_KEY
echo $LONGBRIDGE_APP_SECRET
```

### 问题2：API权限不足

确认应用已开通所需权限：
- 行情订阅权限
- 实时报价权限

### 问题3：数据获取失败

检查股票代码格式：
- A股：`600519` 或 `000001`（自动转换为 `600519.SH` / `000001.SZ`）
- 港股：`00700`（自动转换为 `00700.HK`）
- 美股：`AAPL`（自动转换为 `AAPL.US`）

## 相关脚本

| 脚本 | 用途 |
|------|------|
| `longbridge_provider.py` | 长桥API封装 |
| `vqm_trading_monitor.py` | VQM交易监控（已集成长桥） |
| `ah_market_preopen.py` | 开盘前瞻报告（已集成长桥） |
| `data_utils.py` | 通用数据工具（已集成长桥选项） |

## 更新日志

- 2026-02-20: 初始集成长桥API
