#!/root/.openclaw/workspace/venv/bin/python3
"""
生成因子使用情况报告 - 供heartbeat调用
"""
import sqlite3
import json
import os
from datetime import datetime

DB = '/root/.openclaw/workspace/data/historical/historical.db'
OUT = '/root/.openclaw/workspace/quant/optimizer'

def get_db_factor_counts():
    """获取数据库中各因子表的数据量"""
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    
    result = {}
    
    # stock_factors
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_factors WHERE trade_date >= "20250101"')
    result['stock_factors'] = {'stocks': cursor.fetchone()[0], 'factors': 14}
    
    # stock_defensive_factors
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_defensive_factors WHERE trade_date >= "20250101"')
    result['stock_defensive_factors'] = {'stocks': cursor.fetchone()[0], 'factors': 5}
    
    # stock_fina
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_fina')
    result['stock_fina'] = {'stocks': cursor.fetchone()[0], 'factors': 7}
    
    conn.close()
    
    result['total_factors'] = 26
    return result

def get_optimizer_factor_usage():
    """获取优化器使用的因子情况"""
    # 检查最新优化结果
    result_file = None
    for f in os.listdir(OUT):
        if f.startswith('v25_result_') and f.endswith('.json'):
            result_file = f
            break
    
    if result_file:
        with open(f'{OUT}/{result_file}', 'r') as f:
            data = json.load(f)
        return {
            'version': 'v25',
            'used_factors': len(data.get('factor_weights', {})),
            'total_factors': 26,
            'utilization': len(data.get('factor_weights', {})) / 26 * 100,
            'top_factors': data.get('top_factors', [])[:5]
        }
    
    # 检查v23结果
    for f in os.listdir(OUT):
        if f.startswith('result_') and f.endswith('.json'):
            return {
                'version': 'v23',
                'used_factors': 6,
                'total_factors': 26,
                'utilization': 23.1,
                'top_factors': []
            }
    
    return {
        'version': 'unknown',
        'used_factors': 0,
        'total_factors': 26,
        'utilization': 0,
        'top_factors': []
    }

def generate_report():
    """生成因子使用报告"""
    db_stats = get_db_factor_counts()
    opt_stats = get_optimizer_factor_usage()
    
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'database': db_stats,
        'optimizer': opt_stats,
        'recommendations': []
    }
    
    # 生成建议
    if opt_stats['utilization'] < 80:
        report['recommendations'].append({
            'type': 'warning',
            'message': f'因子利用率仅{opt_stats["utilization"]:.1f}%，建议运行v25增强优化器以利用全部26个因子'
        })
    
    if db_stats['stock_factors']['stocks'] < 3000:
        report['recommendations'].append({
            'type': 'error',
            'message': f'stock_factors仅覆盖{db_stats["stock_factors"]["stocks"]}只股票，需要补充数据'
        })
    
    # 保存报告
    with open(f'{OUT}/factor_usage_report.json', 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return report

def print_report():
    """打印可读性报告"""
    report = generate_report()
    
    print("="*60)
    print("📊 **因子使用情况报告**")
    print("="*60)
    
    print("\n📁 **数据库因子覆盖:**")
    print(f"  • 技术指标因子: {report['database']['stock_factors']['factors']}个 | 覆盖{report['database']['stock_factors']['stocks']}只股票")
    print(f"  • 防御因子: {report['database']['stock_defensive_factors']['factors']}个 | 覆盖{report['database']['stock_defensive_factors']['stocks']}只股票")
    print(f"  • 财务因子: {report['database']['stock_fina']['factors']}个 | 覆盖{report['database']['stock_fina']['stocks']}只股票")
    print(f"  • 总计: {report['database']['total_factors']}个因子")
    
    print("\n⚙️  **优化器因子使用:**")
    print(f"  • 当前版本: {report['optimizer']['version']}")
    print(f"  • 已使用: {report['optimizer']['used_factors']}/{report['optimizer']['total_factors']}个因子")
    print(f"  • 利用率: {report['optimizer']['utilization']:.1f}%")
    
    if report['optimizer']['top_factors']:
        print("\n🏆 **Top 5 有效因子:**")
        for i, f in enumerate(report['optimizer']['top_factors'], 1):
            print(f"  {i}. {f['factor']}: {f['score']:+.2f}%")
    
    if report['recommendations']:
        print("\n💡 **建议:**")
        for rec in report['recommendations']:
            icon = '⚠️' if rec['type'] == 'warning' else '❌'
            print(f"  {icon} {rec['message']}")
    
    print("\n" + "="*60)

if __name__ == '__main__':
    print_report()
