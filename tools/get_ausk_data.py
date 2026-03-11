#!/root/.openclaw/workspace/venv/bin/python3
"""获取奥士康股票基础数据"""
from longport.openapi import Config, QuoteContext
import json

config = Config.from_env()
ctx = QuoteContext(config)

# 查询奥士康股票信息 (002913.SZ)
stock_code = '002913.SZ'

# 获取实时行情
quote = ctx.quote([stock_code])
static = ctx.static_info([stock_code])

# 提取数据
price = float(quote[0].last_done)
total_shares = float(static[0].total_shares)
eps_ttm = float(static[0].eps_ttm) if static[0].eps_ttm else 0

# 计算PE_TTM
pe_ttm = price / eps_ttm if eps_ttm > 0 else 0

# 计算市值
market_cap = price * total_shares / 1e8

# 输出JSON格式结果
result = {
    "stock_code": stock_code,
    "name": static[0].name_cn,
    "price": price,
    "prev_close": float(quote[0].prev_close),
    "change_pct": round((price - float(quote[0].prev_close)) / float(quote[0].prev_close) * 100, 2),
    "total_shares": total_shares,
    "total_shares_yi": round(total_shares / 1e8, 2),
    "eps_ttm": eps_ttm,
    "pe_ttm": round(pe_ttm, 2),
    "market_cap": round(market_cap, 2),
    "open": float(quote[0].open),
    "high": float(quote[0].high),
    "low": float(quote[0].low),
    "volume": int(quote[0].volume),
    "turnover": round(float(quote[0].turnover) / 1e8, 2),
    "timestamp": str(quote[0].timestamp)
}

print(json.dumps(result, ensure_ascii=False, indent=2))
