#!/root/.openclaw/workspace/venv/bin/python3
"""用efinance获取A股行情"""
import efinance as ef
from datetime import datetime

# 获取今日行情
print("正在获取A股全市场数据...")
df = ef.stock.get_realtime_quotes()
print(f"获取到 {len(df)} 只股票")
print(df.columns.tolist())
print(df.head(3).to_string())

# 清洗数据 - 将'-'转为NaN
df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
df = df.dropna(subset=['涨跌幅'])

total = len(df)
up = len(df[df['涨跌幅'] > 0])
down = len(df[df['涨跌幅'] < 0])
flat = len(df[df['涨跌幅'] == 0])
avg_change = df['涨跌幅'].mean()
limit_up = len(df[df['涨跌幅'] >= 9.5])
limit_down = len(df[df['涨跌幅'] <= -9.5])
total_amount = df['成交额'].sum() / 100000000  # 亿

print(f"\n=== 市场统计 ===")
print(f"总股票数: {total}")
print(f"上涨: {up} | 下跌: {down} | 平盘: {flat}")
print(f"平均涨跌幅: {avg_change:+.2f}%")
print(f"涨停: {limit_up} | 跌停: {limit_down}")
print(f"成交额: {total_amount:.0f}亿")

# 板块分类
def classify(code):
    c = str(code)
    if c.startswith('688'):
        return '科创板'
    elif c.startswith('3'):
        return '创业板'
    elif c.startswith('8') or c.startswith('4'):
        return '北交所'
    else:
        return '主板'

df['板块'] = df['股票代码'].apply(classify)
sector_perf = df.groupby('板块')['涨跌幅'].mean().sort_values(ascending=False)
print(f"\n=== 板块等权平均 ===")
for sector, change in sector_perf.items():
    count = len(df[df['板块'] == sector])
    print(f"{sector}: {change:+.2f}% ({count}只)")

# 涨跌幅榜
print(f"\n=== 涨幅TOP10 ===")
top_up = df.nlargest(10, '涨跌幅')[['股票代码', '股票名称', '涨跌幅', '板块']]
for _, row in top_up.iterrows():
    print(f"{row['股票代码']} {row['股票名称']}: {row['涨跌幅']:+.2f}% [{row['板块']}]")

print(f"\n=== 跌幅TOP10 ===")
top_down = df.nsmallest(10, '涨跌幅')[['股票代码', '股票名称', '涨跌幅', '板块']]
for _, row in top_down.iterrows():
    print(f"{row['股票代码']} {row['股票名称']}: {row['涨跌幅']:+.2f}% [{row['板块']}]")

# 保存数据
import json
result = {
    'total': total, 'up': up, 'down': down, 'flat': flat,
    'avg_change': avg_change,
    'limit_up': limit_up, 'limit_down': limit_down,
    'sector_perf': {k: round(v, 2) for k, v in sector_perf.items()},
    'top_up': top_up.to_dict('records'),
    'top_down': top_down.to_dict('records')
}
with open('/root/.openclaw/workspace/data/ef_market_20260522.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("\n数据已保存")
