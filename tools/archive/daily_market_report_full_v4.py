#!/root/.openclaw/workspace/venv/bin/python3
"""
A股收盘深度报告 - 完整版 v4 (长桥API优先)
使用venv环境运行，确保长桥SDK可用
API优先级: 长桥 > efinance > 腾讯
"""
import sys
import os

# 添加tools路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')

from datetime import datetime
import pandas as pd
import requests
import time
import subprocess
import json

# 导入长桥API
from longbridge_api import get_longbridge_api


def get_exa_news(queries, num_results=5):
    """使用Exa搜索新闻"""
    all_news = []
    for query in queries:
        try:
            result = subprocess.run(
                ['mcporter', 'call', f'exa.web_search_exa({{"query": "{query}", "numResults": {num_results}}})'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                output = result.stdout
                try:
                    json_start = output.find('{')
                    if json_start >= 0:
                        data = json.loads(output[json_start:])
                        results = data.get('results', [])
                        for r in results:
                            all_news.append({
                                'title': r.get('title', ''),
                                'text': r.get('text', '')[:200],
                                'url': r.get('url', '')
                            })
                except:
                    pass
            time.sleep(0.3)
        except Exception as e:
            log(f"Exa搜索失败 {query}: {e}")
    return all_news

REPORT_DIR = '/root/.openclaw/workspace/data'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_all_stocks_tushare():
    """从Tushare获取股票列表"""
    try:
        import tushare as ts
        ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
        pro = ts.pro_api()
        stocks = pro.stock_basic(exchange='', list_status='L')
        return stocks['ts_code'].tolist()
    except Exception as e:
        log(f"Tushare获取失败: {e}")
        return []

def get_longbridge_quotes_all(codes):
    """长桥API获取全市场行情 - 分批获取"""
    try:
        log(f"初始化长桥API...")
        api = get_longbridge_api()
        log(f"✅ 长桥API初始化成功")
        
        # 转换代码格式
        lb_codes = []
        for code in codes:
            if code.endswith('.SH'):
                lb_codes.append(f"{code[:-3]}.SH")
            elif code.endswith('.SZ'):
                lb_codes.append(f"{code[:-3]}.SZ")
            elif code.endswith('.BJ'):
                lb_codes.append(f"{code[:-3]}.BJ")
        
        log(f"准备获取 {len(lb_codes)} 只股票行情...")
        
        # 分批获取（每批100只）
        all_data = []
        batch_size = 100
        
        for i in range(0, len(lb_codes), batch_size):
            batch = lb_codes[i:i+batch_size]
            try:
                quotes = api.get_quotes(batch)
                for q in quotes:
                    all_data.append({
                        'ts_code': q['symbol'],
                        'name': '',  # 长桥不返回名称，后面用腾讯补
                        'close': q['price'],
                        'open': q['open'],
                        'high': q['high'],
                        'low': q['low'],
                        'pre_close': q['prev_close'],
                        'pct_chg': q['change'],
                        'volume': q['volume'],
                        'amount': q['turnover']
                    })
                
                if (i // batch_size) % 10 == 0:
                    log(f"  已获取 {len(all_data)}/{len(lb_codes)} 只...")
                
                time.sleep(0.1)  # 限速
            except Exception as e:
                log(f"  批次 {i//batch_size} 失败: {e}")
                continue
        
        if all_data:
            log(f"✅ 长桥API成功获取 {len(all_data)} 只股票")
            return pd.DataFrame(all_data)
    except Exception as e:
        log(f"长桥API失败: {e}")
    return None

def get_efinance_quotes():
    """efinance API - 备选"""
    try:
        import efinance as ef
        df = ef.stock.get_realtime_quotes()
        
        if df is not None and not df.empty:
            data = []
            for _, row in df.iterrows():
                try:
                    code = str(row.get('股票代码', ''))
                    if code.startswith('6'):
                        ts_code = code + '.SH'
                    elif code.startswith('0') or code.startswith('3'):
                        ts_code = code + '.SZ'
                    elif code.startswith('8') or code.startswith('4'):
                        ts_code = code + '.BJ'
                    else:
                        continue
                    
                    price = float(row.get('最新价', 0))
                    pre_close = float(row.get('昨日收盘价', 0))
                    
                    data.append({
                        'ts_code': ts_code,
                        'name': row.get('股票名称', ''),
                        'close': price,
                        'open': float(row.get('今日开盘价', 0)),
                        'high': float(row.get('最高', 0)),
                        'low': float(row.get('最低', 0)),
                        'pre_close': pre_close,
                        'pct_chg': ((price - pre_close) / pre_close * 100) if pre_close > 0 else float(row.get('涨跌幅', 0)),
                        'volume': float(row.get('成交量', 0)),
                        'amount': float(row.get('成交额', 0))
                    })
                except:
                    continue
            
            if data:
                return pd.DataFrame(data)
    except Exception as e:
        log(f"efinance失败: {e}")
    return None

def get_tencent_quotes(codes):
    """腾讯API - 备选"""
    all_data = []
    batch_size = 800
    
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        
        try:
            tencent_codes = []
            for code in batch:
                if code.endswith('.SH'):
                    tencent_codes.append(f"sh{code[:-3]}")
                elif code.endswith('.SZ'):
                    tencent_codes.append(f"sz{code[:-3]}")
                elif code.endswith('.BJ'):
                    tencent_codes.append(f"bj{code[:-3]}")
            
            url = f"https://qt.gtimg.cn/q={','.join(tencent_codes)}"
            r = requests.get(url, timeout=30)
            
            lines = r.text.strip().split(';')
            for line in lines:
                if not line.strip():
                    continue
                try:
                    parts = line.split('=')
                    if len(parts) < 2:
                        continue
                    
                    code_str = parts[0].split('_')[-1]
                    values = parts[1].strip('"').split('~')
                    
                    if len(values) < 45:
                        continue
                    
                    name = values[1]
                    price = float(values[3]) if values[3] else 0
                    pre_close = float(values[4]) if values[4] else 0
                    
                    if code_str.startswith('sh'):
                        ts_code = code_str.replace('sh', '') + '.SH'
                    elif code_str.startswith('sz'):
                        ts_code = code_str.replace('sz', '') + '.SZ'
                    elif code_str.startswith('bj'):
                        ts_code = code_str.replace('bj', '') + '.BJ'
                    else:
                        continue
                    
                    all_data.append({
                        'ts_code': ts_code,
                        'name': name,
                        'close': price,
                        'open': float(values[5]) if values[5] else 0,
                        'high': float(values[33]) if values[33] else 0,
                        'low': float(values[34]) if values[34] else 0,
                        'pre_close': pre_close,
                        'pct_chg': ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0,
                        'volume': float(values[6]) if values[6] else 0,
                        'amount': 0
                    })
                except:
                    continue
            
            time.sleep(0.2)
        except:
            continue
    
    if all_data:
        return pd.DataFrame(all_data)
    return None

def get_market_data():
    """获取市场数据 - 按优先级"""
    codes = get_all_stocks_tushare()
    if not codes:
        log("❌ 无法获取股票列表")
        return None, None
    
    log(f"股票列表: {len(codes)}只")
    
    # 1. 首选长桥
    log("="*50)
    log("尝试长桥API...")
    df = get_longbridge_quotes_all(codes)
    if df is not None and not df.empty and len(df) > 1000:
        # 补充股票名称（用腾讯）
        log("补充股票名称...")
        names_df = get_tencent_quotes(df['ts_code'].tolist())
        if names_df is not None and not names_df.empty:
            name_map = dict(zip(names_df['ts_code'], names_df['name']))
            df['name'] = df['ts_code'].map(name_map)
        return df, '长桥API'
    
    # 2. 备选efinance
    log("="*50)
    log("长桥失败，尝试efinance...")
    df = get_efinance_quotes()
    if df is not None and not df.empty and len(df) > 1000:
        return df, 'efinance'
    
    # 3. 备选腾讯
    log("="*50)
    log("efinance失败，尝试腾讯API...")
    df = get_tencent_quotes(codes)
    if df is not None and not df.empty:
        return df, '腾讯API'
    
    log("❌ 所有API都失败")
    return None, None

def get_index_data():
    """获取指数数据"""
    indices = ['sh000001', 'sz399001', 'sz399006', 'sh000300']
    index_names = {
        'sh000001': '上证指数',
        'sz399001': '深证成指',
        'sz399006': '创业板指',
        'sh000300': '沪深300'
    }
    
    try:
        url = f"https://qt.gtimg.cn/q={','.join(indices)}"
        r = requests.get(url, timeout=10)
        
        data = {}
        lines = r.text.strip().split(';')
        for line in lines:
            if not line.strip():
                continue
            try:
                parts = line.split('=')
                if len(parts) < 2:
                    continue
                
                code_str = parts[0].split('_')[-1]
                values = parts[1].strip('"').split('~')
                
                if len(values) < 45:
                    continue
                
                name = index_names.get(code_str, code_str)
                price = float(values[3]) if values[3] else 0
                pre_close = float(values[4]) if values[4] else 0
                pct_chg = ((price - pre_close) / pre_close * 100) if pre_close > 0 else 0
                
                data[code_str] = {
                    'name': name,
                    'price': price,
                    'pct_chg': pct_chg
                }
            except:
                continue
        
        return data
    except:
        return {}

def analyze_sectors(df):
    """板块分析"""
    # 定义板块（根据股票代码前缀）
    sectors = {
        'AI算力': ['688256', '688041', '300474', '688525', '688297'],
        '半导体': ['688012', '688072', '688120', '688981', '688396'],
        '光通讯': ['300308', '300502', '300394', '002281', '000988'],
        '新能源': ['300750', '002594', '601012', '600438', '002460'],
        '消费电子': ['002475', '300433', '000725', '601138', '300136'],
        '金融科技': ['300059', '600030', '601688', '300033', '601211'],
        '医药生物': ['600276', '300760', '603259', '600196', '000538'],
        '白酒': ['600519', '000858', '000568', '002304', '000596'],
        '银行': ['600036', '000001', '601398', '601288', '601939'],
        '券商': ['300059', '600030', '601688', '600999', '600837'],
    }
    
    def get_sector(ts_code):
        code = ts_code.split('.')[0]
        for sector, codes in sectors.items():
            if code in codes:
                return sector
        if code.startswith('688'):
            return '科创板'
        elif code.startswith('300'):
            return '创业板'
        elif code.startswith('8') or code.startswith('4'):
            return '北交所'
        else:
            return '主板'
    
    df['sector'] = df['ts_code'].apply(get_sector)
    
    sector_perf = df.groupby('sector').agg({
        'pct_chg': 'mean',
        'ts_code': 'count'
    }).rename(columns={'ts_code': 'count'}).sort_values('pct_chg', ascending=False)
    
    return sector_perf

def format_money(val):
    """格式化金额"""
    if val >= 1e12:
        return f"{val/1e12:.2f}万亿"
    elif val >= 1e8:
        return f"{val/1e8:.0f}亿"
    elif val >= 1e4:
        return f"{val/1e4:.0f}万"
    else:
        return f"{val:.0f}"

def generate_report():
    """生成完整收盘报告"""
    log("="*60)
    log("A股收盘深度报告 - 完整版 v4 (长桥API)")
    log("="*60)
    
    today = datetime.now().strftime('%Y%m%d')
    log(f"报告日期: {today}")
    
    # 获取市场数据
    df, api_source = get_market_data()
    
    if df is None or df.empty:
        log("❌ 无法获取市场数据")
        return None
    
    log(f"✅ 数据来源: {api_source}, 共{len(df)}只股票")
    
    # 市场统计
    total = len(df)
    up = len(df[df['pct_chg'] > 0])
    down = len(df[df['pct_chg'] < 0])
    flat = len(df[df['pct_chg'] == 0])
    avg_change = df['pct_chg'].mean()
    limit_up = len(df[df['pct_chg'] >= 9.5])
    limit_down = len(df[df['pct_chg'] <= -9.5])
    total_amount = df['amount'].sum() if 'amount' in df.columns else 0
    
    # 指数数据
    index_data = get_index_data()
    
    # 板块分析
    sector_perf = analyze_sectors(df)
    
    # Exa新闻搜索
    log("Exa搜索新闻...")
    news_queries = [
        "A股今日行情",
        "AI算力 芯片 最新消息",
        "存储芯片 涨价",
        "半导体 国产替代",
        "光通讯 订单"
    ]
    news_list = get_exa_news(news_queries, 3)
    log(f"✅ 获取 {len(news_list)} 条新闻")
    
    # 涨跌幅榜
    top_up = df.nlargest(15, 'pct_chg')[['name', 'ts_code', 'pct_chg', 'close']]
    top_down = df.nsmallest(15, 'pct_chg')[['name', 'ts_code', 'pct_chg', 'close']]
    
    # 生成报告
    report = f"""{'='*70}
📊 A股每日收盘深度报告 ({today})
数据来源: {api_source} | 统计股票: {total}只
{'='*70}

【一、主要指数表现】
"""
    
    for code, data in index_data.items():
        emoji = "🔴" if data['pct_chg'] > 0 else "🟢" if data['pct_chg'] < 0 else "⚪"
        report += f"{emoji} {data['name']}: {data['price']:.2f} ({data['pct_chg']:+.2f}%)\n"
    
    report += f"""
【二、市场全景】
┌─────────────────────────────────────────────────────────────────────┐
│ 涨跌分布: 🔴 {up:5}只上涨 | 🟢 {down:5}只下跌 | ⚪ {flat:5}只平盘        │
│ 平均涨跌幅: {avg_change:+.2f}%                                              │
│ 涨停: {limit_up:3}只 | 跌停: {limit_down:3}只                                          │
│ 两市成交额: {format_money(total_amount)}                                        │
└─────────────────────────────────────────────────────────────────────┘

【三、板块强弱排序】
"""
    
    for i, (sector, row) in enumerate(sector_perf.iterrows(), 1):
        emoji = "🔴" if row['pct_chg'] > 0 else "🟢" if row['pct_chg'] < 0 else "⚪"
        report += f"{i:2}. {emoji} {sector:10s}: {row['pct_chg']:+6.2f}% ({int(row['count'])}只)\n"
    
    report += f"""
【四、热点新闻】(Exa搜索)
"""
    if news_list:
        for i, news in enumerate(news_list[:10], 1):
            title = news.get('title', '')
            if title:
                report += f"{i}. {title[:60]}...\n"
    else:
        report += "• 暂无相关新闻数据\n"
    
    report += f"""
【五、涨幅榜 TOP15】
"""
    for i, (_, row) in enumerate(top_up.iterrows(), 1):
        name = row['name'] if pd.notna(row['name']) else '未知'
        report += f"{i:2}. {name[:8]:8s} ({row['ts_code'][:6]}): {row['close']:8.2f}  +{row['pct_chg']:6.2f}%\n"
    
    report += f"""
【六、跌幅榜 TOP15】
"""
    for i, (_, row) in enumerate(top_down.iterrows(), 1):
        name = row['name'] if pd.notna(row['name']) else '未知'
        report += f"{i:2}. {name[:8]:8s} ({row['ts_code'][:6]}): {row['close']:8.2f}  {row['pct_chg']:6.2f}%\n"
    
    trend = "震荡调整" if abs(avg_change) < 0.5 else ("上涨" if avg_change > 0 else "下跌")
    report += f"""
【七、市场展望与总结】

📈 今日市场呈{trend}态势，主要指数{'全线飘红' if avg_change > 0 else '多数收跌'}。

🔍 核心观察:
• 上涨家数: {up}只 ({up/total*100:.1f}%)
• 下跌家数: {down}只 ({down/total*100:.1f}%)
• 涨跌停比: {limit_up}:{limit_down} ({'情绪积极' if limit_up > limit_down*2 else '情绪中性' if limit_up > limit_down else '情绪谨慎'})

💡 明日关注点:
• 成交量变化（今日{format_money(total_amount)}）
• 北向资金流向
• 外盘表现（美股/港股）

⚠️ 风险提示:
• 注意高位股回调风险
• 关注政策面变化
• 控制仓位，注意波动

{'='*70}
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}
"""
    
    filename = f"{REPORT_DIR}/daily_report_full_{today}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"✅ 完整报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_report()
