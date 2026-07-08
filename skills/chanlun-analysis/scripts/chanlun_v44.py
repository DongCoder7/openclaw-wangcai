#!/root/.openclaw/workspace/venv/bin/python3
"""
缠论多级别联立分析系统 v4.4
结构分析融合：笔段、中枢、买点识别 + 左侧交易框架
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/chanlun-analysis/scripts')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============ 核心函数（从v4.3复制并扩展） ============
FUZZY_CONFIG = {
    '1F': {'points': 3, 'pct': 0.0008},
    '5F': {'points': 3, 'pct': 0.0008},
    '15F': {'points': 2, 'pct': 0.0005},
    '30F': {'points': 2, 'pct': 0.0005},
    '60F': {'points': 3, 'pct': 0.0007},
    '120F': {'points': 3, 'pct': 0.0007},
    '日线': {'points': 5, 'pct': 0.0012},
    '双日': {'points': 5, 'pct': 0.0012},
}

def get_fuzzy(level_name, price):
    config = FUZZY_CONFIG.get(level_name, {'points': 2, 'pct': 0.0005})
    by_points = config['points']
    by_pct = price * config['pct']
    return min(by_points, by_pct)

def is_above(value, level, level_name):
    if pd.isna(level): return False
    return value > level + get_fuzzy(level_name, value)

def is_below(value, level, level_name):
    if pd.isna(level): return False
    return value < level - get_fuzzy(level_name, value)

def calc_ma(s, w): return s.rolling(w).mean()
def calc_ema(s, span): return s.ewm(span=span, adjust=False).mean()

def calc_macd(c, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(c, fast)
    ema_slow = calc_ema(c, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    macd = 2 * (dif - dea)
    return dif, dea, macd

def calc_boll(c, w=20, n=2):
    ma = calc_ma(c, w)
    std = c.rolling(w).std()
    return ma, ma + n * std, ma - n * std

def add_indicators(df):
    df = df.copy()
    df['MA55'] = calc_ma(df['Close'], 55)
    df['MA233'] = calc_ma(df['Close'], 233)
    df['DIF'], df['DEA'], df['MACD'] = calc_macd(df['Close'])
    df['BOLL_MID'], df['BOLL_UP'], df['BOLL_LOW'] = calc_boll(df['Close'])
    return df

# ============ v4.4 新增：结构分析 ============

def find_fenxing(df, n=3):
    """
    寻找顶底分型
    n: 分型需要的最少K线数（默认3）
    返回: 顶分型列表、底分型列表
    """
    tops = []
    bottoms = []
    
    for i in range(n-1, len(df)-n+1):
        # 顶分型：中间最高
        if df['High'].iloc[i] == df['High'].iloc[i-n+1:i+n].max():
            if df['High'].iloc[i] > df['High'].iloc[i-1] and df['High'].iloc[i] > df['High'].iloc[i+1]:
                if df['Low'].iloc[i] > df['Low'].iloc[i-1] and df['Low'].iloc[i] > df['Low'].iloc[i+1]:
                    tops.append({
                        'idx': i,
                        'time': df.index[i] if hasattr(df.index, '__getitem__') else i,
                        'high': df['High'].iloc[i],
                        'low': df['Low'].iloc[i]
                    })
        
        # 底分型：中间最低
        if df['Low'].iloc[i] == df['Low'].iloc[i-n+1:i+n].min():
            if df['Low'].iloc[i] < df['Low'].iloc[i-1] and df['Low'].iloc[i] < df['Low'].iloc[i+1]:
                if df['High'].iloc[i] < df['High'].iloc[i-1] and df['High'].iloc[i] < df['High'].iloc[i+1]:
                    bottoms.append({
                        'idx': i,
                        'time': df.index[i] if hasattr(df.index, '__getitem__') else i,
                        'high': df['High'].iloc[i],
                        'low': df['Low'].iloc[i]
                    })
    
    return tops, bottoms

def identify_bi(df, tops, bottoms):
    """
    识别笔（Bi）
    笔：顶分型与底分型之间的连接，中间至少有1根独立K线
    """
    bis = []
    
    # 合并顶底分型，按时间排序
    all_fenxing = []
    for t in tops:
        all_fenxing.append({**t, 'type': 'top'})
    for b in bottoms:
        all_fenxing.append({**b, 'type': 'bottom'})
    
    all_fenxing.sort(key=lambda x: x['idx'])
    
    # 连接笔
    last = None
    for fx in all_fenxing:
        if last is None:
            last = fx
            continue
        
        # 顶底交替
        if fx['type'] != last['type']:
            # 检查中间是否有独立K线
            if fx['idx'] - last['idx'] >= 2:
                bis.append({
                    'start': last,
                    'end': fx,
                    'direction': 'up' if fx['type'] == 'top' else 'down',
                    'start_price': last['low'] if last['type'] == 'bottom' else last['high'],
                    'end_price': fx['high'] if fx['type'] == 'top' else fx['low']
                })
                last = fx
    
    return bis

def identify_zhongshu(bis):
    """
    识别中枢（Zhongshu）
    中枢：连续三段重叠区域
    """
    zhongshus = []
    
    for i in range(2, len(bis)):
        b1, b2, b3 = bis[i-2], bis[i-1], bis[i]
        
        # 获取三段的价格范围
        if b1['direction'] == 'up':
            s1_high, s1_low = b1['end_price'], b1['start_price']
        else:
            s1_high, s1_low = b1['start_price'], b1['end_price']
        
        if b2['direction'] == 'up':
            s2_high, s2_low = b2['end_price'], b2['start_price']
        else:
            s2_high, s2_low = b2['start_price'], b2['end_price']
        
        if b3['direction'] == 'up':
            s3_high, s3_low = b3['end_price'], b3['start_price']
        else:
            s3_high, s3_low = b3['start_price'], b3['end_price']
        
        # 找重叠区域
        high_min = min(s1_high, s2_high, s3_high)
        low_max = max(s1_low, s2_low, s3_low)
        
        if high_min > low_max:
            zhongshus.append({
                'idx': i,
                'high': high_min,
                'low': low_max,
                'mid': (high_min + low_max) / 2,
                'bi1': b1, 'bi2': b2, 'bi3': b3
            })
    
    return zhongshus

def analyze_duan(bis):
    """
    分析段（Duan）：连续同向的笔组成一段
    """
    duans = []
    if len(bis) == 0:
        return duans
    
    current_duan = {
        'direction': bis[0]['direction'],
        'bis': [bis[0]],
        'start_price': bis[0]['start_price'],
        'end_price': bis[0]['end_price']
    }
    
    for bi in bis[1:]:
        if bi['direction'] == current_duan['direction']:
            current_duan['bis'].append(bi)
            current_duan['end_price'] = bi['end_price']
        else:
            duans.append(current_duan)
            current_duan = {
                'direction': bi['direction'],
                'bis': [bi],
                'start_price': bi['start_price'],
                'end_price': bi['end_price']
            }
    
    duans.append(current_duan)
    return duans

def check_beichi(duans, df,macd_col='MACD'):
    """
    检查背驰（Beichi）
    条件：第二段力度弱于第一段
    """
    if len(duans) < 2:
        return []
    
    beichi_list = []
    
    for i in range(1, len(duans)):
        d1, d2 = duans[i-1], duans[i]
        
        # 同向段比较
        if d1['direction'] == d2['direction']:
            # 计算力度（用MACD面积或价格幅度）
            d1_range = abs(d1['end_price'] - d1['start_price'])
            d2_range = abs(d2['end_price'] - d2['start_price'])
            
            # MACD面积（简化：用MACD绝对值之和）
            # 这里简化处理，实际需要计算段内的MACD面积
            
            if d2_range < d1_range * 0.8:  # 第二段力度明显弱于第一段
                beichi_list.append({
                    'idx': i,
                    'type': 'beichi',
                    'direction': d2['direction'],
                    'd1_range': d1_range,
                    'd2_range': d2_range,
                    'strength_ratio': d2_range / d1_range if d1_range > 0 else 0
                })
    
    return beichi_list

def identify_buy_points(df, bis, duans, zhongshus, beichi_list):
    """
    识别买点
    """
    buy_points = []
    
    # 一买：下跌背驰点
    for bc in beichi_list:
        if bc['direction'] == 'down':
            # 找到对应的底分型
            if bc['idx'] < len(duans):
                d = duans[bc['idx']]
                buy_points.append({
                    'type': '一买',
                    'price': d['end_price'],
                    'reason': f"下跌背驰，力度比{bc['strength_ratio']:.2f}",
                    'stop_loss': d['end_price'] * 0.99
                })
    
    # 二买：一买后的回调不破新低
    if len(buy_points) > 0:
        first_buy = buy_points[0]
        # 检查后续是否有回调不破低
        for i in range(1, len(duans)):
            d = duans[i]
            if d['direction'] == 'down' and d['end_price'] >= first_buy['price'] * 0.995:
                buy_points.append({
                    'type': '二买',
                    'price': d['end_price'],
                    'reason': f"回调不破新低，一买价格{first_buy['price']:.2f}",
                    'stop_loss': first_buy['price'] * 0.99
                })
                break
    
    # 三买：中枢上方回调不回到中枢
    for zs in zhongshus:
        # 检查是否有突破中枢后回调
        # 简化处理
        pass
    
    return buy_points

# ============ v4.4 新增：量能分析 ============

def analyze_volume(df, current_idx=None):
    """
    量能分析
    """
    if current_idx is None:
        current_idx = len(df) - 1
    
    if current_idx < 5:
        return {'status': 'unknown', 'detail': '数据不足'}
    
    recent = df.iloc[max(0, current_idx-4):current_idx+1]
    
    # 5日均量
    avg_volume = df['Volume'].iloc[max(0, current_idx-4):current_idx+1].mean()
    current_volume = df['Volume'].iloc[current_idx]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
    
    # 趋势
    volume_trend = "放量" if volume_ratio > 1.5 else "缩量" if volume_ratio < 0.7 else "正常"
    
    # 价格趋势
    price_change = (df['Close'].iloc[current_idx] - df['Close'].iloc[current_idx-1]) / df['Close'].iloc[current_idx-1] * 100
    price_trend = "上涨" if price_change > 0 else "下跌"
    
    # 量价配合
    if price_trend == "上涨" and volume_ratio > 1.2:
        status = "健康上涨"
    elif price_trend == "上涨" and volume_ratio < 0.8:
        status = "上涨背离"
    elif price_trend == "下跌" and volume_ratio > 1.5:
        status = "恐慌下跌"
    elif price_trend == "下跌" and volume_ratio < 0.8:
        status = "缩量回调"
    else:
        status = "中性"
    
    return {
        'status': status,
        'volume_ratio': volume_ratio,
        'volume_trend': volume_trend,
        'price_trend': price_trend,
        'price_change': price_change,
        'avg_volume': avg_volume,
        'current_volume': current_volume
    }

def check_panic_volume(df, current_idx=None):
    """
    检查恐慌盘
    """
    if current_idx is None:
        current_idx = len(df) - 1
    
    if current_idx < 5:
        return False
    
    avg_volume = df['Volume'].iloc[max(0, current_idx-4):current_idx+1].mean()
    current_volume = df['Volume'].iloc[current_idx]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
    
    # 跌幅
    price_change = (df['Close'].iloc[current_idx] - df['Close'].iloc[current_idx-1]) / df['Close'].iloc[current_idx-1] * 100
    
    # 恐慌盘条件：放量(>2倍) + 大跌(<-1.5%)
    if volume_ratio > 2.0 and price_change < -1.5:
        return {
            'is_panic': True,
            'volume_ratio': volume_ratio,
            'price_change': price_change,
            'message': f"恐慌盘！放量{volume_ratio:.1f}倍，跌幅{price_change:.2f}%"
        }
    
    return {'is_panic': False}

# ============ 主分析函数（v4.4） ============

def analyze_structure(df, level_name='5F'):
    """
    结构分析主函数
    """
    print(f"\n{'='*60}")
    print(f"📐 【{level_name} 结构分析】")
    print(f"{'='*60}")
    
    # 1. 找分型
    tops, bottoms = find_fenxing(df)
    print(f"\n  顶分型: {len(tops)} 个")
    print(f"  底分型: {len(bottoms)} 个")
    
    if len(tops) > 0:
        print(f"  最近顶分型: {tops[-1]['high']:.2f}")
    if len(bottoms) > 0:
        print(f"  最近底分型: {bottoms[-1]['low']:.2f}")
    
    # 2. 识别笔
    bis = identify_bi(df, tops, bottoms)
    print(f"\n  笔数量: {len(bis)} 支")
    
    if len(bis) > 0:
        last_bi = bis[-1]
        print(f"  最近笔: {last_bi['direction']} 从 {last_bi['start_price']:.2f} 到 {last_bi['end_price']:.2f}")
    
    # 3. 识别段
    duans = analyze_duan(bis)
    print(f"\n  段数量: {len(duans)} 段")
    
    if len(duans) > 0:
        last_duan = duans[-1]
        print(f"  最近段: {last_duan['direction']} 从 {last_duan['start_price']:.2f} 到 {last_duan['end_price']:.2f}")
        print(f"  段数统计: 向上{sum(1 for d in duans if d['direction']=='up')}段, 向下{sum(1 for d in duans if d['direction']=='down')}段")
    
    # 4. 识别中枢
    zhongshus = identify_zhongshu(bis)
    print(f"\n  中枢数量: {len(zhongshus)} 个")
    
    if len(zhongshus) > 0:
        last_zs = zhongshus[-1]
        print(f"  最近中枢: {last_zs['low']:.2f} - {last_zs['high']:.2f} (中轴: {last_zs['mid']:.2f})")
    
    # 5. 检查背驰
    beichi_list = check_beichi(duans, df)
    print(f"\n  背驰数量: {len(beichi_list)} 个")
    
    for bc in beichi_list:
        print(f"  - {bc['direction']}背驰，力度比: {bc['strength_ratio']:.2f}")
    
    # 6. 识别买点
    buy_points = identify_buy_points(df, bis, duans, zhongshus, beichi_list)
    print(f"\n  买点数量: {len(buy_points)} 个")
    
    for bp in buy_points:
        print(f"  - {bp['type']}: {bp['price']:.2f}, 止损: {bp['stop_loss']:.2f}")
        print(f"    原因: {bp['reason']}")
    
    return {
        'tops': tops,
        'bottoms': bottoms,
        'bis': bis,
        'duans': duans,
        'zhongshus': zhongshus,
        'beichi': beichi_list,
        'buy_points': buy_points
    }

# ============ 量能分析主函数 ============

def analyze_volume_main(df, level_name='5F'):
    """
    量能分析主函数
    """
    print(f"\n{'='*60}")
    print(f"📊 【{level_name} 量能分析】")
    print(f"{'='*60}")
    
    vol_analysis = analyze_volume(df)
    print(f"\n  量能状态: {vol_analysis['status']}")
    print(f"  量比: {vol_analysis['volume_ratio']:.2f}")
    print(f"  量能趋势: {vol_analysis['volume_trend']}")
    print(f"  价格趋势: {vol_analysis['price_trend']} ({vol_analysis['price_change']:.2f}%)")
    
    panic = check_panic_volume(df)
    if panic['is_panic']:
        print(f"\n  ⚠️ {panic['message']}")
    
    return vol_analysis

# ============ 左侧交易分析 ============

def analyze_left_side(df_5m, df_30m, df_60m, df_daily):
    """
    左侧交易分析：寻找拐点/买点
    """
    print(f"\n{'='*60}")
    print(f"🔍 【左侧交易分析 - 寻找拐点/买点】")
    print(f"{'='*60}")
    
    current = df_5m['Close'].iloc[-1]
    
    # 1. 5F结构分析
    print(f"\n📐 5F结构:")
    struct_5f = analyze_structure(df_5m, '5F')
    
    # 2. 量能分析
    print(f"\n📊 5F量能:")
    vol_5f = analyze_volume_main(df_5m, '5F')
    
    # 3. 大级别状态
    print(f"\n📈 大级别状态:")
    daily_ma55 = df_daily['MA55'].iloc[-1] if 'MA55' in df_daily.columns else None
    if daily_ma55 is not None:
        print(f"  日线MA55: {daily_ma55:.2f}")
        print(f"  日线状态: {'极强' if current > daily_ma55 else '极弱'}")
    
    if 'MA55' in df_60m.columns and len(df_60m) > 0:
        print(f"  60F MA55: {df_60m['MA55'].iloc[-1]:.2f}")
    
    # 4. 买点总结
    print(f"\n🎯 左侧买点总结:")
    
    buy_signals = []
    
    # 一买信号
    if len(struct_5f['beichi']) > 0:
        last_bc = struct_5f['beichi'][-1]
        if last_bc['direction'] == 'down':
            buy_signals.append({
                'type': '一买（背驰）',
                'price': current,
                'confidence': '高' if last_bc['strength_ratio'] < 0.6 else '中',
                'condition': '5F下跌背驰，等待底分型确认'
            })
    
    # 二买信号
    if len(struct_5f['buy_points']) > 1:
        for bp in struct_5f['buy_points']:
            if bp['type'] == '二买':
                buy_signals.append({
                    'type': '二买',
                    'price': bp['price'],
                    'confidence': '高',
                    'condition': '回调不破新低'
                })
    
    # 恐慌买点
    if vol_5f['status'] == '恐慌下跌':
        buy_signals.append({
            'type': '恐慌买点',
            'price': current,
            'confidence': '中',
            'condition': '恐慌盘涌出，等待底分型+缩量确认'
        })
    
    # 4005类支撑（动态计算）
    if len(struct_5f['zhongshus']) > 0:
        last_zs = struct_5f['zhongshus'][-1]
        support_price = last_zs['low']
        if abs(current - support_price) / current < 0.01:  # 接近中枢下轨
            buy_signals.append({
                'type': '中枢支撑',
                'price': support_price,
                'confidence': '中',
                'condition': f'接近中枢下轨{support_price:.2f}'
            })
    
    if len(buy_signals) == 0:
        print(f"  ⚠️ 暂无明确左侧买点")
        print(f"  建议: 等待结构形成")
    else:
        for sig in buy_signals:
            print(f"\n  ✅ {sig['type']}")
            print(f"     价格: {sig['price']:.2f}")
            print(f"     置信度: {sig['confidence']}")
            print(f"     条件: {sig['condition']}")
    
    return {
        'structure': struct_5f,
        'volume': vol_5f,
        'buy_signals': buy_signals
    }

# ============ 融合分析 ============

def analyze_fusion(df_5m, df_30m, df_60m, df_daily):
    """
    融合分析：左侧结构 + 右侧指标
    """
    print(f"\n{'='*80}")
    print(f"🔮 【v4.4 融合分析：左侧结构 + 右侧指标】")
    print(f"{'='*80}")
    
    current = df_5m['Close'].iloc[-1]
    
    # 左侧分析
    left_analysis = analyze_left_side(df_5m, df_30m, df_60m, df_daily)
    
    # 右侧指标（简化）
    print(f"\n{'='*60}")
    print(f"📊 【右侧指标状态】")
    print(f"{'='*60}")
    
    if 'MA55' in df_30m.columns and len(df_30m) > 0:
        ma30_55 = df_30m['MA55'].iloc[-1]
        print(f"\n  30F MA55: {ma30_55:.2f}")
        print(f"  状态: {'上方✅' if current > ma30_55 else '下方❌'}")
    
    if 'MA55' in df_60m.columns and len(df_60m) > 0:
        ma60_55 = df_60m['MA55'].iloc[-1]
        print(f"\n  60F MA55: {ma60_55:.2f}")
        print(f"  状态: {'上方✅' if current > ma60_55 else '下方❌'}")
    
    # 融合判断
    print(f"\n{'='*60}")
    print(f"🎯 【融合策略建议】")
    print(f"{'='*60}")
    
    has_left_signal = len(left_analysis['buy_signals']) > 0
    
    if has_left_signal:
        print(f"\n  ✅ 发现左侧买点信号")
        for sig in left_analysis['buy_signals']:
            print(f"     - {sig['type']}: {sig['price']:.2f}")
        
        print(f"\n  📋 操作策略:")
        print(f"     1. 左侧试仓: 3成仓位")
        print(f"     2. 止损设置: 底分型低点下方")
        print(f"     3. 右侧确认: 突破30F55线加仓至7成")
        print(f"     4. 右侧保护: 跌破60F MA55清仓")
    else:
        print(f"\n  ⚠️ 暂无左侧买点")
        print(f"\n  📋 操作策略:")
        print(f"     1. 空仓观望，等待结构形成")
        print(f"     2. 关注5F底分型+缩量信号")
        print(f"     3. 突破30F55线后右侧跟进")
    
    return left_analysis

# ============ 合成函数 ============

def build_60m_from_5m(df_5m):
    all_bars = []
    for date in df_5m['Date'].dt.date.unique():
        base = pd.Timestamp(date)
        day_5m = df_5m[df_5m['Date'].dt.date == date]
        for start_h, start_m, end_h, end_m, label_h, label_m in [
            (9, 30, 10, 30, 10, 30),
            (10, 30, 11, 30, 11, 30),
            (13, 0, 14, 0, 14, 0),
            (14, 0, 15, 0, 15, 0)
        ]:
            mask = (day_5m['Date'] >= base + pd.Timedelta(hours=start_h, minutes=start_m)) & \
                   (day_5m['Date'] <= base + pd.Timedelta(hours=end_h, minutes=end_m))
            subset = day_5m[mask]
            if len(subset) > 0:
                all_bars.append({
                    'Date': base + pd.Timedelta(hours=label_h, minutes=label_m),
                    'Open': subset['Open'].iloc[0],
                    'High': subset['High'].max(),
                    'Low': subset['Low'].min(),
                    'Close': subset['Close'].iloc[-1],
                    'Volume': subset['Volume'].sum()
                })
    df = pd.DataFrame(all_bars)
    return df.sort_values('Date').reset_index(drop=True) if len(df) > 0 else df

# ============ 主程序 ============
if __name__ == "__main__":
    print("="*80)
    print("缠论多级别联立分析系统 v4.4")
    print("结构分析融合：笔段、中枢、买点识别 + 左侧交易框架")
    print("="*80)
    
    # 加载数据
    data_dir = '/mnt/agents/output/'
    df_5m = pd.read_csv(data_dir + 'sh_index_5m_longbridge.csv')
    df_5m['Date'] = pd.to_datetime(df_5m['Date'])
    df_5m = add_indicators(df_5m)
    
    df_daily = pd.read_csv(data_dir + 'sh_index_daily_0706.csv')
    df_daily['Date'] = pd.to_datetime(df_daily['Date'])
    df_daily = add_indicators(df_daily)
    
    # 合成60F
    df_60m = build_60m_from_5m(df_5m)
    if len(df_60m) > 0:
        df_60m = add_indicators(df_60m)
    
    # 合成30F
    trade = df_5m[df_5m['Date'].dt.hour.isin([9,10,11,13,14])].copy()
    df_30m = trade.set_index('Date').resample('30min').agg({
        'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'
    }).dropna().reset_index()
    if len(df_30m) > 0:
        df_30m = add_indicators(df_30m)
    
    # 执行融合分析
    analyze_fusion(df_5m, df_30m, df_60m, df_daily)
    
    print(f"\n{'='*80}")
    print("分析完成")
    print(f"{'='*80}")
