#!/root/.openclaw/workspace/venv/bin/python3
"""
GTC 2025 产业链分析报告生成器
分析光模块、铜缆、内存、PCB、液冷五大板块
"""
import os
import sys
from datetime import datetime

# 加载环境变量
env_path = '/root/.openclaw/workspace/.longbridge.env'
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

from longport.openapi import QuoteContext, Config

# 配置
config = Config.from_env()
ctx = QuoteContext(config)

# 定义产业链相关股票
categories = {
    "光模块": {
        "description": "AI算力核心基础设施，800G/1.6T高速光模块需求爆发",
        "stocks": [
            ("300502.SZ", "新易盛"),
            ("300308.SZ", "中际旭创"),
            ("300394.SZ", "天孚通信"),
            ("002281.SZ", "光迅科技"),
            ("300548.SZ", "博创科技"),
        ],
        "gtc_catalyst": [
            "Blackwell架构GPU大规模部署带动光模块需求",
            "NVIDIA展示1.6T光模块技术路线图",
            "CPO(共封装光学)技术成为下一代方向",
        ],
        "investment_logic": "光模块是AI算力最确定受益环节，英伟达新架构发布将直接拉动800G/1.6T需求",
    },
    "铜缆高速连接": {
        "description": "服务器内部短距离高速连接方案，GB200 NVL72采用铜缆方案",
        "stocks": [
            ("002130.SZ", "沃尔核材"),
            ("300563.SZ", "神宇股份"),
            ("300913.SZ", "兆龙互连"),
            ("300843.SZ", "胜蓝股份"),
        ],
        "gtc_catalyst": [
            "GB200 NVL72采用铜缆互连方案替代光模块",
            "安费诺等厂商铜缆产能持续扩产",
            "单机柜铜缆价值量显著提升",
        ],
        "investment_logic": "铜缆方案在短距离、大带宽场景具备成本优势，GB200放量直接利好",
    },
    "PCB": {
        "description": "AI服务器PCB用量大幅提升，HDI、高速多层板需求旺盛",
        "stocks": [
            ("002938.SZ", "鹏鼎控股"),
            ("300476.SZ", "胜宏科技"),
            ("600183.SH", "生益科技"),
            ("002916.SZ", "深南电路"),
            ("603228.SH", "景旺电子"),
        ],
        "gtc_catalyst": [
            "AI服务器PCB层数提升至20层以上",
            "HDI板用量大幅增加",
            "高速CCL材料升级至M7/M8级别",
        ],
        "investment_logic": "AI服务器PCB单机价值量是普通服务器3-5倍，算力建设持续拉动需求",
    },
    "液冷": {
        "description": "高算力密度下的散热解决方案，冷板式/浸没式液冷渗透率提升",
        "stocks": [
            ("300499.SZ", "高澜股份"),
            ("002837.SZ", "英维克"),
            ("603912.SH", "佳力图"),
            ("301018.SZ", "申菱环境"),
        ],
        "gtc_catalyst": [
            "GB200 TDP功耗突破1000W，风冷难以为继",
            "NVIDIA官方推荐液冷方案",
            "数据中心PUE政策推动液冷渗透",
        ],
        "investment_logic": "算力密度提升必然带来液冷渗透率提升，2025年是液冷放量元年",
    },
    "存储芯片": {
        "description": "HBM高带宽存储是AI芯片关键配套，供不应求持续",
        "stocks": [
            ("688525.SH", "佰维存储"),
            ("688008.SH", "澜起科技"),
            ("603986.SH", "兆易创新"),
            ("300223.SZ", "北京君正"),
            ("688766.SH", "普冉股份"),
        ],
        "gtc_catalyst": [
            "HBM3E量产进度超预期",
            "Blackwell标配HBM3E，单机容量大幅提升",
            "美光、三星、SK海力士产能持续扩产",
        ],
        "investment_logic": "HBM是AI芯片性能瓶颈，国产存储企业受益于行业景气度提升",
    },
}

def get_stock_data(symbol):
    """获取股票行情数据"""
    try:
        resp = ctx.quote([symbol])
        if resp:
            quote = resp[0]
            return {
                'symbol': symbol,
                'price': quote.last_done,
                'change': quote.change,
                'change_percent': quote.change_rate * 100 if quote.change_rate else 0,
                'volume': quote.volume,
                'high': quote.high,
                'low': quote.low,
            }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None

def generate_report():
    """生成分析报告"""
    report_lines = []
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    report_lines.append(f"# GTC 2025 产业链投资分析报告")
    report_lines.append(f"**报告日期**: {date_str}")
    report_lines.append(f"**事件**: NVIDIA GTC 2025 大会")
    report_lines.append("")
    
    # 报告摘要
    report_lines.append("## 📋 报告摘要")
    report_lines.append("")
    report_lines.append("NVIDIA GTC 2025大会于3月17-21日举行，核心亮点包括：")
    report_lines.append("- **Blackwell架构**: 新一代AI芯片全面量产")
    report_lines.append("- **GB200 NVL72**: 单机柜72颗GPU超大规模集群方案")
    report_lines.append("- **推理算力爆发**: 大模型推理需求推动算力建设加速")
    report_lines.append("")
    report_lines.append("五大受益产业链：光模块、铜缆连接、PCB、液冷、存储")
    report_lines.append("")
    
    # 各板块详细分析
    for category, data in categories.items():
        report_lines.append(f"## {category}")
        report_lines.append("")
        report_lines.append(f"**板块描述**: {data['description']}")
        report_lines.append("")
        
        report_lines.append("**GTC催化剂**:")
        for catalyst in data['gtc_catalyst']:
            report_lines.append(f"- {catalyst}")
        report_lines.append("")
        
        report_lines.append("**相关标的**:")
        for symbol, name in data['stocks']:
            stock_data = get_stock_data(symbol)
            if stock_data:
                change_str = f"{stock_data['change_percent']:+.2f}%" if stock_data['change_percent'] else "N/A"
                report_lines.append(f"- **{name}** ({symbol}): 价格 {stock_data['price']}, 涨跌幅 {change_str}")
            else:
                report_lines.append(f"- **{name}** ({symbol}): 数据获取失败")
        report_lines.append("")
        
        report_lines.append(f"**投资逻辑**: {data['investment_logic']}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")
    
    # 投资建议
    report_lines.append("## 💡 投资建议")
    report_lines.append("")
    report_lines.append("### 配置优先级")
    report_lines.append("")
    report_lines.append("| 优先级 | 板块 | 配置建议 | 核心逻辑 |")
    report_lines.append("|:---|:---|:---|:---|")
    report_lines.append("| **P0** | 光模块 | 30%仓位 | 最确定受益环节，800G/1.6T放量明确 |")
    report_lines.append("| **P1** | 铜缆连接 | 25%仓位 | GB200铜缆方案直接受益，估值相对合理 |")
    report_lines.append("| **P1** | PCB | 20%仓位 | AI服务器PCB量价齐升，业绩确定性强 |")
    report_lines.append("| **P2** | 液冷 | 15%仓位 | 长期趋势确定，短期渗透率仍低 |")
    report_lines.append("| **P2** | 存储 | 10%仓位 | HBM景气度高，但A股标的关联度较弱 |")
    report_lines.append("")
    
    report_lines.append("### 核心标的推荐")
    report_lines.append("")
    report_lines.append("**光模块三剑客**:")
    report_lines.append("- **中际旭创**(300308): 全球光模块龙头，1.6T产品领先")
    report_lines.append("- **新易盛**(300502): 800G主力供应商，毛利率行业最高")
    report_lines.append("- **天孚通信**(300394): 光器件龙头，MPO连接器直接受益")
    report_lines.append("")
    
    report_lines.append("**铜缆核心标的**:")
    report_lines.append("- **沃尔核材**(002130): 安费诺供应商，224G高速线材量产")
    report_lines.append("- **神宇股份**(300563): 高速铜缆直接受益GB200放量")
    report_lines.append("")
    
    report_lines.append("**PCB优质标的**:")
    report_lines.append("- **胜宏科技**(300476): AI服务器PCB核心供应商")
    report_lines.append("- **鹏鼎控股**(002938): 全球PCB龙头，技术实力强")
    report_lines.append("")
    
    report_lines.append("### 风险提示")
    report_lines.append("")
    report_lines.append("1. **估值风险**: 多数标的已大幅上涨，需关注估值消化")
    report_lines.append("2. **订单风险**: 英伟达订单节奏可能不及预期")
    report_lines.append("3. **技术路线风险**: CPO、硅光等新技术可能改变产业格局")
    report_lines.append("4. **竞争加剧**: 行业扩产可能导致价格战")
    report_lines.append("")
    
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("*报告生成时间: {}*".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    report_lines.append("*数据来源: 长桥API*")
    
    return "\n".join(report_lines)

if __name__ == "__main__":
    report = generate_report()
    output_path = '/root/.openclaw/workspace/data/gtc_2025_analysis.md'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"报告已生成: {output_path}")
    print(report)
