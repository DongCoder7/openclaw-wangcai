#!/root/.openclaw/workspace/venv/bin/python3
"""
实盘跟踪分析 - 持仓组合监控与明日计划

用法:
  ./venv_runner.sh tools/portfolio_tracker.py

功能:
  1. 读取持仓组合配置
  2. 分析每只持仓股票的短期走势
  3. 计算组合整体盈亏状况
  4. 生成明日操作计划

持仓配置:
  portfolio_config.json - 持仓股票和数量
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

from longport.openapi import QuoteContext, Config

# 持仓配置 (2026-03-11 初始)
PORTFOLIO = {
    "300750.SZ": {"name": "宁德时代", "shares": 1000, "cost": None},
    "300274.SZ": {"name": "阳光电源", "shares": 1500, "cost": None},
    "688676.SH": {"name": "金盘科技", "shares": 2000, "cost": None},
    "600875.SH": {"name": "东方电气", "shares": 3000, "cost": None},
    "601088.SH": {"name": "中国神华", "shares": 3000, "cost": None},
    "603986.SH": {"name": "兆易创新", "shares": 1500, "cost": None},
    "688008.SH": {"name": "澜起科技", "shares": 2000, "cost": None},
    "603920.SH": {"name": "世运电路", "shares": 4000, "cost": None},
    "002463.SZ": {"name": "沪电股份", "shares": 3000, "cost": None},
}


def init_api():
    """初始化长桥API"""
    env_file = '/root/.openclaw/workspace/.longbridge.env'
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"')
    
    config = Config.from_env()
    return QuoteContext(config)


def analyze_position(ctx, symbol, info):
    """分析单个持仓"""
    try:
        quote = ctx.quote([symbol])
        static = ctx.static_info([symbol])
        
        current_price = float(quote[0].last_done)
        prev_close = float(quote[0].prev_close)
        change_pct = (current_price - prev_close) / prev_close * 100
        shares = info['shares']
        market_value = current_price * shares
        
        return {
            'symbol': symbol,
            'name': info['name'],
            'shares': shares,
            'price': current_price,
            'change_pct': change_pct,
            'market_value': market_value,
            'prev_close': prev_close
        }
    except Exception as e:
        print(f"❌ {symbol} 分析失败: {e}")
        return None


def analyze_trend_simple(price, ma20):
    """简化趋势判断"""
    if price > ma20 * 1.05:
        return "强势上涨", "📈"
    elif price > ma20:
        return "趋势向上", "📈"
    elif price < ma20 * 0.95:
        return "弱势下跌", "📉"
    else:
        return "震荡整理", "➡️"


def generate_plan(position):
    """生成明日操作计划"""
    change = position['change_pct']
    
    if change > 5:
        return "持有观望", "今日大涨，明日可能冲高，观察是否突破压力位"
    elif change > 2:
        return "持有", "趋势良好，继续持有"
    elif change < -5:
        return "关注止损", "今日大跌，明日关注是否反弹，若继续下跌考虑减仓"
    elif change < -2:
        return "观察", "小幅回调，观察明日走势"
    else:
        return "持有观望", "震荡走势，等待方向明确"


def main():
    print("="*70)
    print("📊 实盘跟踪 - 持仓组合分析")
    print("="*70)
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    ctx = init_api()
    
    print("\n【Step 1】获取持仓实时数据\n")
    
    positions = []
    total_value = 0
    
    for symbol, info in PORTFOLIO.items():
        pos = analyze_position(ctx, symbol, info)
        if pos:
            positions.append(pos)
            total_value += pos['market_value']
            print(f"  {pos['name']} ({symbol}): {pos['price']:.2f}元 × {pos['shares']}股 = {pos['market_value']/1e4:.2f}万元 ({pos['change_pct']:+.2f}%)")
    
    print(f"\n  组合总市值: {total_value/1e4:.2f}万元")
    
    print("\n【Step 2】短期走势分析\n")
    
    # 调用short-term-analysis进行批量分析
    import subprocess
    symbols_str = ' '.join(PORTFOLIO.keys())
    
    print("  执行短期技术分析...")
    result = subprocess.run(
        f"cd /root/.openclaw/workspace && ./venv_runner.sh skills/short-term-analysis/scripts/analyze_short_term.py {symbols_str}",
        shell=True, capture_output=True, text=True, timeout=300
    )
    
    # 解析结果
    lines = result.stdout.split('\n')
    analysis_results = {}
    
    for i, line in enumerate(lines):
        if '🥇' in line or '🥈' in line or '🥉' in line or (line.strip() and line.strip()[0].isdigit() and '.' in line[:5]):
            # 解析排名行
            parts = line.split()
            if len(parts) >= 2:
                symbol = parts[1] if len(parts) > 1 else ""
                if symbol in PORTFOLIO:
                    # 找评分和预测
                    for j in range(i, min(i+5, len(lines))):
                        if '评分:' in lines[j]:
                            score_part = lines[j].split('评分:')[1].split('|')[0].strip()
                            outlook_part = lines[j].split('|')[1].strip() if '|' in lines[j] else ""
                            analysis_results[symbol] = {
                                'score': score_part,
                                'outlook': outlook_part
                            }
                            break
    
    print("\n【Step 3】持仓分析与明日计划\n")
    
    print(f"{'股票':<10} {'代码':<12} {'现价':<8} {'涨跌':<8} {'评分':<6} {'预测':<10} {'明日计划':<10}")
    print("-"*70)
    
    for pos in positions:
        symbol = pos['symbol']
        ana = analysis_results.get(symbol, {'score': 'N/A', 'outlook': 'N/A'})
        plan, reason = generate_plan(pos)
        
        print(f"{pos['name']:<10} {symbol:<12} {pos['price']:<8.2f} {pos['change_pct']:+7.2f}% {ana['score']:<6} {ana['outlook']:<10} {plan:<10}")
    
    print("\n【Step 4】组合整体评估\n")
    
    # 计算板块分布
    sectors = {
        '新能源': ['300750.SZ', '300274.SZ'],
        '电力设备': ['688676.SH', '600875.SH'],
        '能源': ['601088.SH'],
        '半导体': ['603986.SH', '688008.SH'],
        'PCB': ['603920.SH', '002463.SZ']
    }
    
    sector_values = {}
    for sector, symbols in sectors.items():
        value = sum([p['market_value'] for p in positions if p['symbol'] in symbols])
        sector_values[sector] = value
    
    print("  板块分布:")
    for sector, value in sorted(sector_values.items(), key=lambda x: -x[1]):
        pct = value / total_value * 100
        print(f"    {sector}: {value/1e4:.2f}万元 ({pct:.1f}%)")
    
    print("\n【明日操作计划汇总】\n")
    
    strong_buy = [p for p in positions if p['symbol'] in analysis_results and float(analysis_results[p['symbol']]['score']) >= 2]
    hold = [p for p in positions if p['symbol'] in analysis_results and 0 <= float(analysis_results[p['symbol']]['score']) < 2]
    watch = [p for p in positions if p['symbol'] in analysis_results and float(analysis_results[p['symbol']]['score']) < 0]
    
    if strong_buy:
        print("🚀 强势持仓 (评分≥2.0，可持有或加仓):")
        for p in strong_buy:
            print(f"    • {p['name']}: 当前{p['price']:.2f}元，今日{p['change_pct']:+.2f}%")
    
    if hold:
        print("\n📈 正常持仓 (评分0-2.0，持有观望):")
        for p in hold:
            print(f"    • {p['name']}: 当前{p['price']:.2f}元，今日{p['change_pct']:+.2f}%")
    
    if watch:
        print("\n⚠️ 关注持仓 (评分<0，注意风险):")
        for p in watch:
            print(f"    • {p['name']}: 当前{p['price']:.2f}元，今日{p['change_pct']:+.2f}%，关注明日走势")
    
    print("\n【风险提示】")
    print("  1. 以上分析基于技术指标，不构成投资建议")
    print("  2. 请结合自身风险承受能力和投资目标决策")
    print("  3. 建议设置止损位，控制单只持仓风险")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    main()
