# Historical Data Fetcher Skill

A comprehensive skill for fetching historical stock data from multiple sources with automatic fallback.

## Overview

This skill provides a unified interface to fetch historical stock data from multiple data sources:
- **AKShare** (Primary) - Free, comprehensive A股数据
- **Tushare** (Alternative) - Professional quality, requires token
- **Tencent API** (Realtime backup) - No auth needed, good for realtime quotes
- **Local Database** (Cache) - Fast, offline access to existing data

## Current Status

| Source | Status | Notes |
|--------|--------|-------|
| Local DB | ✅ Available | 5,459 stocks, 15 factors, 1996-2026 |
| Tencent API | ✅ Available | Realtime quotes, PE/PB data |
| AKShare | ❌ Unavailable | Connection issues (remote disconnected) |
| Tushare | ❌ No Token | Requires configuration |

## Quick Start

### 1. Test All Data Sources
```bash
cd /root/.openclaw/workspace
python3 skills/historical-data-fetcher/test_sources.py
```

### 2. Get Factor Data Summary
```bash
python3 skills/historical-data-fetcher/fetch_factors.py --summary
```

Output:
```
Latest Date: 20260224
Stock Count: 5122
Factor Count: 15
Available Factors: ret_20, ret_60, ret_120, vol_20, vol_ratio, ...
```

### 3. Get Realtime Quotes (Tencent API)
```python
from skills.historical-data-fetcher.sources.tencent_source import TencentSource

tencent = TencentSource()
df = tencent.get_realtime_quotes(['000001.SZ', '600519.SH'])
print(df[['ts_code', 'name', 'price', 'pe', 'pb']])
```

### 4. Get Historical Data from Local DB
```python
from skills.historical-data-fetcher.sources.local_source import LocalSource

local = LocalSource()
df = local.get_daily_data('000001.SZ', '20260201', '20260224')
print(df[['date', 'close', 'ret_20', 'vol_ratio']])
```

## File Structure

```
historical-data-fetcher/
├── SKILL.md                    # This file
├── test_sources.py             # Test all data sources
├── fetch_daily.py              # Fetch daily price data
├── fetch_factors.py            # Fetch/calculate factor data
├── example_usage.py            # Usage examples
└── sources/
    ├── __init__.py             # Base classes and DataFetcher
    ├── akshare_source.py       # AKShare implementation
    ├── tencent_source.py       # Tencent API implementation
    └── local_source.py         # Local SQLite DB implementation
```

## Available Data

### Local Database Coverage
- **Stocks**: 5,459 A股
- **Date Range**: 1996-05-06 to 2026-02-24
- **Total Records**: 1,080,492
- **Recent Coverage**: 5,100+ stocks per day

### Available Factors (15个)
```python
# Returns
'ret_20'        # 20日收益率
'ret_60'        # 60日收益率
'ret_120'       # 120日收益率

# Volatility
'vol_20'        # 20日波动率
'vol_ratio'     # 量比

# Moving Averages
'ma_20'         # 20日均线
'ma_60'         # 60日均线

# Price Position
'price_pos_20'  # 20日价格位置(0-1)
'price_pos_60'  # 60日价格位置(0-1)
'price_pos_high' # 历史高点位置

# Volume
'vol_ratio_amt' # 金额量比

# Sentiment
'money_flow'    # 资金流向
'rel_strength'  # 相对强度
'mom_accel'     # 动量加速
'profit_mom'    # 收益动量
```

## Python API

### DataFetcher - Unified Interface
```python
from skills.historical-data-fetcher.sources import DataFetcher

fetcher = DataFetcher()

# Test all sources
status = fetcher.test_sources()
# {'akshare': False, 'tencent': True, 'local': True}

# Get data with automatic fallback
df = fetcher.get_daily_data('000001.SZ', '20240101', '20241231')

# Batch fetch
results = fetcher.batch_fetch(
    codes=['000001.SZ', '600519.SH'],
    start='20240101',
    end='20241231'
)
```

### Individual Sources
```python
# Local Database
from skills.historical-data-fetcher.sources.local_source import LocalSource

local = LocalSource()
stocks = local.get_stock_list()          # All stocks
df = local.get_daily_data(code, s, e)    # Historical data
coverage = local.get_date_coverage()     # Data coverage info

# Tencent API
from skills.historical-data-fetcher.sources.tencent_source import TencentSource

tencent = TencentSource()
rt = tencent.get_realtime_quotes(codes)  # Realtime quotes
```

## Command Line Usage

### Fetch Daily Data
```bash
# Fetch specific stocks
python3 skills/historical-data-fetcher/fetch_daily.py \
    --codes 000001.SZ,600519.SH \
    --start 20240101 \
    --end 20241231

# Update latest only
python3 skills/historical-data-fetcher/fetch_daily.py --update

# Fetch all stocks (limit for testing)
python3 skills/historical-data-fetcher/fetch_daily.py --all --limit 100
```

### Fetch Factor Data
```bash
# Show summary
python3 skills/historical-data-fetcher/fetch_factors.py --summary

# Fetch from Tencent (for PE/PB data)
python3 skills/historical-data-fetcher/fetch_factors.py --fetch-tencent
```

## Integration with Factor Library

This skill integrates seamlessly with the multi-factor model:

```python
# Use in factor model
from skills.historical-data-fetcher.sources.local_source import LocalSource
from tools.factor_library import FactorLibrary

local = LocalSource()
library = FactorLibrary()

# Get data
df = local.get_daily_data('000001.SZ', '20240101', '20241231')

# Calculate factors
df = library.calc_all_factors(df)
```

## Troubleshooting

### AKShare Connection Issues
```bash
# Check if AKShare is installed
python3 -c "import akshare; print(akshare.__version__)"

# Update AKShare
pip install --upgrade akshare

# If still failing, use Tencent API or Local DB as fallback
```

### No Data Available
1. Check data source availability: `test_sources.py`
2. Verify date range is within database coverage
3. Use local database for historical data (most reliable)

### Missing Factors
Current local DB has 15 technical factors. For more factors:
1. Calculate from price data (see `fetch_factors.py`)
2. Fetch from external sources when AKShare is available
3. Request specific factor additions

## Future Enhancements

- [ ] Add more data sources (Baostock, JoinQuant)
- [ ] Implement incremental data updates
- [ ] Add data validation and quality checks
- [ ] Support for fundamental data (financial statements)
- [ ] Add sector/industry classification data
- [ ] Support for index data

## References

- **Factor Library**: `tools/factor_library.py`
- **Multi-Factor Model**: `tools/multi_factor_model.py`
- **Backtest Engine**: `tools/backtest_engine.py`
