#!/root/.openclaw/workspace/venv/bin/python3
from longport.openapi import Config, QuoteContext

config = Config.from_env()
ctx = QuoteContext(config)

q = ctx.quote(['00700.HK'])
static = ctx.static_info(['00700.HK'])
name = static[0].name_cn or static[0].name_en
change_rate = (q[0].last_done - q[0].prev_close) / q[0].prev_close * 100 if q[0].prev_close > 0 else 0
print("HK:", name, q[0].last_done, q[0].prev_close, change_rate)

q2 = ctx.quote(['000001.SZ'])
static2 = ctx.static_info(['000001.SZ'])
name2 = static2[0].name_cn or static2[0].name_en
change_rate2 = (q2[0].last_done - q2[0].prev_close) / q2[0].prev_close * 100 if q2[0].prev_close > 0 else 0
print("A:", name2, q2[0].last_done, q2[0].prev_close, change_rate2)
