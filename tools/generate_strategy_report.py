#!/root/.openclaw/workspace/venv/bin/python3
"""
策略结果报告生成器 - 生成简洁的策略效果报告
供heartbeat整点汇报使用
"""
import sqlite3
import json
import os
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OPT = '/root/.openclaw/workspace/quant/optimizer'

def get_latest_strategy():
    """获取最新策略结果"""
    
    # 首先查找v26结果
    v26_files = [f for f in os.listdir(OPT) if f.startswith('v26_result_') and f.endswith('.json')]
    if v26_files:
        v26_files.sort(reverse=True)
        with open(f'{OPT}/{v26_files[0]}', 'r') as f:
            data = json.load(f)
        # 使用factor_count字段，如果不存在则使用factors_used长度
        factor_count = data.get('factor_count', len(data.get('factors_used', [])))
        return {
            'version': 'v26',
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': [{'factor': f} for f in data.get('factors_used', [])][:3],
            'factor_weights': {f: 1.0 for f in data.get('factors_used', [])},
            'timestamp': data.get('timestamp', ''),
            'factor_count': factor_count
        }
    
    # 然后查找增强优化器结果
    enhanced_files = []
    for f in os.listdir(OPT):
        if f.startswith('enhanced_optimizer_v') and f.endswith('.json'):
            enhanced_files.append(f)
    
    if enhanced_files:
        enhanced_files.sort(reverse=True)
        with open(f'{OPT}/{enhanced_files[0]}', 'r') as f:
            data = json.load(f)
        version = enhanced_files[0].split('_')[2]
        return {
            'version': version,
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': data.get('top_factors', [])[:3],
            'factor_weights': data.get('factor_weights', {}),
            'timestamp': data.get('timestamp', '')
        }
    
    # 查找v25结果
    v25_files = [f for f in os.listdir(OPT) if f.startswith('v25_result_') and f.endswith('.json')]
    if v25_files:
        v25_files.sort(reverse=True)
        with open(f'{OPT}/{v25_files[0]}', 'r') as f:
            data = json.load(f)
        return {
            'version': 'v25',
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': data.get('top_factors', [])[:3],
            'factor_weights': data.get('factor_weights', {}),
            'timestamp': data.get('timestamp', '')
        }
    
    return None

def get_factor_usage():
    """获取因子使用情况"""
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_factors WHERE trade_date >= "20250101"')
    sf = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_defensive_factors WHERE trade_date >= "20250101"')
    sdf = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_fina')
    fina = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'tech_stocks': sf,
        'def_stocks': sdf,
        'fina_stocks': fina,
        'total_factors': 26
    }

def generate_strategy_report():
    """生成策略效果报告"""
    strategy = get_latest_strategy()
    factors = get_factor_usage()
    
    if not strategy:
        return """📊 **策略状态汇报**

【当前策略组合】
- 状态: 暂无策略数据 ⚠️
- 建议: 运行 auto_optimizer.py 生成首份策略

【因子使用情况】
- 已采用: 0/26 个因子 (0%)
- 未采用: 26 个因子 (100%)
- 数据覆盖: 技术{}/防御{}/财务{} ✅

【后续优化点】
- 立即执行: tools/auto_optimizer.py 生成策略
- 优化器将自动发现最新版本 (v25/v26...)
""".format(factors['tech_stocks'], factors['def_stocks'], factors['fina_stocks'])
    
    # 构建报告
    report_lines = ["📊 **策略状态汇报**", ""]
    
    # 当前策略组合
    p = strategy['params']
    report_lines.append("【当前策略组合】")
    report_lines.append(f"- 仓位: {p.get('p', 0)*100:.0f}% | 止损: {p.get('s', 0)*100:.0f}% | 持仓: {p.get('n', 0)}只 | 调仓: {p.get('rebal', 10)}天")
    
    # 回测表现
    yearly_strs = []
    for y in strategy['yearly']:
        yearly_strs.append(f"{y['year']}:{y['return']*100:+.0f}%")
    report_lines.append(f"- 回测表现: {' | '.join(yearly_strs)}")
    report_lines.append(f"- 平均年化: {strategy['avg_return']:+.1f}% {'✅' if strategy['avg_return'] > 0 else '⚠️'}")
    
    # 因子使用情况
    used = strategy.get('factor_count', len(strategy['factor_weights']) if strategy['factor_weights'] else 6)
    unused = factors['total_factors'] - used
    report_lines.append("")
    report_lines.append("【因子使用情况】")
    report_lines.append(f"- 已采用: {used}/{factors['total_factors']} 个因子 ({used/factors['total_factors']*100:.0f}%)")
    report_lines.append(f"- 未采用: {unused}/{factors['total_factors']} 个因子 ({unused/factors['total_factors']*100:.0f}%)")
    
    if strategy['top_factors']:
        top_names = [f['factor'] for f in strategy['top_factors']]
        report_lines.append(f"- Top 3: {' | '.join(top_names)}")
    
    report_lines.append(f"- 数据覆盖: 技术{factors['tech_stocks']}/防御{factors['def_stocks']}/财务{factors['fina_stocks']} ✅")
    
    # 后续优化点
    report_lines.append("")
    report_lines.append("【后续优化点】")
    
    # 根据因子使用情况生成建议
    suggestions = []
    if unused > 0:
        suggestions.append(f"有{unused}个因子未采用，建议逐步引入测试效果")
        
        # 建议引入哪些因子
        all_factors = ['roe', 'revenue_growth', 'netprofit_growth', 'pe_ttm', 'pb', 
                      'rel_strength', 'mom_accel', 'money_flow', 'vol_ratio_amt']
        current_factors = set(strategy['factor_weights'].keys()) if strategy['factor_weights'] else set()
        missing_factors = [f for f in all_factors if f not in current_factors][:3]
        if missing_factors:
            suggestions.append(f"建议优先尝试: {', '.join(missing_factors)}")
    
    if strategy['avg_return'] < 15:
        suggestions.append("当前收益有提升空间，建议调整止损参数或增加防御因子权重")
    
    # 检查是否需要持续优化
    suggestions.append("持续运行优化器，每15分钟迭代寻找更优组合")
    
    for s in suggestions:
        report_lines.append(f"- {s}")
    
    return "\n".join(report_lines)

def save_and_print_report():
    """保存并打印报告"""
    report = generate_strategy_report()
    
    # 保存到文件
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    with open(f'{OPT}/strategy_report_{ts}.txt', 'w') as f:
        f.write(report)
    
    # 更新最新报告
    with open(f'{OPT}/latest_report.txt', 'w') as f:
        f.write(report)
    
    print(report)

if __name__ == '__main__':
    save_and_print_report()
