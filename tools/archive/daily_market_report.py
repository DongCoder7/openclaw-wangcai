#!/root/.openclaw/workspace/venv/bin/python3
"""
每日收盘报告 - 完整版
包含市场全景、板块分析、个股表现、策略建议
"""
import sqlite3
import pandas as pd
import json
import subprocess
from datetime import datetime, timedelta
import sys
import os

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

def get_market_overview():
    """获取市场全景"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 获取最新日期
        latest_date = pd.read_sql("SELECT MAX(trade_date) FROM stock_factors", conn).iloc[0, 0]
        
        # 获取市场涨跌统计
        df = pd.read_sql(f"""
            SELECT ts_code, ret_20, vol_20, money_flow
            FROM stock_factors
            WHERE trade_date = '{latest_date}'
            AND ret_20 IS NOT NULL
        """, conn)
        
        conn.close()
        
        # 计算涨跌家数
        up_count = len(df[df['ret_20'] > 0])
        down_count = len(df[df['ret_20'] < 0])
        flat_count = len(df[df['ret_20'] == 0])
        
        # 计算市场情绪
        avg_ret = df['ret_20'].mean()
        
        return {
            'date': latest_date,
            'up': up_count,
            'down': down_count,
            'flat': flat_count,
            'total': len(df),
            'avg_ret': avg_ret
        }
    except Exception as e:
        print(f"获取市场全景失败: {e}")
        return None

def get_sector_performance():
    """获取板块表现"""
    # 定义主要板块及其代表股票
    sectors = {
        'AI算力': ['300308', '300502', '603019', '688981'],
        '半导体': ['688012', '603893', '300760', '600584'],
        '新能源': ['300750', '601012', '600438', '002594'],
        '金融': ['600036', '000001', '601318', '601166'],
        '消费': ['600519', '000858', '600887', '603288'],
        '医药': ['600276', '603259', '300760', '000538'],
        '科技': ['000938', '600570', '002230', '600498']
    }
    
    try:
        conn = sqlite3.connect(DB_PATH)
        latest_date = pd.read_sql("SELECT MAX(trade_date) FROM stock_factors", conn).iloc[0, 0]
        
        sector_data = []
        
        for sector_name, codes in sectors.items():
            codes_str = "','".join(codes)
            df = pd.read_sql(f"""
                SELECT ts_code, ret_20, vol_20
                FROM stock_factors
                WHERE ts_code IN ('{codes_str}')
                AND trade_date = '{latest_date}'
                AND ret_20 IS NOT NULL
            """, conn)
            
            if not df.empty:
                avg_change = df['ret_20'].mean()
                up_count = len(df[df['ret_20'] > 0])
                sector_data.append({
                    'name': sector_name,
                    'change': avg_change,
                    'up_count': up_count,
                    'total': len(df)
                })
        
        conn.close()
        
        # 按涨幅排序
        sector_data.sort(key=lambda x: x['change'], reverse=True)
        return sector_data
    except Exception as e:
        print(f"获取板块表现失败: {e}")
        return []

def get_top_stocks():
    """获取涨跌幅榜"""
    try:
        conn = sqlite3.connect(DB_PATH)
        latest_date = pd.read_sql("SELECT MAX(trade_date) FROM stock_factors", conn).iloc[0, 0]
        
        df = pd.read_sql(f"""
            SELECT ts_code, ret_20, ret_60, vol_20, money_flow, rel_strength
            FROM stock_factors
            WHERE trade_date = '{latest_date}'
            AND ret_20 IS NOT NULL
            AND vol_20 IS NOT NULL
        """, conn)
        
        conn.close()
        
        # 涨幅榜 (20日涨幅)
        top_gainers = df.nlargest(10, 'ret_20')[['ts_code', 'ret_20', 'ret_60', 'rel_strength']].to_dict('records')
        
        # 跌幅榜
        top_losers = df.nsmallest(10, 'ret_20')[['ts_code', 'ret_20', 'ret_60', 'rel_strength']].to_dict('records')
        
        # 资金流入
        top_money = df.nlargest(10, 'money_flow')[['ts_code', 'money_flow', 'ret_20']].to_dict('records')
        
        return {
            'gainers': top_gainers,
            'losers': top_losers,
            'money_flow': top_money
        }
    except Exception as e:
        print(f"获取涨跌幅榜失败: {e}")
        return {'gainers': [], 'losers': [], 'money_flow': []}

def vqm_stock_picking():
    """VQM模型选股"""
    try:
        conn = sqlite3.connect(DB_PATH)
        latest_date = pd.read_sql("SELECT MAX(trade_date) FROM stock_factors", conn).iloc[0, 0]
        
        df = pd.read_sql(f"""
            SELECT ts_code, ret_20, ret_60, ret_120, vol_20, 
                   money_flow, price_pos_20, mom_accel, rel_strength
            FROM stock_factors
            WHERE trade_date = '{latest_date}'
            AND ret_20 IS NOT NULL
        """, conn)
        
        conn.close()
        
        # VQM评分 - 基于现有字段
        df['score'] = (
            df['ret_20'].rank(pct=True) * 0.20 +
            df['ret_60'].rank(pct=True) * 0.15 +
            df['mom_accel'].rank(pct=True) * 0.15 +
            (1 - df['vol_20'].rank(pct=True)) * 0.15 +
            df['money_flow'].rank(pct=True) * 0.15 +
            df['price_pos_20'].rank(pct=True) * 0.20
        )
        
        top_stocks = df.nlargest(15, 'score')[['ts_code', 'score', 'ret_20', 'ret_60', 'vol_20', 'money_flow']].to_dict('records')
        
        return top_stocks
    except Exception as e:
        print(f"VQM选股失败: {e}")
        return []

def get_portfolio_status():
    """获取模拟盘状态"""
    try:
        import json
        with open('/root/.openclaw/workspace/data/sim_portfolio.json', 'r') as f:
            portfolio = json.load(f)
        return portfolio
    except:
        return None

def generate_report():
    """生成完整收盘报告"""
    now = datetime.now()
    
    print("📊 获取市场全景...")
    market = get_market_overview()
    
    print("📈 获取板块表现...")
    sectors = get_sector_performance()
    
    print("🔥 获取涨跌幅榜...")
    top_stocks = get_top_stocks()
    
    print("🎯 VQM模型选股...")
    vqm_stocks = vqm_stock_picking()
    
    print("💼 获取模拟盘...")
    portfolio = get_portfolio_status()
    
    # 构建报告
    report = f"""📊 **每日收盘深度报告** {now.strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📈 市场全景**

• 🟢 上涨: {market['up'] if market else '--'} 只
• 🔴 下跌: {market['down'] if market else '--'} 只  
• ⚪ 平盘: {market['flat'] if market else '--'} 只
• 📊 总计: {market['total'] if market else '--'} 只
• 📉 20日平均: {market['avg_ret']*100 if market and market['avg_ret'] else '--':.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🔥 板块表现排序** (20日涨跌幅)

"""
    
    # 添加板块数据
    for i, sector in enumerate(sectors[:7], 1):
        emoji = "🟢" if sector['change'] > 0 else "🔴"
        change = sector['change'] * 100 if sector['change'] else 0
        report += f"{i}. {emoji} **{sector['name']}**: {change:+.2f}% ({sector['up_count']}/{sector['total']}上涨)\n"
    
    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📊 涨跌幅榜** (20日涨跌幅)

**涨幅前十**:
"""
    
    for i, stock in enumerate(top_stocks['gainers'][:8], 1):
        ret = stock['ret_20'] * 100 if stock['ret_20'] else 0
        report += f"{i}. **{stock['ts_code']}**: {ret:+.2f}%\n"
    
    report += """
**跌幅前十**:
"""
    
    for i, stock in enumerate(top_stocks['losers'][:8], 1):
        ret = stock['ret_20'] * 100 if stock['ret_20'] else 0
        report += f"{i}. **{stock['ts_code']}**: {ret:+.2f}%\n"
    
    report += """
**资金净流入**:
"""
    
    for i, stock in enumerate(top_stocks['money_flow'][:8], 1):
        mf = stock['money_flow'] if stock['money_flow'] else 0
        report += f"{i}. **{stock['ts_code']}**: {mf:+.2f}M\n"
    
    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🎯 VQM模型精选** (Top 15)

"""
    
    for i, stock in enumerate(vqm_stocks[:15], 1):
        ret20 = stock['ret_20'] * 100 if stock['ret_20'] else 0
        ret60 = stock['ret_60'] * 100 if stock['ret_60'] else 0
        vol = stock['vol_20'] if stock['vol_20'] else 0
        mf = stock['money_flow'] if stock['money_flow'] else 0
        report += f"{i}. **{stock['ts_code']}** | 评分:{stock['score']:.3f} | 20日:{ret20:+.1f}% | 60日:{ret60:+.1f}% | 波动:{vol:.3f} | 资金:{mf:+.1f}\n"
    
    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**💼 模拟盘状态**

"""
    
    if portfolio:
        positions = portfolio.get('positions', {})
        pos_list = list(positions.items())
        report += f"• 持仓: {len(pos_list)}只\n"
        report += f"• 现金: ¥{portfolio.get('cash', 0):,.0f}\n"
        report += f"• 总市值: ¥{portfolio.get('total_value', 0):,.0f}\n"
        
        if pos_list:
            report += "\n**持仓明细**:\n"
            for code, pos in pos_list[:5]:
                report += f"• {code}: {pos.get('shares', 0)}股 @ ¥{pos.get('cost', 0):.2f}\n"
    else:
        report += "• 未初始化\n"
    
    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**💡 明日策略建议**

• 关注板块轮动方向
• 优选VQM评分>0.75的强势股
• 控制仓位在30-50%
• 关注资金净流入的板块

---
📅 日期: {market['date'] if market else '--'}
🧠 策略: v23多因子优化模型
🔧 系统: 豆奶投资策略
"""
    
    return report

def send_report(report):
    """发送报告"""
    try:
        # 使用subprocess调用openclaw message
        result = subprocess.run(
            ['openclaw', 'message', 'send', '--target', USER_ID, '--message', report],
            capture_output=True, text=True, timeout=30
        )
        print(f"发送结果: {result.returncode}")
        if result.stderr:
            print(f"错误: {result.stderr}")
        return True
    except Exception as e:
        print(f"发送失败: {e}")
        return False

def main():
    print("="*60)
    print("📊 生成每日收盘深度报告")
    print("="*60)
    
    report = generate_report()
    print("\n" + report)
    
    send_report(report)
    
    # 保存到文件
    today = datetime.now().strftime('%Y%m%d')
    report_path = f'/root/.openclaw/workspace/data/daily_report_{today}.md'
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\n✅ 报告已保存: {report_path}")

if __name__ == "__main__":
    main()
