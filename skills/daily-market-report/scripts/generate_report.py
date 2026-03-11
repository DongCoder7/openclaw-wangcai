#!/root/.openclaw/workspace/venv/bin/python3
"""
A股收盘深度报告 - 标准模板 v6
包含: 外围市场、A股行情、资金流向、龙虎榜、Exa新闻、操作建议
API: 长桥 > efinance > 腾讯

使用方式:
    ./venv_runner.sh tools/daily_market_report_template_v6.py
    
输出: data/daily_report_YYYYMMDD.md
"""
import sys
import os
sys.path.insert(0, '/root/.openclaw/workspace/tools')

from datetime import datetime
import pandas as pd
import requests
import json
import subprocess
import time

from longbridge_api import get_longbridge_api

REPORT_DIR = '/root/.openclaw/workspace/data'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_kline_data_tencent(symbol, days=60):
    """获取K线数据 - 使用Tushare Pro"""
    try:
        import tushare as ts
        
        # 转换代码格式
        if symbol.startswith('sh'):
            ts_code = f"{symbol[2:]}.SH"
        elif symbol.startswith('sz'):
            ts_code = f"{symbol[2:]}.SZ"
        else:
            ts_code = symbol
        
        ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
        pro = ts.pro_api()
        
        # 获取日线数据
        end_date = datetime.now().strftime('%Y%m%d')
        df = pro.index_daily(ts_code=ts_code, end_date=end_date, limit=days)
        
        if df is not None and not df.empty and len(df) >= 20:
            df = df.sort_values('trade_date')
            df['date'] = pd.to_datetime(df['trade_date'])
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['vol'].astype(float)
            return df[['date', 'open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)
        else:
            # 如果指数接口没有数据，尝试使用个股接口
            df = pro.daily(ts_code=ts_code, end_date=end_date, limit=days)
            if df is not None and not df.empty and len(df) >= 20:
                df = df.sort_values('trade_date')
                df['date'] = pd.to_datetime(df['trade_date'])
                df['open'] = df['open'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['close'] = df['close'].astype(float)
                df['volume'] = df['vol'].astype(float)
                return df[['date', 'open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)
    except Exception as e:
        log(f"Tushare获取失败 {symbol}: {e}")
    return None

def get_kline_data_eastmoney(symbol, days=60):
    """从东方财富获取K线数据"""
    try:
        # 转换代码格式
        if symbol.startswith('sh'):
            secid = f"1.{symbol[2:]}"
        elif symbol.startswith('sz'):
            secid = f"0.{symbol[2:]}"
        else:
            secid = symbol
        
        url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&end=20500101&limit={days}"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if data.get('data') and data['data'].get('klines'):
            klines = data['data']['klines']
            rows = []
            for k in klines:
                parts = k.split(',')
                if len(parts) >= 6:
                    rows.append({
                        'date': parts[0],
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'high': float(parts[3]),
                        'low': float(parts[4]),
                        'volume': float(parts[5])
                    })
            df = pd.DataFrame(rows)
            df['date'] = pd.to_datetime(df['date'])
            return df
    except Exception as e:
        log(f"东方财富K线获取失败 {symbol}: {e}")
    return None

def calculate_ma(df, periods=[5, 10, 20, 60]):
    """计算移动平均线"""
    for p in periods:
        df[f'MA{p}'] = df['close'].rolling(window=p).mean()
    return df

def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['MACD_DIF'] = ema_fast - ema_slow
    df['MACD_DEA'] = df['MACD_DIF'].ewm(span=signal, adjust=False).mean()
    df['MACD_BAR'] = (df['MACD_DIF'] - df['MACD_DEA']) * 2
    return df

def calculate_rsi(df, period=14):
    """计算RSI指标"""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_bollinger(df, period=20, std_dev=2):
    """计算布林带"""
    df['BOLL_MID'] = df['close'].rolling(window=period).mean()
    df['BOLL_STD'] = df['close'].rolling(window=period).std()
    df['BOLL_UP'] = df['BOLL_MID'] + (df['BOLL_STD'] * std_dev)
    df['BOLL_DOWN'] = df['BOLL_MID'] - (df['BOLL_STD'] * std_dev)
    return df

def analyze_technical(df, symbol_name):
    """技术面综合分析"""
    if df is None or len(df) < 30:
        return None
    
    # 计算指标
    df = calculate_ma(df)
    df = calculate_macd(df)
    df = calculate_rsi(df)
    df = calculate_bollinger(df)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    analysis = {
        'symbol': symbol_name,
        'price': latest['close'],
        'change_pct': (latest['close'] - prev['close']) / prev['close'] * 100 if prev['close'] != 0 else 0,
        'ma_trend': '',
        'macd_signal': '',
        'rsi_status': '',
        'boll_position': '',
        'support_resist': {},
        'overall': ''
    }
    
    # 1. 均线趋势分析
    ma5, ma10, ma20, ma60 = latest.get('MA5', 0), latest.get('MA10', 0), latest.get('MA20', 0), latest.get('MA60', 0)
    if ma5 > ma10 > ma20:
        analysis['ma_trend'] = '多头排列📈'
    elif ma5 < ma10 < ma20:
        analysis['ma_trend'] = '空头排列📉'
    elif ma5 > ma10 and ma5 > ma20:
        analysis['ma_trend'] = '短期走强'
    else:
        analysis['ma_trend'] = '震荡整理'
    
    # 2. MACD分析
    dif, dea, bar = latest.get('MACD_DIF', 0), latest.get('MACD_DEA', 0), latest.get('MACD_BAR', 0)
    prev_bar = prev.get('MACD_BAR', 0)
    
    if dif > dea and prev['MACD_DIF'] <= prev['MACD_DEA']:
        analysis['macd_signal'] = '金叉买入✅'
    elif dif < dea and prev['MACD_DIF'] >= prev['MACD_DEA']:
        analysis['macd_signal'] = '死叉卖出❌'
    elif bar > 0 and bar > prev_bar:
        analysis['macd_signal'] = '红柱放大📈'
    elif bar > 0 and bar < prev_bar:
        analysis['macd_signal'] = '红柱缩小⚠️'
    elif bar < 0 and bar < prev_bar:
        analysis['macd_signal'] = '绿柱放大📉'
    else:
        analysis['macd_signal'] = '绿柱缩小🔄'
    
    # 3. RSI分析
    rsi = latest.get('RSI', 50)
    if rsi > 80:
        analysis['rsi_status'] = f'严重超买({rsi:.1f})🔴'
    elif rsi > 70:
        analysis['rsi_status'] = f'超买({rsi:.1f})🟠'
    elif rsi < 20:
        analysis['rsi_status'] = f'严重超卖({rsi:.1f})🟢'
    elif rsi < 30:
        analysis['rsi_status'] = f'超卖({rsi:.1f})🟢'
    else:
        analysis['rsi_status'] = f'正常({rsi:.1f})⚪'
    
    # 4. 布林带位置
    close = latest['close']
    boll_up = latest.get('BOLL_UP', close * 1.05)
    boll_mid = latest.get('BOLL_MID', close)
    boll_down = latest.get('BOLL_DOWN', close * 0.95)
    if close > boll_up:
        analysis['boll_position'] = '突破上轨⚠️'
    elif close > boll_mid:
        analysis['boll_position'] = '中上区间'
    elif close > boll_down:
        analysis['boll_position'] = '中下区间'
    else:
        analysis['boll_position'] = '跌破下轨🔥'
    
    # 5. 支撑阻力位
    recent_highs = df['high'].tail(20).nlargest(3).values
    recent_lows = df['low'].tail(20).nsmallest(3).values
    analysis['support_resist'] = {
        'resistance1': recent_highs[0] if len(recent_highs) > 0 else close * 1.05,
        'resistance2': recent_highs[1] if len(recent_highs) > 1 else close * 1.08,
        'support1': recent_lows[0] if len(recent_lows) > 0 else close * 0.95,
        'support2': recent_lows[1] if len(recent_lows) > 1 else close * 0.92
    }
    
    # 6. 综合判断
    bullish_signals = sum([
        '多头' in analysis['ma_trend'] or '走强' in analysis['ma_trend'],
        '金叉' in analysis['macd_signal'] or '红柱放大' in analysis['macd_signal'],
        '超卖' in analysis['rsi_status'],
        '下轨' in analysis['boll_position']
    ])
    bearish_signals = sum([
        '空头' in analysis['ma_trend'],
        '死叉' in analysis['macd_signal'],
        '超买' in analysis['rsi_status'],
        '上轨' in analysis['boll_position']
    ])
    
    if bullish_signals >= 3:
        analysis['overall'] = '强烈看多🚀'
    elif bullish_signals >= 2:
        analysis['overall'] = '偏多📈'
    elif bearish_signals >= 3:
        analysis['overall'] = '强烈看空📉'
    elif bearish_signals >= 2:
        analysis['overall'] = '偏空'
    else:
        analysis['overall'] = '震荡观望➡️'
    
    return analysis

def get_kline_data_eastmoney_index(symbol, days=60):
    """从东方财富获取指数K线数据 - 与腾讯API数据同源"""
    try:
        # 转换代码格式为东方财富格式
        if symbol.startswith('sh'):
            secid = f"1.{symbol[2:]}"
        elif symbol.startswith('sz'):
            secid = f"0.{symbol[2:]}"
        else:
            secid = symbol
        
        url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=0&end=20500101&limit={days}"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if data.get('data') and data['data'].get('klines'):
            klines = data['data']['klines']
            rows = []
            for k in klines:
                parts = k.split(',')
                if len(parts) >= 6:
                    rows.append({
                        'date': parts[0],
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'high': float(parts[3]),
                        'low': float(parts[4]),
                        'volume': float(parts[5])
                    })
            df = pd.DataFrame(rows)
            df['date'] = pd.to_datetime(df['date'])
            return df
    except Exception as e:
        log(f"东方财富指数K线获取失败 {symbol}: {e}")
    return None

def get_technical_analysis_summary(indices_realtime=None):
    """获取主要指数的技术面分析汇总 - 使用东方财富数据与腾讯API同源"""
    log("计算技术指标...")
    indices_to_analyze = [
        ('sh000001', '上证指数'),
        ('sz399001', '深证成指'),
        ('sz399006', '创业板指'),
        ('sh000688', '科创50')
    ]
    
    results = []
    for code, name in indices_to_analyze:
        # 优先使用东方财富数据（与腾讯API同源）
        df = get_kline_data_eastmoney_index(code, days=60)
        if df is not None:
            analysis = analyze_technical(df, name)
            if analysis:
                # 如果有实时数据，覆盖价格信息确保一致性
                if indices_realtime and code in indices_realtime:
                    realtime = indices_realtime[code]
                    analysis['price'] = realtime['price']
                    analysis['change_pct'] = realtime['change_pct']
                results.append(analysis)
        time.sleep(0.1)
    
    return results

def get_index_market():
    """获取官方指数行情（腾讯API）- 市值加权，市场基准"""
    try:
        url = 'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688,sh000016,sh000905'
        r = requests.get(url, timeout=10)
        indices = {}
        name_map = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指',
            'sh000688': '科创50',
            'sh000016': '上证50',
            'sh000905': '中证500'
        }
        for line in r.text.strip().split(';'):
            if not line.strip():
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            code = parts[0].split('_')[-1]
            values = parts[1].strip('"').split('~')
            if len(values) > 32:
                name = name_map.get(code, code)
                price = float(values[3])
                change_pct = float(values[32])
                change = float(values[31]) if len(values) > 31 else 0
                indices[code] = {
                    'name': name,
                    'price': price,
                    'change': change,
                    'change_pct': change_pct
                }
        return indices
    except Exception as e:
        log(f"获取指数失败: {e}")
    return {}

def get_exa_news(queries, num_results=5):
    """使用Exa搜索新闻 - 解析mcporter文本输出"""
    all_news = []
    for query in queries:
        try:
            result = subprocess.run(
                ['mcporter', 'call', f'exa.web_search_exa({{"query": "{query}", "numResults": {num_results}}})'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                output = result.stdout
                # 解析文本格式输出
                lines = output.split('\n')
                current_news = {}
                for line in lines:
                    line = line.strip()
                    if line.startswith('Title:'):
                        if current_news.get('title'):
                            all_news.append(current_news)
                            current_news = {}
                        current_news['title'] = line.replace('Title:', '').strip()[:70]
                    elif line.startswith('Text:'):
                        current_news['text'] = line.replace('Text:', '').strip()[:150]
                    elif line.startswith('URL:'):
                        current_news['url'] = line.replace('URL:', '').strip()
                # 添加最后一个
                if current_news.get('title'):
                    all_news.append(current_news)
            time.sleep(0.3)
        except Exception as e:
            log(f"Exa搜索失败 {query}: {e}")
    return all_news

def get_us_stock_market():
    """获取美股行情"""
    try:
        url = 'https://qt.gtimg.cn/q=usDJI,usIXIC,usINX'
        r = requests.get(url, timeout=10)
        data = {}
        for line in r.text.strip().split(';'):
            if not line.strip():
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            code = parts[0].split('_')[-1]
            values = parts[1].strip('"').split('~')
            if len(values) > 30:
                name_map = {'usDJI': '道琼斯', 'usIXIC': '纳斯达克', 'usINX': '标普500'}
                name = name_map.get(code, code)
                price = float(values[3])
                pre_close = float(values[4])
                if pre_close > 0:
                    change_pct = (price - pre_close) / pre_close * 100
                    change = price - pre_close
                else:
                    change_pct = 0
                    change = 0
                data[code] = {'name': name, 'price': price, 'change': change, 'change_pct': change_pct}
        return data
    except Exception as e:
        log(f"获取美股失败: {e}")
    return {}

def get_hk_stock_market():
    """获取港股行情"""
    try:
        url = 'https://qt.gtimg.cn/q=hkHSI,hkHSTECH'
        r = requests.get(url, timeout=10)
        data = {}
        for line in r.text.strip().split(';'):
            if not line.strip():
                continue
            parts = line.split('=')
            if len(parts) < 2:
                continue
            values = parts[1].strip('"').split('~')
            if len(values) > 30:
                name = values[1]
                price = float(values[3])
                pre_close = float(values[4])
                if pre_close > 0:
                    change_pct = (price - pre_close) / pre_close * 100
                    change = price - pre_close
                else:
                    change_pct = 0
                    change = 0
                data[name] = {'price': price, 'change': change, 'change_pct': change_pct}
        return data
    except Exception as e:
        log(f"获取港股失败: {e}")
    return {}

def get_longhu_data():
    """获取龙虎榜数据"""
    try:
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        longhu = ak.stock_lhb_detail_em(start_date=today, end_date=today)
        if longhu is not None and not longhu.empty:
            return longhu
    except Exception as e:
        log(f"获取龙虎榜失败: {e}")
    return None

def get_a_stock_market():
    """获取A股行情（长桥API）"""
    try:
        import tushare as ts
        ts.set_token('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
        pro = ts.pro_api()
        stocks = pro.stock_basic(exchange='', list_status='L')
        codes = stocks['ts_code'].tolist()
        
        log(f"长桥API获取 {len(codes)} 只股票...")
        api = get_longbridge_api()
        
        lb_codes = []
        for code in codes:
            if code.endswith('.SH'):
                lb_codes.append(f"{code[:-3]}.SH")
            elif code.endswith('.SZ'):
                lb_codes.append(f"{code[:-3]}.SZ")
            elif code.endswith('.BJ'):
                lb_codes.append(f"{code[:-3]}.BJ")
        
        all_data = []
        batch_size = 100
        for i in range(0, len(lb_codes), batch_size):
            batch = lb_codes[i:i+batch_size]
            try:
                quotes = api.get_quotes(batch)
                for q in quotes:
                    all_data.append({
                        'ts_code': q['symbol'],
                        'close': q['price'],
                        'pct_chg': q['change'],
                        'volume': q['volume'],
                        'amount': q['turnover']
                    })
                time.sleep(0.05)
            except:
                continue
        
        return pd.DataFrame(all_data)
    except Exception as e:
        log(f"获取A股失败: {e}")
    return None

def generate_report():
    """生成标准深度报告"""
    log("="*60)
    log("A股收盘深度报告 - 标准模板 v6")
    log("="*60)
    
    today = datetime.now().strftime('%Y%m%d')
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 1. 外围市场
    log("获取外围市场数据...")
    us_market = get_us_stock_market()
    hk_market = get_hk_stock_market()
    
    # 2. A股数据
    log("获取A股行情...")
    df = get_a_stock_market()
    if df is None or df.empty:
        log("❌ A股数据获取失败")
        return None
    
    # 2.5 获取官方指数（市值加权）
    log("获取官方指数...")
    indices = get_index_market()
    
    # 2.6 获取技术面分析 - 传入实时指数数据确保一致性
    log("计算技术指标...")
    tech_analysis = get_technical_analysis_summary(indices)
    
    total = len(df)
    up = len(df[df['pct_chg'] > 0])
    down = len(df[df['pct_chg'] < 0])
    avg_change = df['pct_chg'].mean()
    limit_up = len(df[df['pct_chg'] >= 9.5])
    limit_down = len(df[df['pct_chg'] <= -9.5])
    total_amount = df['amount'].sum()
    
    # 3. Exa新闻
    log("Exa搜索新闻...")
    news_queries = [
        "A股今日行情",
        "美股最新走势",
        "中东局势 美伊以冲突",
        "AI算力 芯片 最新消息",
        "龙虎榜 机构席位"
    ]
    news_list = get_exa_news(news_queries, 3)
    
    # 4. 龙虎榜
    log("获取龙虎榜...")
    longhu = get_longhu_data()
    
    # 5. 板块分析 - 修复分类逻辑
    def classify_sector(ts_code):
        """根据股票代码分类板块 - 修复版"""
        # 提取数字部分（去掉.SZ/.SH/.BJ后缀）
        code = ts_code.split('.')[0] if '.' in ts_code else ts_code
        
        if code.startswith('688'):  # 科创板: 688XXX
            return '科创板'
        elif code.startswith('3'):  # 创业板: 300XXX, 301XXX
            return '创业板'
        elif code.startswith('8') or code.startswith('4'):  # 北交所
            return '北交所'
        elif code.startswith('6') or code.startswith('0') or code.startswith('1'):  # 主板
            return '主板'
        else:
            return '其他'
    
    df['sector'] = df['ts_code'].apply(classify_sector)
    sector_perf = df.groupby('sector')['pct_chg'].mean().sort_values(ascending=False)
    
    # 板块详细统计
    sector_stats = df.groupby('sector').agg({
        'pct_chg': ['mean', 'count', 'sum'],
        'amount': 'sum'
    }).round(2)
    sector_stats.columns = ['avg_change', 'count', 'total_change', 'total_amount']
    
    # 涨跌幅榜
    top_up = df.nlargest(10, 'pct_chg')
    top_down = df.nsmallest(10, 'pct_chg')
    
    # 领涨板块个股分析
    def analyze_sector_leaders(df, sector_name, top_n=3):
        """分析某板块的领涨股"""
        sector_df = df[df['sector'] == sector_name]
        if len(sector_df) == 0:
            return []
        return sector_df.nlargest(top_n, 'pct_chg')[['ts_code', 'close', 'pct_chg', 'amount']]
    
    # 生成深度报告
    report = f"""{'='*70}
📊 A股收盘深度报告 ({today})
数据来源: 长桥API + Exa搜索 + Akshare | 统计: {total}只
{'='*70}

【一、外围市场环境】

🇺🇸 美股隔夜行情:
"""
    
    for code, data in us_market.items():
        emoji = "🔴" if data['change'] > 0 else "🟢"
        report += f"{emoji} {data['name']}: {data['price']:.2f} ({data['change']:+.2f}, {data['change_pct']:+.2f}%)\n"
    
    report += f"""
🇭🇰 港股收盘:
"""
    for name, data in hk_market.items():
        emoji = "🔴" if data['change'] > 0 else "🟢"
        report += f"{emoji} {name}: {data['price']:.2f} ({data['change']:+.2f}, {data['change_pct']:+.2f}%)\n"
    
    # 添加官方指数板块
    report += f"""
【二、A股官方指数】(市值加权 - 市场基准)
"""
    if indices:
        for code in ['sh000001', 'sh000016', 'sz399001', 'sz399006', 'sh000688', 'sh000905']:
            if code in indices:
                d = indices[code]
                emoji = "🔴" if d['change_pct'] > 0 else "🟢"
                report += f"{emoji} {d['name']}: {d['price']:.2f} ({d['change']:+.2f}, {d['change_pct']:+.2f}%)\n"
    
    report += f"""
【三、技术面深度分析】(基于K线形态与技术指标)
"""
    
    if tech_analysis:
        # 生成技术面汇总表
        report += """
┌─────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ 指数/板块   │ 均线趋势 │ MACD信号 │ RSI状态  │ 布林位置 │ 综合判断 │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
"""
        for ta in tech_analysis:
            report += f"│ {ta['symbol']:<10} │ {ta['ma_trend']:<8} │ {ta['macd_signal']:<8} │ {ta['rsi_status']:<8} │ {ta['boll_position']:<8} │ {ta['overall']:<8} │\n"
        report += "└─────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘\n"
        
        # 详细分析
        report += "\n📊 详细技术诊断:\n"
        for ta in tech_analysis:
            report += f"\n【{ta['symbol']}】当前{ta['price']:.2f} ({ta['change_pct']:+.2f}%)\n"
            report += f"  • 均线系统: {ta['ma_trend']}\n"
            report += f"  • MACD: {ta['macd_signal']}\n"
            report += f"  • RSI: {ta['rsi_status']}\n"
            report += f"  • 布林带: {ta['boll_position']}\n"
            sr = ta['support_resist']
            report += f"  • 支撑位: {sr['support1']:.2f} / {sr['support2']:.2f}\n"
            report += f"  • 阻力位: {sr['resistance1']:.2f} / {sr['resistance2']:.2f}\n"
            report += f"  💡 综合判断: {ta['overall']}\n"
        
        # 技术面总结
        bullish_count = sum(1 for ta in tech_analysis if '看多' in ta['overall'] or '偏多' in ta['overall'])
        bearish_count = sum(1 for ta in tech_analysis if '看空' in ta['overall'] or '偏空' in ta['overall'])
        
        report += f"""
📈 技术面总结:
• 看多信号: {bullish_count}个指数 | 看空信号: {bearish_count}个指数
• 建议策略: {'逢低做多' if bullish_count > bearish_count else '逢高减仓' if bearish_count > bullish_count else '震荡观望'}
"""
    else:
        report += "\n(技术指标计算失败)\n"
    
    report += f"""
【四、A股市场全景与板块统计】

┌─────────────────────────────────────────────────────────────────────┐
│ 涨跌分布: 🔴 {up:5}只上涨 | 🟢 {down:5}只下跌                              │
│ 全市场平均涨跌幅: {avg_change:+.2f}% (等权平均，非市值加权)                    │
│ 涨停: {limit_up:3}只 | 跌停: {limit_down:3}只                                   │
│ 两市成交额: {total_amount/1e8:.0f}亿                                        │
└─────────────────────────────────────────────────────────────────────┘

【四、板块深度分析】(等权平均 - 反映板块内部强度)
"""
    
    # 板块详细表现
    for sector in sector_perf.index:
        pct = sector_perf[sector]
        stats = sector_stats.loc[sector]
        emoji = "🔴" if pct > 0 else "🟢"
        
        report += f"""
{emoji} {sector} ( avg: {pct:+6.2f}% | 股票数: {int(stats['count'])} | 成交额: {stats['total_amount']/1e8:.0f}亿 )
"""
        # 该板块领涨股
        leaders = analyze_sector_leaders(df, sector, 3)
        if not leaders.empty:
            report += f"  领涨: "
            for _, row in leaders.iterrows():
                code_short = row['ts_code'].split('.')[0]
                report += f"{code_short}({row['pct_chg']:+.1f}%) "
            report += "\n"
    
    # 新闻与板块关联分析
    report += f"""
【五、热点新闻与驱动因子分析】(Exa搜索)
"""
    
    # 分类新闻
    geopolitical_news = [n for n in news_list if any(k in n.get('title','') for k in ['伊朗','中东','战争','美以','冲突'])]
    ai_news = [n for n in news_list if any(k in n.get('title','') for k in ['AI','芯片','英伟达','人工智能','算力'])]
    market_news = [n for n in news_list if any(k in n.get('title','') for k in ['A股','行情','股市','指数'])]
    
    if geopolitical_news:
        report += f"""
🌍 地缘政治风险（影响原油、黄金、军工板块）:
"""
        for news in geopolitical_news[:3]:
            report += f"• {news.get('title', '')[:55]}...\n"
    
    if ai_news:
        report += f"""
🤖 AI/科技催化（影响科创板、创业板科技股）:
"""
        for news in ai_news[:3]:
            report += f"• {news.get('title', '')[:55]}...\n"
    
    if market_news:
        report += f"""
📈 市场整体动态:
"""
        for news in market_news[:3]:
            report += f"• {news.get('title', '')[:55]}...\n"
    
    # 关联分析
    report += f"""
💡 新闻-板块关联解读:
"""
    # 分析领涨板块与新闻的关联
    top_sector = sector_perf.index[0] if len(sector_perf) > 0 else ''
    top_sector_change = sector_perf.iloc[0] if len(sector_perf) > 0 else 0
    
    if top_sector == '创业板' and ai_news:
        report += f"• 创业板领涨(+{top_sector_change:.2f}%)与AI/芯片利好消息高度相关\n"
    if top_sector == '科创板' and ai_news:
        report += f"• 科创板领涨(+{top_sector_change:.2f}%)受半导体产业催化\n"
    if geopolitical_news and '主板' in sector_perf.index:
        report += f"• 中东局势紧张，关注原油、黄金、军工板块轮动机会\n"
    
    report += f"• 今日{limit_up}只涨停，市场情绪{'积极' if limit_up > 30 else '中性' if limit_up > 10 else '谨慎'}\n"
    
    if longhu is not None and not longhu.empty:
        report += f"""
【六、龙虎榜与资金流向】

机构净买入TOP5:
"""
        longhu_buy = longhu[longhu['龙虎榜净买额'] > 0].sort_values('龙虎榜净买额', ascending=False)
        for i, (_, row) in enumerate(longhu_buy.head(5).iterrows(), 1):
            report += f"{i}. {row['名称']}({row['代码']}): 净买{row['龙虎榜净买额']/1e8:.2f}亿, 涨{row['涨跌幅']:.2f}%\n"
        
        report += f"""
机构净卖出TOP5:
"""
        longhu_sell = longhu[longhu['龙虎榜净买额'] < 0].sort_values('龙虎榜净买额')
        for i, (_, row) in enumerate(longhu_sell.head(5).iterrows(), 1):
            report += f"{i}. {row['名称']}({row['代码']}): 净卖{row['龙虎榜净买额']/1e8:.2f}亿, 涨{row['涨跌幅']:.2f}%\n"
    
    report += f"""
【七、个股深度分析】

🔥 涨幅榜 TOP10 (结合板块与驱动):
"""
    for i, (_, row) in enumerate(top_up.iterrows(), 1):
        code_short = row['ts_code'].split('.')[0]
        sector = row.get('sector', '未知')
        report += f"{i:2}. {code_short}({sector}): {row['close']:8.2f} +{row['pct_chg']:6.2f}%  成交{row['amount']/1e8:.1f}亿\n"
    
    report += f"""
❄️ 跌幅榜 TOP10:
"""
    for i, (_, row) in enumerate(top_down.iterrows(), 1):
        code_short = row['ts_code'].split('.')[0]
        sector = row.get('sector', '未知')
        report += f"{i:2}. {code_short}({sector}): {row['close']:8.2f} {row['pct_chg']:6.2f}%  成交{row['amount']/1e8:.1f}亿\n"
    
    # 明日展望 - 更深度
    trend = "上涨" if avg_change > 0.5 else "下跌" if avg_change < -0.5 else "震荡"
    sentiment = "积极" if limit_up > limit_down * 1.5 else "中性" if limit_up > limit_down else "谨慎"
    
    # 根据新闻调整策略
    risk_factor = ""
    if geopolitical_news:
        risk_factor += "中东局势不确定性增加，"
    if ai_news:
        risk_factor += "AI主线延续强势，"
    
    report += f"""
【八、明日展望与深度策略】

📊 **市场诊断:**
• 今日市场呈{trend}态势，{up}只上涨，{down}只下跌
• 涨跌停比 {limit_up}:{limit_down}，情绪{sentiment}
• 成交额 {total_amount/1e8:.0f}亿，{'放量' if total_amount > 1.5e12 else '缩量' if total_amount < 8e11 else '量能平稳'}
• 最强板块: {top_sector}(+{top_sector_change:.2f}%)

💡 **操作策略:**
• 仓位建议: {'维持6-7成，积极参与' if sentiment == '积极' else '控制在5成左右，精选个股' if sentiment == '中性' else '降至3-4成，防御为主'}
• 主线方向: {'AI算力/半导体/光通讯（有持续催化）' if ai_news else '科技成长'}
• 关注板块: {top_sector}（今日最强）、{'原油/黄金（地缘风险）' if geopolitical_news else ''}
• 选股思路: 优先{top_sector}内今日涨停或放量突破的个股

⚠️ **风险预警:**
• {risk_factor if risk_factor else '外围市场波动风险'}
• 避免追高涨幅过大(>30%)的题材股
• 设置止损位: 短线-5%，中线-10%

【九、数据质量说明】
• 板块分类已修复: 科创板(688XXX)、创业板(3XXXXX)、主板(0/6开头)、北交所(8/4开头)
• 新闻来源: Exa AI搜索引擎实时抓取
• 行情数据: 长桥API实时推送

{'='*70}
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}
"""
    
    filename = f"{REPORT_DIR}/daily_report_{today}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    log(f"✅ 报告已保存: {filename}")
    print(report)
    return report

if __name__ == '__main__':
    generate_report()
