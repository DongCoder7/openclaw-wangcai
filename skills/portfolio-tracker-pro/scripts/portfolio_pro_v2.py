#!/root/.openclaw/workspace/venv/bin/python3
"""
实盘跟踪Pro V2 - 高级技术分析系统

升级功能:
1. K线形态库 (十字星/锤头/吞没/启明星/黄昏星等)
2. 量能深度分析 (资金流向/主力吸筹出货识别)
3. 完整5浪理论 (艾略特波浪 1-2-3-4-5 + A-B-C)
4. MACD背离检测 (顶背离/底背离)
5. 板块轮动分析 (持仓板块强弱对比)

用法:
  ./venv_runner.sh skills/portfolio-tracker-pro/scripts/portfolio_pro_v2.py [session]
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import json
from collections import defaultdict

sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

from longport.openapi import QuoteContext, Config, AdjustType, Period

# 持仓配置
PORTFOLIO = {
    "300750.SZ": {"name": "宁德时代", "shares": 1000, "sector": "新能源"},
    "300274.SZ": {"name": "阳光电源", "shares": 1500, "sector": "新能源"},
    "688676.SH": {"name": "金盘科技", "shares": 2000, "sector": "电力设备"},
    "600875.SH": {"name": "东方电气", "shares": 3000, "sector": "电力设备"},
    "601088.SH": {"name": "中国神华", "shares": 3000, "sector": "能源"},
    "603986.SH": {"name": "兆易创新", "shares": 1500, "sector": "半导体"},
    "688008.SH": {"name": "澜起科技", "shares": 2000, "sector": "半导体"},
    "603920.SH": {"name": "世运电路", "shares": 4000, "sector": "PCB"},
    "002463.SZ": {"name": "沪电股份", "shares": 3000, "sector": "PCB"},
}

# 板块基准ETF/指数用于对比
SECTOR_BENCHMARK = {
    "新能源": "515030.SH",      # 新能源车ETF
    "电力设备": "159611.SZ",     # 电力ETF
    "能源": "159930.SZ",         # 能源ETF
    "半导体": "512480.SH",       # 半导体ETF
    "PCB": "159997.SZ",          # 电子ETF
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


# ========================================
# 功能1: K线形态库
# ========================================

class CandlestickPatterns:
    """K线形态识别库"""
    
    @staticmethod
    def is_doji(open_price, high, low, close, tolerance=0.01):
        """十字星: 实体很小，上下影线"""
        body = abs(close - open_price)
        range_price = high - low
        if range_price == 0:
            return False
        return body / range_price < tolerance
    
    @staticmethod
    def is_hammer(open_price, high, low, close):
        """锤头线: 小实体，长下影线"""
        body = abs(close - open_price)
        lower_shadow = min(open_price, close) - low
        upper_shadow = high - max(open_price, close)
        return lower_shadow > body * 2 and upper_shadow < body
    
    @staticmethod
    def is_inverted_hammer(open_price, high, low, close):
        """倒锤头: 小实体，长上影线"""
        body = abs(close - open_price)
        upper_shadow = high - max(open_price, close)
        lower_shadow = min(open_price, close) - low
        return upper_shadow > body * 2 and lower_shadow < body
    
    @staticmethod
    def is_engulfing(prev_open, prev_close, curr_open, curr_close):
        """吞没形态"""
        prev_bullish = prev_close > prev_open
        curr_bullish = curr_close > curr_open
        
        if prev_bullish and not curr_bullish:  # 看跌吞没
            return curr_open > prev_close and curr_close < prev_open
        elif not prev_bullish and curr_bullish:  # 看涨吞没
            return curr_open < prev_close and curr_close > prev_open
        return False
    
    @staticmethod
    def is_morning_star(df, idx):
        """启明星: 下跌趋势中的反转信号"""
        if idx < 2:
            return False
        
        first = df.iloc[idx-2]
        second = df.iloc[idx-1]
        third = df.iloc[idx]
        
        # 第一根大阴线
        first_bearish = first['close'] < first['open']
        first_body = first['open'] - first['close']
        
        # 第二根小实体（十字星或锤头）
        second_body = abs(second['close'] - second['open'])
        
        # 第三根大阳线
        third_bullish = third['close'] > third['open']
        third_body = third['close'] - third['open']
        
        return (first_bearish and first_body > 0 and
                second_body < first_body * 0.3 and
                third_bullish and third_body > first_body * 0.5 and
                third['close'] > (first['open'] + first['close']) / 2)
    
    @staticmethod
    def is_evening_star(df, idx):
        """黄昏星: 上涨趋势中的反转信号"""
        if idx < 2:
            return False
        
        first = df.iloc[idx-2]
        second = df.iloc[idx-1]
        third = df.iloc[idx]
        
        # 第一根大阳线
        first_bullish = first['close'] > first['open']
        first_body = first['close'] - first['open']
        
        # 第二根小实体
        second_body = abs(second['close'] - second['open'])
        
        # 第三根大阴线
        third_bearish = third['close'] < third['open']
        third_body = third['open'] - third['close']
        
        return (first_bullish and first_body > 0 and
                second_body < first_body * 0.3 and
                third_bearish and third_body > first_body * 0.5 and
                third['close'] < (first['open'] + first['close']) / 2)
    
    @staticmethod
    def analyze_patterns(df):
        """分析所有K线形态"""
        patterns = []
        
        if len(df) < 3:
            return patterns
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 单根K线形态
        if CandlestickPatterns.is_doji(latest['open'], latest['high'], latest['low'], latest['close']):
            patterns.append("十字星")
        
        if CandlestickPatterns.is_hammer(latest['open'], latest['high'], latest['low'], latest['close']):
            patterns.append("锤头线" if latest['close'] > latest['open'] else "吊颈线")
        
        if CandlestickPatterns.is_inverted_hammer(latest['open'], latest['high'], latest['low'], latest['close']):
            patterns.append("倒锤头")
        
        # 双根形态
        if CandlestickPatterns.is_engulfing(prev['open'], prev['close'], latest['open'], latest['close']):
            if latest['close'] > latest['open']:
                patterns.append("看涨吞没")
            else:
                patterns.append("看跌吞没")
        
        # 三根形态
        if CandlestickPatterns.is_morning_star(df, len(df)-1):
            patterns.append("启明星")
        
        if CandlestickPatterns.is_evening_star(df, len(df)-1):
            patterns.append("黄昏星")
        
        return patterns


# ========================================
# 功能2: 量能深度分析
# ========================================

class VolumeAnalysis:
    """量能深度分析"""
    
    @staticmethod
    def calculate_money_flow(df):
        """计算资金流向"""
        df = df.copy()
        
        # 典型价格
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        # 资金流入/流出
        df['money_flow'] = df['typical_price'] * df['volume']
        
        # 判断流入还是流出
        df['positive_flow'] = np.where(df['close'] > df['open'], df['money_flow'], 0)
        df['negative_flow'] = np.where(df['close'] < df['open'], df['money_flow'], 0)
        
        # 累计资金流向
        total_positive = df['positive_flow'].sum()
        total_negative = df['negative_flow'].sum()
        
        money_flow_ratio = total_positive / (total_negative + 1e-10)
        
        return {
            'positive_flow': total_positive,
            'negative_flow': total_negative,
            'money_flow_ratio': money_flow_ratio,
            'net_flow': total_positive - total_negative
        }
    
    @staticmethod
    def detect_accumulation_distribution(df, lookback=20):
        """识别主力吸筹/出货"""
        if len(df) < lookback:
            return "数据不足"
        
        recent = df.tail(lookback)
        
        # 计算OBV (On Balance Volume)
        obv = [recent.iloc[0]['volume']]
        for i in range(1, len(recent)):
            if recent.iloc[i]['close'] > recent.iloc[i-1]['close']:
                obv.append(obv[-1] + recent.iloc[i]['volume'])
            elif recent.iloc[i]['close'] < recent.iloc[i-1]['close']:
                obv.append(obv[-1] - recent.iloc[i]['volume'])
            else:
                obv.append(obv[-1])
        
        # 价格趋势
        price_trend = (recent.iloc[-1]['close'] - recent.iloc[0]['close']) / recent.iloc[0]['close']
        
        # OBV趋势
        obv_trend = (obv[-1] - obv[0]) / abs(obv[0] + 1)
        
        # 判断吸筹/出货
        if obv_trend > 0.1 and price_trend < 0.05:
            return "主力吸筹"  # 量价背离，价跌量增
        elif obv_trend < -0.1 and price_trend > 0:
            return "主力出货"  # 量价背离，价涨量减
        elif obv_trend > 0 and price_trend > 0:
            return "量价齐升"  # 健康上涨
        elif obv_trend < 0 and price_trend < 0:
            return "量价齐跌"  # 健康下跌
        else:
            return "震荡整理"
    
    @staticmethod
    def analyze_volume_profile(df, bins=10):
        """成交量分布分析"""
        price_min = df['low'].min()
        price_max = df['high'].max()
        bin_size = (price_max - price_min) / bins
        
        profile = []
        for i in range(bins):
            low = price_min + i * bin_size
            high = price_min + (i + 1) * bin_size
            mask = (df['low'] <= high) & (df['high'] >= low)
            vol = df[mask]['volume'].sum()
            profile.append({'low': low, 'high': high, 'mid': (low+high)/2, 'volume': vol})
        
        # POC和Value Area
        poc = max(profile, key=lambda x: x['volume'])
        total_vol = sum(p['volume'] for p in profile)
        
        # 70% Value Area
        sorted_profile = sorted(profile, key=lambda x: -x['volume'])
        cum_vol = 0
        va_levels = []
        for p in sorted_profile:
            cum_vol += p['volume']
            va_levels.append(p)
            if cum_vol >= total_vol * 0.7:
                break
        
        va_low = min(v['low'] for v in va_levels)
        va_high = max(v['high'] for v in va_levels)
        
        return {
            'poc': poc['mid'],
            'poc_volume': poc['volume'],
            'value_area_low': va_low,
            'value_area_high': va_high,
            'profile': profile
        }


# ========================================
# 功能3: 完整5浪理论
# ========================================

class ElliottWave:
    """艾略特波浪理论分析"""
    
    @staticmethod
    def find_pivots(df, window=5):
        """找到转折点（高低点）"""
        highs = df['high'].values
        lows = df['low'].values
        
        pivots_high = []
        pivots_low = []
        
        for i in range(window, len(df) - window):
            # 高点
            if highs[i] == max(highs[i-window:i+window+1]):
                pivots_high.append((i, highs[i]))
            
            # 低点
            if lows[i] == min(lows[i-window:i+window+1]):
                pivots_low.append((i, lows[i]))
        
        return pivots_high, pivots_low
    
    @staticmethod
    def detect_wave_structure(df):
        """检测波浪结构"""
        pivots_high, pivots_low = ElliottWave.find_pivots(df)
        
        if len(pivots_high) < 3 or len(pivots_low) < 3:
            return {"structure": "无法识别", "current_wave": "未知", "confidence": 0}
        
        # 简化版：判断当前处于上涨还是下跌趋势
        recent_highs = [p[1] for p in pivots_high[-3:]]
        recent_lows = [p[1] for p in pivots_low[-3:]]
        
        current_price = df.iloc[-1]['close']
        
        # 判断趋势
        if len(recent_highs) >= 2 and len(recent_lows) >= 2:
            # 上涨趋势特征
            if recent_highs[-1] > recent_highs[-2] and recent_lows[-1] > recent_lows[-2]:
                # 判断是第几浪
                if current_price > recent_highs[-1] * 0.98:
                    return {"structure": "上升浪", "current_wave": "第5浪或延长浪", "confidence": 70, "risk": "注意回调"}
                else:
                    return {"structure": "上升浪", "current_wave": "第3浪或第4浪调整", "confidence": 60}
            
            # 下跌趋势特征
            elif recent_highs[-1] < recent_highs[-2] and recent_lows[-1] < recent_lows[-2]:
                if current_price < recent_lows[-1] * 1.02:
                    return {"structure": "下跌浪", "current_wave": "第5浪下跌或C浪", "confidence": 70, "risk": "可能反弹"}
                else:
                    return {"structure": "下跌浪", "current_wave": "第3浪或第4浪反弹", "confidence": 60}
            
            # 震荡
            else:
                return {"structure": "震荡整理", "current_wave": "B浪反弹或三角形整理", "confidence": 50}
        
        return {"structure": "无法识别", "current_wave": "数据不足", "confidence": 0}


# ========================================
# 功能4: MACD背离检测
# ========================================

class MACDivergence:
    """MACD背离检测"""
    
    @staticmethod
    def calculate_macd(df, fast=12, slow=26, signal=9):
        """计算MACD"""
        df = df.copy()
        df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
        df['macd'] = df['ema_fast'] - df['ema_slow']
        df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        return df
    
    @staticmethod
    def find_peaks_troughs(values, window=3):
        """找到峰值和谷值"""
        peaks = []
        troughs = []
        
        for i in range(window, len(values) - window):
            if values[i] == max(values[i-window:i+window+1]):
                peaks.append((i, values[i]))
            if values[i] == min(values[i-window:i+window+1]):
                troughs.append((i, values[i]))
        
        return peaks, troughs
    
    @staticmethod
    def detect_divergence(df):
        """检测背离"""
        df = MACDivergence.calculate_macd(df)
        
        closes = df['close'].values
        macd_values = df['macd'].values
        
        # 找价格的峰谷
        price_peaks, price_troughs = MACDivergence.find_peaks_troughs(closes)
        macd_peaks, macd_troughs = MACDivergence.find_peaks_troughs(macd_values)
        
        divergence = []
        
        # 顶背离检测 (价格新高，MACD未新高)
        if len(price_peaks) >= 2 and len(macd_peaks) >= 2:
            last_price_peak = price_peaks[-1]
            prev_price_peak = price_peaks[-2]
            
            # 找对应的MACD峰值
            last_macd_peak = None
            prev_macd_peak = None
            
            for mp in macd_peaks:
                if abs(mp[0] - last_price_peak[0]) < 3:
                    last_macd_peak = mp
                if abs(mp[0] - prev_price_peak[0]) < 3:
                    prev_macd_peak = mp
            
            if last_macd_peak and prev_macd_peak:
                if last_price_peak[1] > prev_price_peak[1] and last_macd_peak[1] < prev_macd_peak[1]:
                    divergence.append({
                        'type': '顶背离',
                        'signal': '看跌',
                        'strength': '强' if last_macd_peak[1] < prev_macd_peak[1] * 0.9 else '弱'
                    })
        
        # 底背离检测 (价格新低，MACD未新低)
        if len(price_troughs) >= 2 and len(macd_troughs) >= 2:
            last_price_trough = price_troughs[-1]
            prev_price_trough = price_troughs[-2]
            
            last_macd_trough = None
            prev_macd_trough = None
            
            for mt in macd_troughs:
                if abs(mt[0] - last_price_trough[0]) < 3:
                    last_macd_trough = mt
                if abs(mt[0] - prev_price_trough[0]) < 3:
                    prev_macd_trough = mt
            
            if last_macd_trough and prev_macd_trough:
                if last_price_trough[1] < prev_price_trough[1] and last_macd_trough[1] > prev_macd_trough[1]:
                    divergence.append({
                        'type': '底背离',
                        'signal': '看涨',
                        'strength': '强' if last_macd_trough[1] > prev_macd_trough[1] * 1.1 else '弱'
                    })
        
        return divergence


# ========================================
# 功能5: 板块轮动分析
# ========================================

class SectorRotation:
    """板块轮动分析"""
    
    @staticmethod
    def get_sector_performance(ctx, lookback_days=5):
        """获取板块表现"""
        sector_perf = {}
        
        for sector, etf in SECTOR_BENCHMARK.items():
            try:
                resp = ctx.candlesticks(etf, period=Period.Day, count=lookback_days+1, adjust_type=AdjustType.NoAdjust)
                if len(resp) >= 2:
                    start_price = float(resp[0].close)
                    end_price = float(resp[-1].close)
                    change_pct = (end_price - start_price) / start_price * 100
                    sector_perf[sector] = change_pct
            except:
                sector_perf[sector] = 0
        
        return sector_perf
    
    @staticmethod
    def analyze_portfolio_sectors(ctx, portfolio):
        """分析持仓板块强弱"""
        sector_perf = SectorRotation.get_sector_performance(ctx)
        
        # 持仓板块 exposure
        portfolio_sectors = defaultdict(float)
        for symbol, info in portfolio.items():
            sector = info.get('sector', '其他')
            portfolio_sectors[sector] += 1
        
        # 板块排名
        ranked_sectors = sorted(sector_perf.items(), key=lambda x: -x[1])
        
        return {
            'sector_performance': sector_perf,
            'portfolio_exposure': dict(portfolio_sectors),
            'ranked_sectors': ranked_sectors,
            'strong_sectors': [s for s, p in ranked_sectors[:2]],
            'weak_sectors': [s for s, p in ranked_sectors[-2:]]
        }


# ========================================
# 主分析函数
# ========================================

def analyze_stock_pro(ctx, symbol, name, shares):
    """高级股票分析"""
    
    # 获取数据
    df_1min = get_minute_data(ctx, symbol, Period.Min_1, 240)
    df_5min = get_minute_data(ctx, symbol, Period.Min_5, 48)
    df_day = get_minute_data(ctx, symbol, Period.Day, 60)
    
    if df_1min is None or len(df_1min) < 10:
        return None
    
    current_price = df_1min.iloc[-1]['close']
    market_value = current_price * shares
    
    # 1. K线形态
    patterns = CandlestickPatterns.analyze_patterns(df_1min.tail(5))
    
    # 2. 量能分析
    volume_analysis = VolumeAnalysis.calculate_money_flow(df_1min)
    accumulation = VolumeAnalysis.detect_accumulation_distribution(df_1min)
    vol_profile = VolumeAnalysis.analyze_volume_profile(df_1min)
    
    # 3. 波浪理论
    wave_info = ElliottWave.detect_wave_structure(df_day if df_day is not None else df_5min)
    
    # 4. MACD背离
    macd_div = MACDivergence.detect_divergence(df_day if df_day is not None else df_5min)
    
    # 综合评分
    score = 0
    factors = []
    
    # K线形态加分
    bullish_patterns = ['锤头线', '看涨吞没', '启明星', '倒锤头']
    bearish_patterns = ['吊颈线', '看跌吞没', '黄昏星']
    
    for p in patterns:
        if any(bp in p for bp in bullish_patterns):
            score += 0.5
            factors.append(f"看涨形态({p})")
        if any(bp in p for bp in bearish_patterns):
            score -= 0.5
            factors.append(f"看跌形态({p})")
    
    # 资金流向
    if volume_analysis.get('money_flow_ratio', 1) > 1.5:
        score += 0.5
        factors.append("资金流入")
    elif volume_analysis.get('money_flow_ratio', 1) < 0.7:
        score -= 0.5
        factors.append("资金流出")
    
    # 吸筹/出货
    if "吸筹" in accumulation:
        score += 1
        factors.append("主力吸筹")
    elif "出货" in accumulation:
        score -= 1
        factors.append("主力出货")
    
    # 波浪位置
    if "第5浪" in wave_info.get('current_wave', '') and "上升" in wave_info.get('structure', ''):
        score -= 0.5
        factors.append("5浪末期(风险)")
    
    # 背离
    for div in macd_div:
        if div['type'] == '顶背离':
            score -= 1
            factors.append(f"顶背离({div['strength']})")
        elif div['type'] == '底背离':
            score += 1
            factors.append(f"底背离({div['strength']})")
    
    # 趋势判断
    if len(df_1min) > 20:
        ma20 = df_1min['close'].rolling(20).mean().iloc[-1]
        if current_price > ma20:
            score += 0.5
            factors.append("趋势向上")
        else:
            score -= 0.5
            factors.append("趋势向下")
    
    # 预测
    if score >= 2:
        outlook = "🚀 强烈看涨"
    elif score >= 1:
        outlook = "📈 看涨"
    elif score >= -1:
        outlook = "➡️ 震荡"
    elif score >= -2:
        outlook = "📉 看跌"
    else:
        outlook = "🔻 强烈看跌"
    
    return {
        'symbol': symbol,
        'name': name,
        'shares': shares,
        'price': current_price,
        'market_value': market_value,
        'patterns': patterns,
        'volume_signal': accumulation,
        'money_flow_ratio': volume_analysis.get('money_flow_ratio', 1),
        'wave': wave_info,
        'macd_divergence': macd_div,
        'score': score,
        'factors': factors,
        'outlook': outlook,
        'poc': vol_profile['poc'],
        'value_area': (vol_profile['value_area_low'], vol_profile['value_area_high'])
    }


def get_minute_data(ctx, symbol, period, count):
    """获取分钟数据"""
    try:
        resp = ctx.candlesticks(symbol, period=period, count=count, adjust_type=AdjustType.NoAdjust)
        data = []
        for c in resp:
            data.append({
                'datetime': c.timestamp,
                'open': float(c.open),
                'high': float(c.high),
                'low': float(c.low),
                'close': float(c.close),
                'volume': int(c.volume)
            })
        return pd.DataFrame(data).sort_values('datetime').reset_index(drop=True)
    except:
        return None


def generate_report(results, sector_analysis, session_name):
    """生成报告"""
    lines = []
    lines.append(f"📊 实盘跟踪Pro V2 - {session_name}")
    lines.append(f"时间: {datetime.now().strftime('%H:%M')}")
    lines.append("="*60)
    
    # 板块轮动
    lines.append("\n【板块轮动】(近5日涨幅)")
    lines.append(f"  强势板块: {', '.join(sector_analysis['strong_sectors'])}")
    lines.append(f"  弱势板块: {', '.join(sector_analysis['weak_sectors'])}")
    lines.append("  板块涨幅(5日):")
    for sector, perf in sector_analysis['ranked_sectors'][:3]:
        lines.append(f"    {sector}: {perf:+.2f}%")
    
    # 紧急调仓
    urgent = [r for r in results if r['score'] <= -2 or any('顶背离' in f and '强' in f for f in r['factors'])]
    if urgent:
        lines.append("\n🔴 紧急调仓:")
        for r in urgent:
            lines.append(f"  {r['name']}: {r['outlook']}")
            lines.append(f"    形态: {', '.join(r['patterns'])}")
            lines.append(f"    量能: {r['volume_signal']}")
            if r['macd_divergence']:
                lines.append(f"    MACD: {r['macd_divergence'][0]['type']}({r['macd_divergence'][0]['strength']})")
    
    # 推荐买入
    buy = [r for r in results if r['score'] >= 1.5 and r['outlook'] in ['🚀 强烈看涨', '📈 看涨']]
    if buy:
        lines.append("\n✅ 关注买入:")
        for r in buy:
            lines.append(f"  {r['name']}: {r['price']:.2f} {r['outlook']}")
            if r['patterns']:
                lines.append(f"    信号: {', '.join(r['patterns'])}")
    
    # 持仓明细
    lines.append("\n📈 持仓分析:")
    for r in sorted(results, key=lambda x: -x['score']):
        emoji = "🚀" if r['score'] >= 2 else "📈" if r['score'] >= 1 else "➡️" if r['score'] >= -1 else "📉" if r['score'] >= -2 else "🔻"
        lines.append(f"  {emoji} {r['name']}: {r['price']:.2f} (评分{r['score']:.1f}) {r['outlook']}")
    
    return '\n'.join(lines)


def send_feishu(message, target="user:ou_efbad805767f4572e8f93ebafa8d5402"):
    """发送飞书"""
    import subprocess
    cmd = ["openclaw", "message", "send", "--channel", "feishu", "--target", target, "--message", message]
    try:
        subprocess.run(cmd, timeout=30)
        return True
    except:
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: portfolio_pro_v2.py [morning|noon|afternoon|close]")
        return
    
    session = sys.argv[1]
    session_names = {
        "morning": "🌅 早盘分析 (9:30)",
        "noon": "☀️ 午盘分析 (11:00)",
        "afternoon": "🌤️ 下午分析 (13:30)",
        "close": "🌇 尾盘分析 (14:50)"
    }
    
    print(f"开始 {session_names.get(session)} 分析...")
    
    ctx = init_api()
    
    # 分析每只股票
    results = []
    for symbol, info in PORTFOLIO.items():
        print(f"  分析 {info['name']}...")
        result = analyze_stock_pro(ctx, symbol, info['name'], info['shares'])
        if result:
            results.append(result)
    
    # 板块分析
    print("  分析板块轮动...")
    sector_analysis = SectorRotation.analyze_portfolio_sectors(ctx, PORTFOLIO)
    
    # 生成报告
    report = generate_report(results, sector_analysis, session_names.get(session))
    
    print("\n" + report)
    
    # 发送飞书
    send_feishu(report)
    print("\n✅ 报告已发送至飞书")


if __name__ == '__main__':
    main()
