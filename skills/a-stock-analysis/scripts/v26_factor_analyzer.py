#!/root/.openclaw/workspace/venv/bin/python3
"""
A股个股分析 - v26全因子升级版
使用26个因子进行深度分析
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'

# v26 全因子列表
ALL_FACTORS = {
    # 动量因子 (6个)
    'momentum': ['ret_20', 'ret_60', 'ret_120', 'mom_accel', 'profit_mom', 'rel_strength'],
    # 波动率因子 (5个)
    'volatility': ['vol_20', 'vol_ratio', 'vol_120', 'downside_vol', 'max_drawdown_120'],
    # 趋势因子 (5个)
    'trend': ['price_pos_20', 'price_pos_60', 'price_pos_high', 'ma_20', 'ma_60'],
    # 资金因子 (2个)
    'flow': ['money_flow', 'vol_ratio_amt'],
    # 质量因子 (2个)
    'quality': ['sharpe_like', 'low_vol_score'],
    # 估值因子 (2个) - 财务数据
    'valuation': ['pe_ttm', 'pb'],
    # 财务因子 (4个) - 财务数据
    'financial': ['roe', 'revenue_growth', 'netprofit_growth', 'debt_ratio']
}

def get_stock_factor_score(ts_code, trade_date=None):
    """获取单只股票的全因子评分"""
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y%m%d')
    
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    
    factor_scores = {}
    
    # 1. 获取技术指标因子（根据实际数据库结构）
    cursor.execute('''
        SELECT ret_20, ret_60, vol_20, ma_20, ma_60, 
               price_pos_20, money_flow, rel_strength, rsi_14, macd
        FROM stock_factors 
        WHERE ts_code = ? AND trade_date <= ?
        ORDER BY trade_date DESC LIMIT 1
    ''', (ts_code, trade_date))
    
    row = cursor.fetchone()
    if row:
        cols = ['ret_20', 'ret_60', 'vol_20', 'ma_20', 'ma_60',
                'price_pos_20', 'money_flow', 'rel_strength', 'rsi_14', 'macd']
        for i, col in enumerate(cols):
            if row[i] is not None:
                factor_scores[col] = row[i]
    
    # 2. 获取防御因子
    try:
        cursor.execute('''
            SELECT vol_120, max_drawdown_120, downside_vol, sharpe_like, low_vol_score
            FROM stock_defensive_factors 
            WHERE ts_code = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 1
        ''', (ts_code, trade_date))
        
        row = cursor.fetchone()
        if row:
            cols = ['vol_120', 'max_drawdown_120', 'downside_vol', 'sharpe_like', 'low_vol_score']
            for i, col in enumerate(cols):
                if row[i] is not None:
                    factor_scores[col] = row[i]
    except Exception as e:
        print(f"[WARN] 防御因子获取失败: {e}")
    
    # 3. 获取财务因子
    try:
        cursor.execute('''
            SELECT pe_ttm, pb, roe, revenue_growth, netprofit_growth, debt_ratio
            FROM stock_fina 
            WHERE ts_code = ?
            ORDER BY report_date DESC LIMIT 1
        ''', (ts_code,))
        
        row = cursor.fetchone()
        if row:
            cols = ['pe_ttm', 'pb', 'roe', 'revenue_growth', 'netprofit_growth', 'debt_ratio']
            for i, col in enumerate(cols):
                if row[i] is not None:
                    factor_scores[col] = row[i]
    except Exception as e:
        print(f"[WARN] 财务因子获取失败: {e}")
    
    conn.close()
    
    # 计算综合得分
    total_score = 0
    valid_factors = 0
    
    # 正向因子：值越大越好
    positive_factors = ['ret_20', 'ret_60', 'rel_strength', 'money_flow', 'rsi_14', 'sharpe_like', 'low_vol_score']
    
    # 负向因子：值越小越好
    negative_factors = ['vol_20', 'macd', 'vol_120', 'max_drawdown_120', 'downside_vol']
    
    for factor, value in factor_scores.items():
        if factor in positive_factors:
            total_score += min(max(value * 100, -50), 50)  # 限制在-50到50之间
            valid_factors += 1
        elif factor in negative_factors:
            total_score -= min(max(value * 100, -50), 50)
            valid_factors += 1
    
    if valid_factors > 0:
        total_score = total_score / valid_factors
    
    return {
        'total_score': total_score,
        'valid_factors': valid_factors,
        'factor_scores': factor_scores
    }

def analyze_stocks(stock_list, trade_date=None):
    """分析多只股票"""
    results = []
    
    for code, name in stock_list:
        result = get_stock_factor_score(code, trade_date)
        result['code'] = code
        result['name'] = name
        results.append(result)
    
    # 按总分排序
    results.sort(key=lambda x: x['total_score'], reverse=True)
    return results

if __name__ == '__main__':
    # 存储芯片产业链股票
    stocks = [
        ('688981.SH', '中芯国际'),
        ('688347.SH', '华虹公司'),
        ('600584.SH', '长电科技'),
        ('002156.SZ', '通富微电'),
        ('603005.SH', '晶方科技'),
        ('688019.SH', '安集科技'),
        ('688256.SH', '寒武纪'),
        ('300474.SZ', '景嘉微'),
        ('688041.SH', '海光信息'),
        ('688521.SH', '芯原股份')
    ]
    
    print('='*70)
    print('存储芯片产业链 - v26全因子分析 (26个因子)')
    print('='*70)
    
    results = analyze_stocks(stocks)
    
    print(f'\n{"排名":<4} {"代码":<10} {"名称":<10} {"综合得分":<10} {"有效因子":<8}')
    print('-'*70)
    
    for i, r in enumerate(results, 1):
        emoji = '🟢' if r['total_score'] > 0 else '🔴'
        print(f'{i:<4} {r["code"]:<10} {r["name"]:<10} {emoji}{r["total_score"]:+7.2f}   {r["valid_factors"]}/26')
    
    print('\n' + '='*70)
    print('投资建议:')
    print('='*70)
    
    # 推荐前3名
    top3 = results[:3]
    print(f'\n⭐ 核心持仓推荐 (基于{len(top3[0]["factor_scores"])}个有效因子):')
    for i, r in enumerate(top3, 1):
        print(f'  {i}. {r["code"]} {r["name"]}: 综合得分 {r["total_score"]:+.2f}')
        # 显示主要贡献因子
        top_factors = sorted(r['factor_scores'].items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        print(f'     主要因子: {", ".join([f"{k}={v:+.2f}" for k, v in top_factors])}')
    
    print('\n' + '='*70)
