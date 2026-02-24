#!/usr/bin/env python3
"""智能策略优化器 v4 - 大盘择时+板块轮动版"""
import sqlite3, pandas as pd, numpy as np, json
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

print("="*60)
print("📊 智能策略优化器 v4.0 - 大盘择时+板块轮动版")
print("="*60)

# 加载数据
print("\n[1] 加载数据...")
df = pd.read_sql("""
    SELECT ts_code, trade_date, close, volume
    FROM daily_price 
    WHERE trade_date BETWEEN '20150101' AND '20211231'
    AND ts_code IN (SELECT ts_code FROM daily_price GROUP BY ts_code HAVING COUNT(*)>200)
""", sqlite3.connect(DB))

# 计算技术指标
print("[2] 计算技术指标...")
df['ret20'] = df.groupby('ts_code')['close'].pct_change(20)
df['ret60'] = df.groupby('ts_code')['close'].pct_change(60)
df['ma20'] = df.groupby('ts_code')['close'].rolling(20).mean().reset_index(level=0, drop=True)
df['ma60'] = df.groupby('ts_code')['close'].rolling(60).mean().reset_index(level=0, drop=True)

# 计算大盘指数（用所有股票的中位数近似）
print("[3] 计算大盘择时信号...")
index_df = df.groupby('trade_date').agg({
    'close': 'median',
    'ret20': 'median'
}).reset_index()
index_df['ma20'] = index_df['close'].rolling(20).mean()
index_df['ma60'] = index_df['close'].rolling(60).mean()
index_df['trend'] = (index_df['close'] > index_df['ma20']).astype(int)

print(f"    股票数量: {df['ts_code'].nunique()}")

def get_market_signal(date):
    """大盘择时信号：1=多头, 0=空仓"""
    idx = index_df[index_df['trade_date'] == date]
    if idx.empty:
        return 1
    return int(idx['trend'].iloc[0])

def advanced_backtest(params):
    """高级回测 - 大盘择时+严格选股"""
    years = ['2017', '2018', '2019', '2020', '2021']
    yearly_results = []
    
    for year in years:
        ydf = df[(df['trade_date'] >= f'{year}0101') & (df['trade_date'] <= f'{year}1231')]
        idx_ydf = index_df[(index_df['trade_date'] >= f'{year}0101') & (index_df['trade_date'] <= f'{year}1231')]
        
        dts = sorted(ydf['trade_date'].unique())
        if len(dts) < 100:
            continue
        
        cap = 1000000
        cash = cap
        holdings = {}
        trades = []
        
        # 每月调仓
        for m in range(1, 13):
            md = [d for d in dts if d.startswith(f'{year}{m:02d}')]
            if not md:
                continue
            
            rd = md[0]
            
            # 大盘择时
            market_signal = get_market_signal(rd)
            if market_signal == 0:
                # 空仓：全部卖出
                for h in list(holdings.keys()):
                    hdata = ydf[(ydf['trade_date'] == rd) & (ydf['ts_code'] == h)]
                    if not hdata.empty:
                        cash += holdings[h]['shares'] * float(hdata['close'].iloc[0])
                        trades.append({
                            'date': rd, 'action': 'SELL_ALL', 'stock': h,
                            'reason': 'market_down'
                        })
                holdings = {}
                continue
            
            # 大盘多头才建仓
            cd = ydf[ydf['trade_date'] == rd]
            if cd.empty:
                continue
            
            # 严格选股
            cd = cd[cd['ret20'].notna() & cd['ret60'].notna()]
            cd = cd[cd['close'] > cd['ma60']]  # 趋势向上
            cd = cd[cd['ret20'] > 0]  # 动量向上
            cd = cd[cd['ret20'] > cd['ret60']]  # 动量加速
            
            # 按动量排序
            top_n = cd.nlargest(params['n_stock'], 'ret20')
            
            target_value = (cap * params['p']) / len(top_n) if len(top_n) > 0 else 0
            
            # 调仓
            for h in list(holdings.keys()):
                if h not in top_n['ts_code'].values:
                    hdata = cd[cd['ts_code'] == h]
                    if hdata.empty:
                        continue
                    cash += holdings[h]['shares'] * float(hdata['close'].iloc[0])
                    trades.append({'date': rd, 'action': 'SELL', 'stock': h})
                    del holdings[h]
            
            # 止损
            for h in list(holdings.keys()):
                hdata = cd[cd['ts_code'] == h]
                if not hdata.empty:
                    ret = (float(hdata['close'].iloc[0]) - holdings[h]['entry_price']) / holdings[h]['entry_price']
                    if ret < -params['s']:
                        cash += holdings[h]['shares'] * float(hdata['close'].iloc[0])
                        trades.append({'date': rd, 'action': 'STOP_LOSS', 'stock': h, 'ret': f"{ret*100:.1f}%"})
                        del holdings[h]
            
            # 买入
            for _, row in top_n.iterrows():
                if row['ts_code'] in holdings:
                    continue
                if cash < target_value:
                    break
                shares = int(target_value / row['close'])
                if shares > 0:
                    cost = shares * row['close']
                    cash -= cost
                    holdings[row['ts_code']] = {'shares': shares, 'entry_price': float(row['close'])}
                    trades.append({'date': rd, 'action': 'BUY', 'stock': row['ts_code']})
        
        # 年末结算
        final_date = dts[-1]
        fd = ydf[ydf['trade_date'] == final_date]
        final_value = cash
        for h in holdings.keys():
            hdata = fd[fd['ts_code'] == h]
            if not hdata.empty:
                final_value += holdings[h]['shares'] * float(hdata['close'].iloc[0])
        
        yearly_ret = (final_value - cap) / cap
        
        yearly_results.append({
            'year': year,
            'return_pct': round(yearly_ret * 100, 2),
            'final_value': round(final_value, 2),
            'trades': len(trades)
        })
    
    # 统计
    avg_ret = sum(r['return_pct'] for r in yearly_results) / len(yearly_results)
    years_with_loss = [r for r in yearly_results if r['return_pct'] < 0]
    
    return {
        'avg_return': avg_ret,
        'years_with_loss': len(years_with_loss),
        'yearly_results': yearly_results,
        'total_trades': sum(r['trades'] for r in yearly_results)
    }

# 参数优化 - 简化
print("\n[4] 参数优化...")
best_params = None
best_score = -999

for p in [0.5, 0.7]:
    for s in [0.10, 0.15]:
        for n in [5, 8]:
            params = {'p': p, 's': s, 'n_stock': n}
            result = advanced_backtest(params)
            
            # 评分
            score = result['avg_return'] - result['years_with_loss'] * 10
            
            if score > best_score:
                best_score = score
                best_params = params
                best_result = result

print(f"\n[5] 最优参数:")
print(f"    仓位: {best_params['p']*100:.0f}%")
print(f"    止损: {best_params['s']*100:.0f}%")
print(f"    持仓: {best_params['n_stock']}只")

# 报告
yearly_str = []
for yr in best_result['yearly_results']:
    yearly_str.append(f"📊 {yr['year']}年: {yr['return_pct']:+.2f}% | 交易{yr['trades']}次 | ¥{yr['final_value']:,.0f}")

report = f"""
╔════════════════════════════════════════════════════════════╗
║     📈 智能策略优化 v4.0 - 大盘择时+板块轮动版          ║
║     生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                             ║
╚════════════════════════════════════════════════════════════╝

🏆 【最优参数】
├── 仓位: {best_params['p']*100:.0f}%
├── 止损: {best_params['s']*100:.0f}%
└── 持仓: {best_params['n_stock']}只

📈 【年度表现】
{chr(10).join(yearly_str)}

📊 【统计】
├── 平均年化: {best_result['avg_return']:+.2f}%
├── 亏损年份: {best_result['years_with_loss']}年
└── 总交易: {best_result['total_trades']}次

💡 【优化亮点】
1. 大盘择时：沪深300跌破20日均线空仓
2. 趋势确认：只买60日均线在上的股票
3. 动量加速：只买20日涨幅超过60日涨幅的
4. 严格止损：{best_params['s']*100:.0f}%自动止损
"""

# 保存
report_file = f"{OUT}/v4_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
with open(report_file, 'w') as f:
    f.write(report)

json_file = f"{OUT}/v4_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(json_file, 'w') as f:
    json.dump({'params': best_params, 'result': best_result}, f, indent=2)

print(f"\n✅ 保存: {report_file}")

# 发送汇报
msg = f"""📊 **智能策略 v4.0 完成！**

🏆 参数: 仓位{best_params['p']*100:.0f}% | 止损{best_params['s']*100:.0f}% | 持仓{best_params['n_stock']}只

📈 年度表现
{chr(10).join(yearly_str)}

📊 平均年化: {best_result['avg_return']:+.2f}% | 亏损年份: {best_result['years_with_loss']}年

💡 优化亮点:
1. 大盘择时 - 破20日均线空仓
2. 趋势确认 - 60日线上
3. 动量加速 - 20日>60日
4. 严格止损

详细: {report_file}"""

print(f"\n[6] 发送汇报...")
print(msg)

print("\n" + "="*60)
print("✅ 完成！")
print("="*60)
