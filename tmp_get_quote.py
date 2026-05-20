#!/root/.openclaw/workspace/venv/bin/python3
from longport.openapi import Config, QuoteContext

config = Config.from_env()
ctx = QuoteContext(config)

# 获取实时行情
quote = ctx.quote(['688300.SH'])
print('实时行情:')
for q in quote:
    print(f'  代码: {q.symbol}')
    print(f'  最新价: {q.last_done}')
    print(f'  开盘价: {q.open}')
    print(f'  最高价: {q.high}')
    print(f'  最低价: {q.low}')
    print(f'  成交量: {q.volume}')
    print(f'  成交额: {q.turnover}')

# 获取静态数据
static = ctx.static_info(['688300.SH'])
print('\n静态数据:')
for s in static:
    print(f'  名称: {s.name}')
    print(f'  总股本: {s.total_shares}')
    print(f'  流通股本: {s.outstanding_shares}')
    print(f'  EPS_TTM: {s.eps_ttm}')
    print(f'  每股净资产: {s.net_asset_per_share}')
    print(f'  所属行业: {s.industry}')
    print(f'  上市日期: {s.listing_date}')

# 计算PE和市值
price = float(quote[0].last_done)
shares = float(static[0].total_shares)
eps_ttm = float(static[0].eps_ttm)
market_cap = price * shares / 1e8
pe = price / eps_ttm if eps_ttm > 0 else None

print(f'\n计算结果:')
print(f'  当前股价: {price}元')
print(f'  总股本: {shares/1e8:.4f}亿股')
print(f'  市值: {market_cap:.2f}亿元')
print(f'  EPS_TTM: {eps_ttm}')
if pe:
    print(f'  PE_TTM: {pe:.2f}x')
else:
    print('  PE_TTM: N/A')
