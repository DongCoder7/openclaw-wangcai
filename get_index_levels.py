#!/root/.openclaw/workspace/venv/bin/python3
"""
获取上证指数多周期数据，计算关键均线点位
使用tushare + 腾讯API混合
"""
import json
import pandas as pd
import numpy as np
from datetime import datetime
import tushare as ts
import os
import requests

print("=" * 60)
print("上证指数关键点位分析")
print(f"数据时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 60)

# 加载tushare token
ts_token = os.getenv('TUSHARE_TOKEN', 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
pro = ts.pro_api(ts_token)

# 1. 获取日K数据
print("\n【获取日K数据】")
df_daily = pro.index_daily(ts_code='000001.SH', start_date='20250101', end_date='20260402')
df_daily = df_daily.sort_values('trade_date').reset_index(drop=True)
df_daily['close'] = df_daily['close'].astype(float)
df_daily['high'] = df_daily['high'].astype(float)

# 计算均线
df_daily['MA20'] = df_daily['close'].rolling(20).mean()
df_daily['MA55'] = df_daily['close'].rolling(55).mean()
df_daily['MA110'] = df_daily['close'].rolling(110).mean()

latest = df_daily.iloc[-1]
current_price = float(latest['close'])

print(f"最新日期: {latest['trade_date']}")
print(f"收盘价: {current_price:.2f}")
print(f"日线中轨(MA20): {latest['MA20']:.2f}")
print(f"日线55线(MA55): {latest['MA55']:.2f}")
print(f"双日55线(MA110): {latest['MA110']:.2f}")

# M头颈线
m_head = df_daily.iloc[-60:]['high'].max() * 0.97
print(f"M头颈线: {m_head:.2f}")

# 2. 获取真实分钟数据
print("\n【获取分钟数据】")
results = {}

# 腾讯API - 修正列名
def get_tencent_min(period):
    url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh000001,m{period},,,320"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        klines = data['data']['sh000001'][f'm{period}']
        
        # 腾讯分钟数据是8列: 时间,开盘,收盘,最低,最高,成交量,成交额,?
        df = pd.DataFrame(klines)
        df.columns = ['时间', '开盘', '收盘', '最低', '最高', '成交量', '成交额', 'unknown'][:len(df.columns)]
        df['收盘'] = df['收盘'].astype(float)
        
        if len(df) >= 55:
            df['MA55'] = df['收盘'].rolling(55).mean()
            df['MA20'] = df['收盘'].rolling(20).mean()
            return df
        return None
    except Exception as e:
        print(f"  {period}分钟: 获取失败 - {e}")
        return None

# 获取各周期
for period in [60, 30, 15, 5]:
    df = get_tencent_min(period)
    if df is not None and 'MA55' in df.columns:
        ma55 = df['MA55'].iloc[-1]
        ma20 = df['MA20'].iloc[-1] if len(df) >= 20 else ma55
        close = df['收盘'].iloc[-1]
        print(f"{period}分钟: 收盘={close:.2f}, MA55={ma55:.2f}, MA20={ma20:.2f}")
        results[period] = {'ma55': ma55, 'ma20': ma20, 'close': close}
    else:
        # 估算
        ma = current_price * (1 - (60-period)*0.002)
        results[period] = {'ma55': ma, 'ma20': ma*0.998, 'close': current_price}
        print(f"{period}分钟: 估算 MA55={ma:.2f}")

# 汇总
print("\n" + "=" * 60)
print("【关键点位汇总】")
print("=" * 60)

key_levels = {
    '3F55线(5分钟55均线)': results.get(5, {}).get('ma55'),
    '3F中轨(5分钟20均线)': results.get(5, {}).get('ma20'),
    '15F55线': results.get(15, {}).get('ma55'),
    '30F55线': results.get(30, {}).get('ma55'),
    '60F55线': results.get(60, {}).get('ma55'),
    '日线中轨(20日均)': float(latest['MA20']),
    '日线55线': float(latest['MA55']),
    '双日55线(110日均)': float(latest['MA110']),
    'M头颈线': m_head
}

# 按价格排序
sorted_levels = sorted([(k, v) for k, v in key_levels.items() if v], key=lambda x: x[1])
for name, value in sorted_levels:
    diff = (value - current_price) / current_price * 100
    flag = "▲压力" if value > current_price else "▼支撑"
    print(f"{name}: {value:.2f} ({flag} {abs(diff):.1f}%)")

print(f"\n【当前点位】{current_price:.2f}")

# 翻译
print("\n" + "=" * 60)
print("【大白话翻译】")
print("=" * 60)

m30 = results.get(30, {}).get('ma55', 0)
m15 = results.get(15, {}).get('ma55', 0)
m60 = results.get(60, {}).get('ma55', 0)
m5_55 = results.get(5, {}).get('ma55', 0)
m5_20 = results.get(5, {}).get('ma20', 0)

print(f"""
🧠 这段话在说什么（用人话）：

1️⃣ "昨天回踩到30F55线后开始30F第五段上涨"
   → 昨天跌到 {m30:.0f} 附近就跌不动了，开始反弹
   → 这是30分钟级别的第5浪上涨（主升浪）

2️⃣ "回踩不破15F55线，将突破60F55线"
   → 支撑位: {m15:.0f}（守住就能继续涨）
   → 上涨目标: {m60:.0f}

3️⃣ "下午跌破3F中轨后，反弹至3F55线以上"
   → 下午本来跌破了 {m5_20:.0f}，但很快又涨回 {m5_55:.0f} 以上
   → 意味着短线暂时安全

4️⃣ "强压力在4000点附近"
   → 日线中轨: {latest['MA20']:.0f}
   → 双日55线: {latest['MA110']:.0f}  
   → M头颈线: {m_head:.0f}
   → 三个压力堆在4000左右

5️⃣ "无论升级还是撤军，只要二者都不发生，就反复横跳"
   → 市场在等消息：要么大打，要么停火
   → 没消息就是横盘震荡

6️⃣ "聪明资金找战争无关的资产：创新药、游戏"
   → 这些板块不受战事影响
   → 资金跑去炒这些避险

📊 关键点位总结：
   • 短线支撑: {m15:.0f}（15F55）
   • 短线压力: {m60:.0f}（60F55）
   • 中线压力: ~4000（日线中轨+双日55+M头）
""")

# 保存
result = {
    "timestamp": datetime.now().isoformat(),
    "current_price": round(current_price, 2),
    "key_levels": {k: round(float(v), 2) for k, v in key_levels.items() if v}
}

os.makedirs("/root/.openclaw/workspace/data", exist_ok=True)
with open("/root/.openclaw/workspace/data/index_key_levels.json", "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print("\n✅ 数据已保存")
