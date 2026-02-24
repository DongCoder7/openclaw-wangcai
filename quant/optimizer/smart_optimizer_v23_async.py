#!/usr/bin/env python3
"""v23 - 增强版多因子 (异步汇报版)
每轮迭代都写入报告文件"""
import sqlite3, pandas as pd
import numpy as np
from datetime import datetime
import os

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'
REPORT_FILE = f'{OUT}/latest_report.txt'
ITERATION_FILE = f'{OUT}/iteration_log.txt'

def write_report(content, iteration=None):
    """写入报告文件"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 主报告文件 - 始终是最新结果
    with open(REPORT_FILE, 'w') as f:
        f.write(f"📊 **v23 优化汇报** ({ts})")
        if iteration:
            f.write(f" - 第{iteration}轮迭代")
        f.write(f"\n\n{content}\n")
    
    # 迭代日志 - 追加所有结果
    with open(ITERATION_FILE, 'a') as f:
        f.write(f"\n[{ts}] ")
        if iteration:
            f.write(f"迭代{iteration}: ")
        f.write(f"{content}\n")

def main():
    print("="*60)
    print("v23 增强版多因子 (异步汇报)")
    print("="*60)
    
    # 清空迭代日志
    with open(ITERATION_FILE, 'w') as f:
        f.write(f"=== v23 优化迭代日志 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    conn = sqlite3.connect(DB)
    df = pd.read_sql("""
        SELECT e.ts_code, e.trade_date, e.close, e.volume, e.amount,
               f.ret_20, f.ret_60, f.ret_120, f.vol_20, f.vol_ratio, f.ma_20, f.ma_60,
               f.money_flow, f.rel_strength, f.mom_accel, f.price_pos_20, f.price_pos_60
        FROM stock_efinance e
        LEFT JOIN stock_factors f ON e.ts_code = f.ts_code AND e.trade_date = f.trade_date
        WHERE e.trade_date BETWEEN '20180101' AND '20211231'
        AND e.ts_code IN (SELECT DISTINCT ts_code FROM stock_efinance GROUP BY ts_code HAVING COUNT(*) > 900)
    """, conn)
    
    conn.close()
    df = df[df['ret_20'].notna()]
    
    print(f"股票数: {df['ts_code'].nunique()}")
    
    # 增强因子
    df['mom_20_60'] = df['ret_20'] - df['ret_60']
    df['price_strength'] = df['price_pos_20'] * df['ret_20']
    df['fund_quality'] = df['money_flow'] * df['rel_strength']
    
    # 综合评分
    df['score'] = (
        df['ret_20'].rank(pct=True) * 0.20 +
        df['ret_60'].rank(pct=True) * 0.15 +
        df['mom_accel'].rank(pct=True) * 0.15 +
        (1 - df['vol_20'].rank(pct=True)) * 0.15 +
        df['money_flow'].rank(pct=True) * 0.15 +
        df['price_pos_20'].rank(pct=True) * 0.20
    )
    
    # 择时
    idx = df.groupby('trade_date')['close'].median().reset_index()
    idx['ma20'] = idx['close'].rolling(20).mean()
    idx['ma60'] = idx['close'].rolling(60).mean()
    idx['trend'] = (idx['close'] > idx['ma20']).astype(int)
    idx_dict = dict(zip(idx['trade_date'], idx['trend']))
    
    def bt(p, s, n, rebal=15):
        res = []
        for y in ['2018','2019','2020','2021']:
            yd = df[(df['trade_date'] >= f'{y}0101') & (df['trade_date'] <= f'{y}1231')]
            dates = sorted(yd['trade_date'].unique())
            if len(dates) < 20: continue
            
            init = 1000000.0
            cash = init
            h = {}
            
            for rd in dates[::rebal]:
                rd_d = yd[yd['trade_date']==rd]
                
                hv = sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) 
                        for c in h if not rd_d[rd_d['ts_code']==c].empty)
                tot = cash + hv
                
                if idx_dict.get(rd, 1) == 0:
                    for c in list(h.keys()):
                        cd = rd_d[rd_d['ts_code']==c]
                        if not cd.empty:
                            cash += h[c]['s'] * float(cd['close'].iloc[0])
                    h = {}
                    continue
                
                cand = rd_d[rd_d['score'].notna()].nlargest(n, 'score')
                if cand.empty: continue
                
                tgt = tot * p / len(cand)
                
                for c in list(h.keys()):
                    if c not in cand['ts_code'].values:
                        cd = rd_d[rd_d['ts_code']==c]
                        if not cd.empty:
                            cash += h[c]['s'] * float(cd['close'].iloc[0])
                            del h[c]
                
                for _, r in cand.iterrows():
                    if r['ts_code'] not in h:
                        sh = int(tgt / r['close'])
                        if sh > 0:
                            h[r['ts_code']] = {'s': sh, 'p': r['close']}
                            cash -= sh * r['close']
                
                for c in list(h.keys()):
                    cd = rd_d[rd_d['ts_code']==c]
                    if not cd.empty:
                        ret = (float(cd['close'].iloc[0]) - h[c]['p']) / h[c]['p']
                        if ret < -s:
                            cash += h[c]['s'] * float(cd['close'].iloc[0])
                            del h[c]
                        elif ret > 0.15:
                            cash += h[c]['s'] * float(cd['close'].iloc[0])
                            del h[c]
            
            rd = dates[-1]
            rd_d = yd[yd['trade_date']==rd]
            fv = cash + sum(h[c]['s'] * float(rd_d[rd_d['ts_code']==c]['close'].iloc[0]) 
                           for c in h if not rd_d[rd_d['ts_code']==c].empty)
            res.append({'year': y, 'return': (fv - init) / init})
        
        return res
    
    print("\n[回测...]")
    best, best_r, best_avg = None, None, -999
    iteration = 0
    total_iterations = len([0.3, 0.5, 0.7, 1.0]) * len([0.05, 0.08, 0.10, 0.15]) * len([3, 5, 8, 10]) * len([10, 15, 20])
    
    for p in [0.3, 0.5, 0.7, 1.0]:
        for s in [0.05, 0.08, 0.10, 0.15]:
            for n in [3, 5, 8, 10]:
                for rebal in [10, 15, 20]:
                    iteration += 1
                    r = bt(p, s, n, rebal)
                    if not r: continue
                    avg = np.mean([x['return'] for x in r])
                    loss = sum(1 for x in r if x['return'] < 0)
                    score = avg - loss * 0.1
                    
                    yearly_str = " | ".join([f"{d['year']}: {d['return']*100:+.1f}%" for d in r])
                    
                    if score > best_avg:
                        best_avg = score
                        best = {'p':p,'s':s,'n':n,'rebal':rebal}
                        best_r = r
                        
                        # 写入报告 - 发现更优解时
                        report_content = f"""🏆 发现更优参数组合 ({iteration}/{total_iterations})

参数: 仓位{best['p']*100:.0f}% | 止损{best['s']*100:.0f}% | 持仓{best['n']}只 | 调仓{best['rebal']}天

年度收益:
📈 {yearly_str}

平均收益: {avg*100:+.1f}%
亏损年份: {loss}年
综合评分: {score:.3f}"""
                        
                        write_report(report_content, iteration)
                        print(f"\n  📝 第{iteration}轮: 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% = {avg*100:+.1f}%")
    
    if best_r:
        yearly = [f"{d['year']}: {d['return']*100:+.1f}%" for d in best_r]
        avg = np.mean([d['return'] for d in best_r]) * 100
        
        print(f"\n🏆 最终最优: 仓位{best['p']*100:.0f}% 止损{best['s']*100:.0f}% 持仓{best['n']}只 调仓{best['rebal']}天")
        print("📈 " + " | ".join(yearly))
        print(f"📊 平均: {avg:+.1f}%")
        
        # 最终报告
        final_report = f"""✅ 优化完成

🏆 最优参数:
• 仓位: {best['p']*100:.0f}%
• 止损: {best['s']*100:.0f}%
• 持仓: {best['n']}只
• 调仓周期: {best['rebal']}天

📈 年度表现:
{chr(10).join(yearly)}

📊 平均年化收益: {avg:+.1f}%
⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        write_report(final_report, "最终")
        print("\n✅ 完成")

if __name__ == "__main__":
    main()
