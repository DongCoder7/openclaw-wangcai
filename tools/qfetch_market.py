#!/root/.openclaw/workspace/venv/bin/python3
import efinance as ef
import datetime

indices = {'沪深300': '000300', '上证指数': '000001', '创业板': '399006', '科创50': '000688'}
print('=== A股指数 ===')
for name, code in indices.items():
    try:
        df = ef.stock.get_quote_history(code, beg=str(datetime.date.today()))
        if len(df) > 0:
            last = df.iloc[-1]
            chg = last.get('涨跌幅', 0)
            print(f'{name}: {last["最新价"]:.2f} ({chg:+.2f}%)')
        else:
            print(f'{name}: 无数据')
    except Exception as e:
        print(f'{name}: {e}')

print('\n=== 港股标的 ===')
hk = {'腾讯': '00700', '阿里': '09988', '美团': '03690', '小米': '01810', '中海油': '00883', '平安': '02318', '神华': '01088', '中石油': '00857', '友邦': '01299', '中烟': '01898'}
for name, code in hk.items():
    try:
        df = ef.stock.get_quote_history(code, beg=str(datetime.date.today()))
        if len(df) > 0:
            last = df.iloc[-1]
            chg = last.get('涨跌幅', 0)
            print(f'{name}({code}): {last["最新价"]:.2f} ({chg:+.2f}%)')
        else:
            print(f'{name}: 无数据')
    except Exception as e:
        print(f'{name}: {e}')

print('\n=== 热门板块 ===')
try:
    sectors = ef.stock.get_sector_list()
    if sectors is not None and len(sectors) > 0:
        for _, row in sectors.head(15).iterrows():
            nm = row.get('板块名称', '?')
            chg = row.get('涨跌幅', 0)
            print(f'{nm}: {chg:+.2f}%')
    else:
        print('无数据')
except Exception as e:
    print(f'获取失败: {e}')