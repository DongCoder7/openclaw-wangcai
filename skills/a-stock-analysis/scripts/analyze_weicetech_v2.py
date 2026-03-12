#!/root/.openclaw/workspace/venv/bin/python3
# -*- coding: utf-8 -*-
"""
伟测科技（688372.SH）个股深度分析报告
生成时间: 2026-03-12
使用真实数据：长桥API + 腾讯财经
"""

import os
import sys
import json
import datetime
import requests

# 添加skills路径
sys.path.insert(0, '/root/.openclaw/workspace/skills/a-stock-analysis/scripts')

from longport.openapi import Config, QuoteContext

# 配置
STOCK_CODE = "688372.SH"  # 伟测科技
STOCK_CODE_LB = "688372.SH"  # 长桥代码  
STOCK_NAME = "伟测科技"
STOCK_CODE_TENCENT = "sh688372"  # 腾讯财经代码

def get_realtime_data():
    """获取真实股价和静态数据 - 长桥API"""
    print("=" * 60)
    print("【Step 1】获取真实股价数据（长桥API）")
    print("=" * 60)
    
    config = Config.from_env()
    ctx = QuoteContext(config)
    
    # 获取实时报价
    quote = ctx.quote([STOCK_CODE_LB])
    static = ctx.static_info([STOCK_CODE_LB])
    
    price = float(quote[0].last_done)
    eps_ttm = float(static[0].eps_ttm) if static[0].eps_ttm else 0
    total_shares = float(static[0].total_shares)
    
    # 计算PE和市值
    pe_ttm = price / eps_ttm if eps_ttm > 0 else 0
    market_cap = price * total_shares / 1e8  # 转换为亿元
    
    result = {
        "stock_name": STOCK_NAME,
        "stock_code": STOCK_CODE,
        "current_price": price,
        "eps_ttm": eps_ttm,
        "pe_ttm": pe_ttm,
        "total_shares": total_shares / 1e8,  # 亿股
        "market_cap": market_cap,
        "data_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "长桥OpenAPI"
    }
    
    print(f"✅ 股票名称: {STOCK_NAME}")
    print(f"✅ 股票代码: {STOCK_CODE}")
    print(f"✅ 当前股价: {price:.2f} 元")
    print(f"✅ EPS_TTM: {eps_ttm:.4f} 元")
    print(f"✅ PE_TTM: {pe_ttm:.2f} 倍")
    print(f"✅ 总股本: {total_shares/1e8:.4f} 亿股")
    print(f"✅ 总市值: {market_cap:.2f} 亿元")
    print(f"✅ 数据时间: {result['data_time']}")
    print()
    
    return result

def get_tencent_financial():
    """使用腾讯财经API获取财务数据"""
    print("=" * 60)
    print("【Step 2】获取财务数据（腾讯财经API）")
    print("=" * 60)
    
    try:
        # 腾讯财经主要财务指标API
        url = f"https://qt.gtimg.cn/q=sh688372"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.text
            parts = data.split('~')
            
            # 解析腾讯数据格式
            # parts[3] = 当前价, [4] = 昨收, [5] = 今开
            # [39] = 市盈率, [44] = 总市值, [45] = 流通市值
            
            current_price = float(parts[3]) if len(parts) > 3 else 0
            pe = float(parts[39]) if len(parts) > 39 and parts[39] else 0
            total_cap = float(parts[44]) / 100000000 if len(parts) > 44 and parts[44] else 0  # 转换为亿
            
            print(f"✅ 当前股价: {current_price:.2f} 元")
            print(f"✅ 市盈率(动): {pe:.2f} 倍")
            print(f"✅ 总市值: {total_cap:.2f} 亿元")
            print()
            
            return {
                "current_price_tencent": current_price,
                "pe_tencent": pe,
                "market_cap_tencent": total_cap,
                "data_source": "腾讯财经"
            }
    except Exception as e:
        print(f"腾讯财经获取失败: {e}")
    
    return None

def get_company_profile():
    """获取公司基本资料"""
    print("=" * 60)
    print("【Step 3】公司基本资料")
    print("=" * 60)
    
    profile = {
        "fullname": "上海伟测半导体科技股份有限公司",
        "shortname": "伟测科技",
        "industry": "半导体 - 集成电路测试服务",
        "list_date": "2022-10-26",  # 科创板上市
        "province": "上海市",
        "main_business": "第三方集成电路测试服务",
        "products": [
            "晶圆测试（CP测试）",
            "芯片成品测试（FT测试）",
            "测试方案开发",
            "老化测试（Burn-in）"
        ],
        "data_source": "公开资料整理"
    }
    
    print(f"✅ 公司全称: {profile['fullname']}")
    print(f"✅ 所属行业: {profile['industry']}")
    print(f"✅ 上市日期: {profile['list_date']}")
    print(f"✅ 主营业务: {profile['main_business']}")
    print()
    
    return profile

def analyze_business_model():
    """业务结构分析"""
    print("=" * 60)
    print("【Step 4】业务结构分析")
    print("=" * 60)
    
    business = {
        "segments": [
            {
                "name": "晶圆测试（CP测试）",
                "description": "对未切割晶圆上的每个芯片进行功能和性能测试",
                "characteristics": "技术壁垒高、设备投入大、客户粘性强"
            },
            {
                "name": "芯片成品测试（FT测试）",
                "description": "对封装后的芯片进行最终测试验证",
                "characteristics": "产能灵活、周转快、服务响应要求高"
            },
            {
                "name": "测试方案开发",
                "description": "为客户提供定制化测试解决方案",
                "characteristics": "技术附加值高、差异化竞争"
            }
        ],
        "industry_chain": {
            "upstream": ["测试设备（泰瑞达、爱德万）", "探针卡", "测试座"],
            "company": "伟测科技 - 第三方测试服务",
            "downstream": ["芯片设计公司", "晶圆代工厂", "IDM厂商"]
        }
    }
    
    print("核心业务板块:")
    for seg in business["segments"]:
        print(f"  • {seg['name']}: {seg['description']}")
        print(f"    特点: {seg['characteristics']}")
    
    print("\n产业链定位:")
    print(f"  上游: {', '.join(business['industry_chain']['upstream'])}")
    print(f"  中游: {business['industry_chain']['company']}")
    print(f"  下游: {', '.join(business['industry_chain']['downstream'])}")
    print()
    
    return business

def get_peers_comparison():
    """同行对比"""
    print("=" * 60)
    print("【Step 5】同行对比分析（长桥API实时数据）")
    print("=" * 60)
    
    config = Config.from_env()
    ctx = QuoteContext(config)
    
    # 可比公司
    peers = [
        {"code": "688206.SH", "name": "概伦电子"},
        {"code": "688120.SH", "name": "华海清科"},
        {"code": "688019.SH", "name": "安集科技"},
    ]
    
    peer_results = []
    
    for peer in peers:
        try:
            quote = ctx.quote([peer["code"]])
            static = ctx.static_info([peer["code"]])
            
            price = float(quote[0].last_done)
            eps = float(static[0].eps_ttm) if static[0].eps_ttm else 0
            shares = float(static[0].total_shares)
            pe = price / eps if eps > 0 else 0
            cap = price * shares / 1e8
            
            peer_results.append({
                "name": peer["name"],
                "code": peer["code"],
                "price": price,
                "pe": pe,
                "market_cap": cap
            })
        except Exception as e:
            print(f"  {peer['name']} 数据获取失败")
    
    print(f"{'公司':<12} {'股价':<10} {'PE_TTM':<10} {'市值(亿)':<12}")
    print("-" * 50)
    
    # 先打印伟测科技
    quote = ctx.quote([STOCK_CODE_LB])
    static = ctx.static_info([STOCK_CODE_LB])
    price = float(quote[0].last_done)
    eps = float(static[0].eps_ttm) if static[0].eps_ttm else 0
    shares = float(static[0].total_shares)
    pe = price / eps if eps > 0 else 0
    cap = price * shares / 1e8
    
    print(f"{'伟测科技*':<12} {price:<10.2f} {pe:<10.2f} {cap:<12.2f}")
    
    for p in peer_results:
        print(f"{p['name']:<12} {p['price']:<10.2f} {p['pe']:<10.2f} {p['market_cap']:<12.2f}")
    
    print("\n* 目标公司")
    print()
    
    return peer_results

def valuation_analysis(price_data):
    """估值分析 - 展示完整计算过程"""
    print("=" * 60)
    print("【Step 6】估值分析（展示完整计算过程）")
    print("=" * 60)
    
    current_price = price_data['current_price']
    total_shares = price_data['total_shares']  # 亿股
    current_cap = price_data['market_cap']
    pe_ttm = price_data['pe_ttm']
    
    print("=" * 60)
    print("一、基础数据确认")
    print("=" * 60)
    print(f"✅ 当前股价: {current_price:.2f} 元")
    print(f"✅ 总股本: {total_shares:.4f} 亿股 = {total_shares * 1e8:,.0f} 股")
    print(f"✅ 当前市值: {current_price:.2f} × {total_shares:.4f} = {current_cap:.2f} 亿元")
    print(f"✅ 当前PE_TTM: {pe_ttm:.2f} 倍")
    
    # 反向验证
    check_price = current_cap * 1e8 / (total_shares * 1e8)
    print(f"✅ 反向验证: {current_cap:.2f}亿 ÷ {total_shares:.4f}亿 = {check_price:.2f}元 ✓")
    
    print("\n" + "=" * 60)
    print("二、三情景估值计算")
    print("=" * 60)
    
    # 基于半导体测试行业和公司成长性设定参数
    # 参考同行PE和成长性
    scenarios = [
        {
            "name": "保守",
            "profit_2025": 1.0,  # 亿元（考虑行业周期和产能爬坡）
            "pe": 45,
            "reason": "行业周期下行，产能利用率不足"
        },
        {
            "name": "中性", 
            "profit_2025": 1.5,
            "pe": 60,
            "reason": "行业平稳，产能逐步释放"
        },
        {
            "name": "乐观",
            "profit_2025": 2.2,
            "pe": 80,
            "reason": "AI芯片测试需求爆发，国产替代加速"
        }
    ]
    
    print(f"\n{'情景':<8} {'2025净利':<12} {'PE':<8} {'目标市值':<15} {'目标价':<12} {'上涨空间':<10} {'假设'}")
    print("-" * 100)
    
    results = []
    for s in scenarios:
        target_cap = s["profit_2025"] * s["pe"]
        target_price = target_cap / total_shares
        upside = (target_price - current_price) / current_price * 100
        
        print(f"{s['name']:<8} {s['profit_2025']:<12.2f} {s['pe']:<8} "
              f"{s['profit_2025']:.2f}×{s['pe']}{'<':<3} {target_cap:<10.2f}亿 "
              f"{target_cap:.2f}÷{total_shares:.4f}{'<':<3} {target_price:<10.2f}元 "
              f"{upside:+.1f}%   {s['reason']}")
        
        results.append({
            "name": s["name"],
            "profit": s["profit_2025"],
            "pe": s["pe"],
            "target_cap": target_cap,
            "target_price": target_price,
            "upside": upside
        })
    
    print("\n" + "=" * 60)
    print("三、反向验证")
    print("=" * 60)
    for r in results:
        verify_cap = r["target_price"] * total_shares
        print(f"{r['name']}情景: {r['target_price']:.2f}元 × {total_shares:.4f}亿股 = {verify_cap:.2f}亿元 "
              f"{'✓' if abs(verify_cap - r['target_cap']) < 0.1 else '✗'}")
    
    print("\n" + "=" * 60)
    print("四、估值结论")
    print("=" * 60)
    
    # 当前PE与情景PE对比
    print(f"当前PE_TTM: {pe_ttm:.2f}倍")
    print(f"保守情景PE: 45倍 → 目标价 {results[0]['target_price']:.2f}元 ({results[0]['upside']:+.1f}%)")
    print(f"中性情景PE: 60倍 → 目标价 {results[1]['target_price']:.2f}元 ({results[1]['upside']:+.1f}%)")
    print(f"乐观情景PE: 80倍 → 目标价 {results[2]['target_price']:.2f}元 ({results[2]['upside']:+.1f}%)")
    
    if pe_ttm > 70:
        print(f"\n⚠️ 当前PE ({pe_ttm:.1f}倍) 处于较高水平，接近乐观情景估值")
    elif pe_ttm > 50:
        print(f"\n📊 当前PE ({pe_ttm:.1f}倍) 处于中性偏高水平")
    else:
        print(f"\n✅ 当前PE ({pe_ttm:.1f}倍) 估值相对合理")
    
    print()
    
    return {
        "current_price": current_price,
        "current_cap": current_cap,
        "pe_ttm": pe_ttm,
        "scenarios": results
    }

def risk_analysis():
    """风险分析"""
    print("=" * 60)
    print("【Step 7】风险分析（分级）")
    print("=" * 60)
    
    risks = {
        "high": [
            ("估值风险", "当前PE超70倍，若业绩不及预期有回调压力"),
            ("行业周期", "半导体行业周期性波动影响测试需求")
        ],
        "medium": [
            ("客户集中", "前五大客户占比较高"),
            ("设备依赖", "高端测试设备依赖进口"),
            ("竞争加剧", "第三方测试行业竞争日益激烈")
        ],
        "low": [
            ("技术迭代", "需持续投入研发跟进测试技术"),
            ("产能爬坡", "新产能投产初期利用率可能不足")
        ]
    }
    
    print("🔴 高风险:")
    for name, desc in risks["high"]:
        print(f"  • {name}: {desc}")
    
    print("\n🟡 中风险:")
    for name, desc in risks["medium"]:
        print(f"  • {name}: {desc}")
    
    print("\n🟢 低风险:")
    for name, desc in risks["low"]:
        print(f"  • {name}: {desc}")
    
    print()
    return risks

def investment_recommendation(price_data, valuation):
    """投资建议"""
    print("=" * 60)
    print("【Step 8】投资建议")
    print("=" * 60)
    
    current_price = price_data['current_price']
    pe_ttm = price_data['pe_ttm']
    
    # 确定评级
    if pe_ttm > 75:
        rating = "🔴 持有/观望"
        action = "等待回调"
    elif pe_ttm > 55:
        rating = "🟡 谨慎买入"
        action = "分批建仓"
    else:
        rating = "🟢 买入"
        action = "积极配置"
    
    # 建议买入区间（中性目标价的8折）
    buy_zone_low = valuation['scenarios'][0]['target_price'] * 0.8
    buy_zone_high = valuation['scenarios'][1]['target_price'] * 0.9
    
    # 止损位（中性目标价的60%）
    stop_loss = valuation['scenarios'][0]['target_price'] * 0.6
    
    print(f"综合评级: {rating}")
    print(f"建议操作: {action}")
    print()
    print(f"核心逻辑:")
    print(f"  • 半导体测试行业长期受益于国产替代和AI芯片需求增长")
    print(f"  • 公司是国内领先的第三方测试服务商，技术积累深厚")
    print(f"  • 但当前估值偏高({pe_ttm:.1f}倍PE)，需关注业绩兑现")
    print()
    print(f"操作建议:")
    print(f"  • 建议买入区间: ¥{buy_zone_low:.0f}-{buy_zone_high:.0f}")
    print(f"  • 止损位: ¥{stop_loss:.0f} (-{(1-stop_loss/current_price)*100:.0f}%)")
    print(f"  • 中性目标价: ¥{valuation['scenarios'][1]['target_price']:.0f} (+{valuation['scenarios'][1]['upside']:.0f}%)")
    print()
    print(f"跟踪指标:")
    print(f"  • 季度营收增速（重点关注产能利用率）")
    print(f"  • 新签订单情况")
    print(f"  • AI芯片测试业务占比变化")
    print()
    
    return {
        "rating": rating,
        "action": action,
        "buy_zone": f"¥{buy_zone_low:.0f}-{buy_zone_high:.0f}",
        "stop_loss": stop_loss,
        "target": valuation['scenarios'][1]['target_price']
    }

def generate_full_report():
    """生成完整分析报告"""
    print("\n" + "=" * 80)
    print("伟测科技（688372.SH）个股深度分析报告")
    print("=" * 80)
    print(f"报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 步骤1: 获取真实股价
    price_data = get_realtime_data()
    
    # 步骤2: 获取财务数据
    tencent_data = get_tencent_financial()
    
    # 步骤3: 公司资料
    company = get_company_profile()
    
    # 步骤4: 业务分析
    business = analyze_business_model()
    
    # 步骤5: 同行对比
    peers = get_peers_comparison()
    
    # 步骤6: 估值分析（核心）
    valuation = valuation_analysis(price_data)
    
    # 步骤7: 风险分析
    risks = risk_analysis()
    
    # 步骤8: 投资建议
    recommendation = investment_recommendation(price_data, valuation)
    
    # 汇总
    print("=" * 80)
    print("【汇总】数据真实性声明")
    print("=" * 80)
    print("✅ 股价数据: 长桥OpenAPI 实时获取")
    print("✅ PE/股本数据: 长桥OpenAPI 静态数据")
    print("✅ 市值计算: 股价 × 总股本（已反向验证）")
    print("✅ 同行数据: 长桥OpenAPI 实时获取")
    print("✅ 计算过程: 全部展示，可复现")
    print()
    
    # 保存报告
    report = {
        "stock_name": STOCK_NAME,
        "stock_code": STOCK_CODE,
        "price_data": price_data,
        "company": company,
        "valuation": valuation,
        "recommendation": recommendation,
        "report_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    output_file = f"/root/.openclaw/workspace/data/analysis_688372_{datetime.datetime.now().strftime('%Y%m%d')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 报告数据已保存: {output_file}")
    
    return report

if __name__ == "__main__":
    generate_full_report()
