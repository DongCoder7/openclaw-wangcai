#!/root/.openclaw/workspace/venv/bin/python3
"""
短期走势分析 - 核心脚本
使用4项优化技能：多周期+触碰验证+形态识别+Volume Profile
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pickle
import json
import sys
import os

# 添加venv路径
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

from longport.openapi import QuoteContext, Config, AdjustType, Period


class ShortTermAnalyzer:
    """短期走势分析器"""
    
    def __init__(self):
        """初始化，连接长桥API"""
        env_file = '/root/.openclaw/workspace/.longbridge.env'
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"')
        
        config = Config.from_env()
        self.ctx = QuoteContext(config)
    
    def fetch_data(self, symbol, days=60):
        """
        获取股票数据
        
        参数:
            symbol: 股票代码 (如 '688008.SH')
            days: 获取天数
        
        返回:
            df_60: 60分钟K线DataFrame
            df_day: 日线DataFrame
        """
        # 获取60分钟数据
        resp_60 = self.ctx.candlesticks(symbol, period=Period.Min_60, 
                                        count=days*4, adjust_type=AdjustType.NoAdjust)
        data_60 = []
        for candle in resp_60:
            data_60.append({
                'datetime': candle.timestamp,
                'open': float(candle.open),
                'high': float(candle.high),
                'low': float(candle.low),
                'close': float(candle.close),
                'volume': int(candle.volume)
            })
        df_60 = pd.DataFrame(data_60).sort_values('datetime').reset_index(drop=True)
        
        # 获取日线数据
        resp_day = self.ctx.candlesticks(symbol, period=Period.Day, 
                                         count=days, adjust_type=AdjustType.NoAdjust)
        data_day = []
        for candle in resp_day:
            data_day.append({
                'date': candle.timestamp.date(),
                'open': float(candle.open),
                'high': float(candle.high),
                'low': float(candle.low),
                'close': float(candle.close),
                'volume': int(candle.volume)
            })
        df_day = pd.DataFrame(data_day).sort_values('date').reset_index(drop=True)
        
        return df_60, df_day
    
    def calculate_indicators(self, df_60, df_day):
        """计算技术指标"""
        # 60分钟指标
        df_60['ma20'] = df_60['close'].rolling(20).mean()
        df_60['bb_middle'] = df_60['close'].rolling(20).mean()
        bb_std = df_60['close'].rolling(20).std()
        df_60['bb_upper'] = df_60['bb_middle'] + (bb_std * 2)
        df_60['bb_lower'] = df_60['bb_middle'] - (bb_std * 2)
        
        # 日线指标
        df_day['ma20'] = df_day['close'].rolling(20).mean()
        df_day['ma60'] = df_day['close'].rolling(60).mean()
        
        # MACD
        exp1 = df_day['close'].ewm(span=12, adjust=False).mean()
        exp2 = df_day['close'].ewm(span=26, adjust=False).mean()
        df_day['macd'] = exp1 - exp2
        
        # RSI
        delta = df_day['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df_day['rsi'] = 100 - (100 / (1 + gain / loss))
        
        return df_60, df_day
    
    def analyze_support_resistance(self, df_60):
        """分析支撑压力位"""
        recent = df_60.tail(40)
        
        support = recent['low'].min()
        resistance = recent['high'].max()
        latest = df_60['close'].iloc[-1]
        
        return {
            'support': support,
            'resistance': resistance,
            'latest': latest,
            'bb_lower': df_60['bb_lower'].iloc[-1],
            'bb_upper': df_60['bb_upper'].iloc[-1]
        }
    
    def count_touch_points(self, df, level, tolerance=0.02, lookback=60):
        """统计触碰次数"""
        recent = df.tail(lookback)
        lower = level * (1 - tolerance)
        upper = level * (1 + tolerance)
        
        touches = 0
        bounces = 0
        
        for i in range(len(recent) - 1):
            row = recent.iloc[i]
            next_row = recent.iloc[i + 1]
            
            if row['low'] <= upper and row['high'] >= lower:
                touches += 1
                if (row['close'] < level and next_row['close'] > row['close']) or \
                   (row['close'] > level and next_row['close'] < row['close']):
                    bounces += 1
        
        return {
            'count': touches,
            'bounce_rate': bounces / touches if touches > 0 else 0
        }
    
    def detect_patterns(self, df):
        """识别形态"""
        patterns = []
        recent = df.tail(20)
        
        highs = recent['high'].values
        lows = recent['low'].values
        
        # W底检测
        for i in range(3, len(recent) - 6):
            if lows[i] == min(lows[i-2:i+3]):
                for j in range(i + 3, len(recent) - 3):
                    if lows[j] == min(lows[j-2:j+3]):
                        if abs(lows[j] - lows[i]) / lows[i] < 0.03:
                            mid_high = max(highs[i:j])
                            if mid_high > lows[i] * 1.02:
                                patterns.append({'type': 'W底', 'strength': '强'})
                                break
        
        # M顶检测
        for i in range(3, len(recent) - 6):
            if highs[i] == max(highs[i-2:i+3]):
                for j in range(i + 3, len(recent) - 3):
                    if highs[j] == max(highs[j-2:j+3]):
                        if abs(highs[j] - highs[i]) / highs[i] < 0.03:
                            mid_low = min(lows[i:j])
                            if mid_low < highs[i] * 0.98:
                                patterns.append({'type': 'M顶', 'strength': '强'})
                                break
        
        return patterns
    
    def volume_profile(self, df):
        """成交量分布分析"""
        price_min = df['low'].min()
        price_max = df['high'].max()
        bin_size = (price_max - price_min) / 8
        
        volume_dist = {}
        for i in range(8):
            bin_low = price_min + i * bin_size
            bin_high = price_min + (i + 1) * bin_size
            mask = (df['low'] <= bin_high) & (df['high'] >= bin_low)
            vol = df[mask]['volume'].sum()
            volume_dist[f"{bin_low:.2f}"] = {
                'mid': (bin_low + bin_high) / 2,
                'volume': vol
            }
        
        poc_key = max(volume_dist.keys(), key=lambda k: volume_dist[k]['volume'])
        poc = volume_dist[poc_key]
        
        return {
            'poc_price': poc['mid'],
            'poc_volume': poc['volume'],
            'total_volume': sum([v['volume'] for v in volume_dist.values()])
        }
    
    def calculate_score(self, sr, touch_support, patterns, vp, df_day):
        """计算综合评分"""
        score = 0
        factors = []
        latest = sr['latest']
        
        # 日线趋势
        if df_day is not None and len(df_day) > 0:
            latest_day = df_day.iloc[-1]
            if latest_day['close'] > latest_day['ma20']:
                score += 1
                factors.append("日线上涨(+1)")
            else:
                score -= 1
                factors.append("日线下跌(-1)")
            
            if latest_day['rsi'] > 70:
                score -= 0.5
                factors.append("RSI超买(-0.5)")
            elif latest_day['rsi'] < 30:
                score += 0.5
                factors.append("RSI超卖(+0.5)")
        
        # 支撑有效性
        if touch_support['count'] >= 3 and touch_support['bounce_rate'] >= 0.5:
            score += 1
            factors.append("强支撑(+1)")
        elif touch_support['count'] >= 2:
            score += 0.5
            factors.append("有支撑(+0.5)")
        
        # 形态
        if patterns:
            if any('W底' in p['type'] for p in patterns):
                score += 1
                factors.append("W底(+1)")
            if any('M顶' in p['type'] for p in patterns):
                score -= 1
                factors.append("M顶(-1)")
        
        # 位置
        range_size = sr['resistance'] - sr['support']
        if range_size > 0:
            position = (latest - sr['support']) / range_size
            if position < 0.3:
                score += 0.5
                factors.append("低位(+0.5)")
            elif position > 0.7:
                score -= 0.5
                factors.append("高位(-0.5)")
        
        return score, factors
    
    def analyze(self, symbol):
        """
        分析单只股票短期走势
        
        参数:
            symbol: 股票代码 (如 '688008.SH')
        
        返回:
            dict: 分析结果
        """
        print(f"\n📊 分析 {symbol}...")
        
        # 获取数据
        df_60, df_day = self.fetch_data(symbol)
        
        # 计算指标
        df_60, df_day = self.calculate_indicators(df_60, df_day)
        
        # 技能1: 支撑压力分析
        sr = self.analyze_support_resistance(df_60)
        
        # 技能2: 触碰验证
        touch_support = self.count_touch_points(df_60, sr['support'])
        
        # 技能3: 形态识别
        patterns = self.detect_patterns(df_60)
        
        # 技能4: Volume Profile
        vp = self.volume_profile(df_60)
        
        # 综合评分
        score, factors = self.calculate_score(sr, touch_support, patterns, vp, df_day)
        
        # 预测方向
        if score >= 2:
            outlook = "强烈看涨"
            expected_return = "+15~25%"
        elif score >= 1:
            outlook = "看涨"
            expected_return = "+5~15%"
        elif score >= -1:
            outlook = "震荡"
            expected_return = "-5~5%"
        elif score >= -2:
            outlook = "看跌"
            expected_return = "-15~-5%"
        else:
            outlook = "强烈看跌"
            expected_return = "-25~-15%"
        
        result = {
            'symbol': symbol,
            'price': sr['latest'],
            'support': sr['support'],
            'resistance': sr['resistance'],
            'touch_count': touch_support['count'],
            'bounce_rate': touch_support['bounce_rate'],
            'patterns': [p['type'] for p in patterns],
            'poc': vp['poc_price'],
            'score': score,
            'factors': factors,
            'outlook': outlook,
            'expected_return': expected_return
        }
        
        return result
    
    def analyze_multiple(self, symbols):
        """
        分析多只股票
        
        参数:
            symbols: 股票代码列表
        
        返回:
            list: 分析结果列表
        """
        results = []
        for symbol in symbols:
            try:
                result = self.analyze(symbol)
                results.append(result)
            except Exception as e:
                print(f"❌ {symbol} 分析失败: {e}")
        
        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python3 analyze_short_term.py <股票代码1> [股票代码2] ...")
        print("示例: python3 analyze_short_term.py 688008.SH 603986.SH")
        return
    
    symbols = sys.argv[1:]
    
    print("="*70)
    print("短期走势分析")
    print("="*70)
    
    analyzer = ShortTermAnalyzer()
    results = analyzer.analyze_multiple(symbols)
    
    print("\n" + "="*70)
    print("分析结果排名")
    print("="*70)
    
    for i, r in enumerate(results, 1):
        emoji = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else f'{i}.'
        print(f"\n{emoji} {r['symbol']}")
        print(f"   价格: {r['price']:.2f}")
        print(f"   支撑: {r['support']:.2f} | 压力: {r['resistance']:.2f}")
        print(f"   触碰验证: {r['touch_count']}次/{r['bounce_rate']:.0%}反弹")
        print(f"   形态: {', '.join(r['patterns']) if r['patterns'] else '无'}")
        print(f"   POC: {r['poc']:.2f}")
        print(f"   评分: {r['score']:.1f} | {r['outlook']} | 预期收益: {r['expected_return']}")
        print(f"   因素: {', '.join(r['factors'])}")
    
    # 保存结果
    output_file = f'/root/.openclaw/workspace/study/short_term_result_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存: {output_file}")


if __name__ == '__main__':
    main()
