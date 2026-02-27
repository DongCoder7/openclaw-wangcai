#!/usr/bin/env python3
"""
板块分析示例脚本
演示如何使用 a_sector_analysis skill
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace')

from skills.a_sector_analysis import (
    SectorRotationAnalyzer,
    analyze_sector,
    compare_sectors,
    get_rotation_signals,
    detect_market_style,
    generate_portfolio
)

def demo_single_sector():
    """演示：分析单个板块"""
    print("\n" + "="*80)
    print("示例1: 分析单个板块 - AI算力")
    print("="*80)
    
    analyzer = SectorRotationAnalyzer()
    result = analyzer.analyze_sector("AI算力")
    print(analyzer.format_report(result))


def demo_compare_sectors():
    """演示：对比多个板块"""
    print("\n" + "="*80)
    print("示例2: 对比多个板块")
    print("="*80)
    
    analyzer = SectorRotationAnalyzer()
    sectors = ['AI算力', '半导体设备', '储能', '人形机器人']
    result = analyzer.compare_sectors(sectors)
    
    print(f"\n对比板块: {', '.join(sectors)}")
    print("\n板块强弱排序:")
    for i, sector_data in enumerate(result['sectors'], 1):
        score = sector_data['score']
        print(f"{i}. {score['rating']} {sector_data['sector']} - {score['total_score']}分")
    
    print(f"\n🏆 最强板块: {result['top_pick']['sector']}")


def demo_rotation_signals():
    """演示：获取轮动信号"""
    print("\n" + "="*80)
    print("示例3: 全市场轮动信号")
    print("="*80)
    
    signals = get_rotation_signals()
    
    print(f"\n发现 {len(signals)} 个轮动信号:")
    print("\n【买入信号】")
    for s in signals:
        if s['signal'] == 'buy':
            print(f"  🟢 {s['sector']}: 强度{s['strength']:.1f} - {s['reason']}")
    
    print("\n【卖出信号】")
    for s in signals:
        if s['signal'] == 'sell':
            print(f"  🔴 {s['sector']}: 强度{s['strength']:.1f} - {s['reason']}")


def demo_market_style():
    """演示：判断市场风格"""
    print("\n" + "="*80)
    print("示例4: 市场风格判断")
    print("="*80)
    
    style = detect_market_style()
    
    print(f"\n当前风格: {style['description']}")
    print(f"成长板块评分: {style['growth_score']}")
    print(f"价值板块评分: {style['value_score']}")
    print(f"\n配置建议: {style['suggestion']}")


def demo_portfolio_config():
    """演示：生成配置方案"""
    print("\n" + "="*80)
    print("示例5: 生成板块配置方案")
    print("="*80)
    
    for risk in ['low', 'medium', 'high']:
        print(f"\n【{risk} 风险等级配置】")
        portfolio = generate_portfolio(risk_level=risk)
        
        print(f"分级配置: T0={portfolio['tier_allocation']['T0']}%, T1={portfolio['tier_allocation']['T1']}%, T2={portfolio['tier_allocation']['T2']}%, T3={portfolio['tier_allocation']['T3']}%")
        print("\n板块权重TOP5:")
        for s in portfolio['sector_weights'][:5]:
            print(f"  - {s['sector']} ({s['tier']}): {s['weight']}%")


def main():
    print("\n" + "="*80)
    print("🎯 A股板块分析Skill 使用示例")
    print("="*80)
    
    demo_single_sector()
    demo_compare_sectors()
    demo_rotation_signals()
    demo_market_style()
    demo_portfolio_config()
    
    print("\n" + "="*80)
    print("✅ 所有示例运行完成!")
    print("="*80)


if __name__ == "__main__":
    main()
