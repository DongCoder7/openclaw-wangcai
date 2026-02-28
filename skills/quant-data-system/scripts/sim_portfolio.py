#!/usr/bin/env python3
"""
模拟盘交易系统
基于WFO最优参数生成每日持仓建议
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
REPORTS_PATH = f'{WORKSPACE}/skills/quant-data-system/reports'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_latest_wfo_result():
    """加载最新的WFO结果"""
    try:
        # 查找最新的WFO报告
        wfo_files = [f for f in os.listdir(REPORTS_PATH) 
                     if f.startswith('wfo_backtest_') and f.endswith('.json')]
        
        if not wfo_files:
            log("⚠️ 未找到WFO报告")
            return None
        
        wfo_files.sort(reverse=True)
        latest_file = f"{REPORTS_PATH}/{wfo_files[0]}"
        
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        # 使用最后一个窗口的权重
        windows = data.get('windows', [])
        if not windows:
            return None
        
        latest_window = windows[-1]
        weights = latest_window.get('weights', [0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.10])
        
        log(f"✅ 加载WFO权重: {[f'{w:.3f}' for w in weights]}")
        return weights
        
    except Exception as e:
        log(f"⚠️ 加载WFO结果失败: {e}")
        return None

def load_today_data(trade_date=None):
    """加载今日数据"""
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y%m%d')
    
    conn = sqlite3.connect(DB_PATH)
    
    # 加载技术因子
    df = pd.read_sql(f"""
        SELECT f.ts_code, f.trade_date, f.name,
               f.ret_20, f.ret_60, f.ret_120,
               f.vol_20, f.vol_ratio, f.price_pos_20, f.price_pos_60, f.price_pos_high,
               f.money_flow, f.rel_strength, f.mom_accel, f.profit_mom,
               d.close, d.pct_chg, d.vol, d.amount
        FROM stock_factors f
        JOIN daily_price d ON f.ts_code = d.ts_code AND f.trade_date = d.trade_date
        WHERE f.trade_date = '{trade_date}'
    """, conn)
    
    conn.close()
    
    return df

def calculate_scores(df, weights):
    """计算股票打分"""
    factors = ['ret_20', 'ret_60', 'vol_20', 'price_pos_20', 
               'rel_strength', 'mom_accel', 'profit_mom']
    
    # 填充缺失值
    for f in factors:
        df[f] = df[f].fillna(0)
    
    # 标准化
    for f in factors:
        mean = df[f].mean()
        std = df[f].std()
        if std > 0:
            df[f'{f}_norm'] = (df[f] - mean) / std
        else:
            df[f'{f}_norm'] = 0
    
    # 计算综合打分
    df['score'] = 0
    for i, f in enumerate(factors):
        if i < len(weights):
            df['score'] += df[f'{f}_norm'] * weights[i]
    
    return df

def generate_portfolio(df, top_n=20):
    """生成投资组合"""
    # 过滤条件
    df = df[df['close'] > 5]  # 股价大于5元
    df = df[df['vol'] > 0]    # 有成交量
    
    # 按打分排序
    df = df.sort_values('score', ascending=False)
    
    # 选择前N只
    selected = df.head(top_n).copy()
    
    # 计算权重 (等权)
    selected['weight'] = 1.0 / len(selected)
    
    return selected

def save_portfolio(selected, trade_date=None):
    """保存持仓建议"""
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y%m%d')
    
    os.makedirs(REPORTS_PATH, exist_ok=True)
    
    portfolio = {
        'generated_at': datetime.now().isoformat(),
        'trade_date': trade_date,
        'holdings': []
    }
    
    for _, row in selected.iterrows():
        portfolio['holdings'].append({
            'ts_code': row['ts_code'],
            'name': row['name'],
            'price': row['close'],
            'weight': row['weight'],
            'score': row['score'],
            'ret_20': row['ret_20'],
            'vol_20': row['vol_20']
        })
    
    # 保存JSON
    report_file = f"{REPORTS_PATH}/sim_portfolio_{trade_date}.json"
    with open(report_file, 'w') as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)
    
    # 生成Markdown报告
    md_file = f"{REPORTS_PATH}/sim_portfolio_{trade_date}.md"
    with open(md_file, 'w') as f:
        f.write(f"# 📊 模拟盘持仓建议\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**交易日期**: {trade_date}\n\n")
        f.write(f"**持仓数量**: {len(selected)}只\n\n")
        
        f.write("## 持仓列表\n\n")
        f.write("| 排名 | 代码 | 名称 | 价格 | 权重 | 得分 | 20日收益 | 波动率 |\n")
        f.write("|------|------|------|------|------|------|----------|--------|\n")
        
        for i, (_, row) in enumerate(selected.iterrows(), 1):
            f.write(f"| {i} | {row['ts_code']} | {row['name']} | {row['close']:.2f} | "
                   f"{row['weight']*100:.1f}% | {row['score']:.3f} | "
                   f"{row['ret_20']:.2f}% | {row['vol_20']:.2f}% |\n")
        
        f.write("\n## 风险提示\n\n")
        f.write("⚠️ 本建议仅供参考，不构成投资建议。股市有风险，投资需谨慎。\n")
    
    log(f"✅ 持仓建议已保存: {report_file}")
    log(f"✅ Markdown报告: {md_file}")

def track_performance():
    """跟踪模拟盘表现"""
    # 加载历史持仓
    portfolio_files = [f for f in os.listdir(REPORTS_PATH) 
                       if f.startswith('sim_portfolio_') and f.endswith('.json')]
    
    if not portfolio_files:
        log("⚠️ 无历史持仓记录")
        return
    
    log(f"📊 跟踪 {len(portfolio_files)} 个历史持仓")
    
    # 这里可以添加收益计算逻辑
    pass

def main():
    log("="*60)
    log("🚀 模拟盘交易系统")
    log("="*60)
    
    # 1. 加载WFO最优权重
    weights = load_latest_wfo_result()
    if weights is None:
        log("❌ 无法加载WFO权重，使用默认权重")
        weights = [0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.10]
    
    # 2. 加载今日数据
    trade_date = datetime.now().strftime('%Y%m%d')
    log(f"\n📈 加载数据: {trade_date}")
    
    df = load_today_data(trade_date)
    
    if df.empty:
        log(f"⚠️ 无今日数据，尝试加载昨日数据")
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        df = load_today_data(yesterday)
        trade_date = yesterday
    
    if df.empty:
        log("❌ 无可用数据")
        return
    
    log(f"✅ 加载 {len(df)} 只股票")
    
    # 3. 计算打分
    log("\n🎯 计算股票打分...")
    df = calculate_scores(df, weights)
    
    # 4. 生成组合
    log("\n📋 生成投资组合...")
    selected = generate_portfolio(df)
    
    log(f"✅ 选中 {len(selected)} 只股票")
    
    # 5. 打印结果
    log("\n" + "="*60)
    log("📊 持仓建议")
    log("="*60)
    
    for i, (_, row) in enumerate(selected.head(10).iterrows(), 1):
        log(f"{i}. {row['name']}({row['ts_code']}) - "
              f"价格:{row['close']:.2f} 权重:{row['weight']*100:.1f}% "
              f"得分:{row['score']:.3f}")
    
    # 6. 保存结果
    log("\n💾 保存持仓建议...")
    save_portfolio(selected, trade_date)
    
    log("\n" + "="*60)
    log("✅ 模拟盘交易完成!")
    log("="*60)

if __name__ == '__main__':
    main()
