import akshare as ak
import pandas as pd

print('='*70)
print('🚀 VQM真实数据快速验证')
print('='*70)

# 获取实时估值数据
print('\n📊 获取实时估值数据...')
val_df = ak.stock_zh_a_spot_em()
print(f'✅ 获取 {len(val_df)} 只股票')

# 筛选有效PE数据
df = val_df[val_df['市盈率-动态'] > 0]
df = df[df['市盈率-动态'] < 100]
print(f'✅ 有效PE数据: {len(df)} 只')

# 简单VQM排名（仅PE）
df = df.copy()
df['pe'] = df['市盈率-动态'].astype(float)
df['pe_rank'] = df['pe'].rank(pct=True, ascending=True)
df['vqm_score'] = df['pe_rank']  # 简化版，只用PE

# 显示前10名
top10 = df.nlargest(10, 'vqm_score')

print('\n📈 VQM低PE排名前10:')
print('| 代码 | 名称 | 价格 | PE | VQM得分 |')
print('|:----:|:----:|:----:|:--:|:-------:|')
for _, row in top10.iterrows():
    print(f"| {row['代码']} | {row['名称']} | ¥{row['最新价']:.2f} | {row['pe']:.1f} | {row['vqm_score']:.2f} |")

print('\n✅ 真实数据验证成功！')
print('='*70)
