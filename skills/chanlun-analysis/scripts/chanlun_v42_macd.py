def analyze_macd_systematic(levels_macd, levels_55, levels_trend=None):
    """
    v4.2系统化MACD分析：适配SKILL.md理论
    
    核心：六种状态 + 极强/极弱三特征 + N+2→N传导 + 零轴金叉/死叉
    """
    report = []
    report.append("="*70)
    report.append("Step 3.2: MACD系统化分析（v4.2理论适配）")
    report.append("="*70)
    report.append("")
    
    # 1. 第一步：六种状态判定
    report.append("【第一步：各级别MACD六种状态判定（SKILL.md）】")
    report.append("")
    
    # 状态定义
    report.append("  状态定义：")
    report.append("  极强: DIF≥0, DEA≤0, MACD>0  |  强: DIF>DEA>0, MACD>0  |  中性偏强: 0>DIF>DEA, MACD>0")
    report.append("  极弱: DIF≤0, DEA≥0, MACD<0  |  弱: DIF<DEA<0, MACD<0  |  中性偏弱: 0<DIF<DEA, MACD<0")
    report.append("")
    
    for level_name in ['双日', '日线', '120F', '60F', '30F', '15F', '5F', '3F']:
        if level_name in levels_macd:
            data = levels_macd[level_name]
            dif = data['dif']
            dea = data['dea']
            macd_val = data['macd']
            
            # 判定状态
            if dif >= 0 and dea <= 0 and macd_val > 0:
                state = "极强"
                op = "不做空，上涨持续性极高"
            elif dif > dea > 0 and macd_val > 0:
                state = "强"
                op = "做多胜率高"
            elif 0 > dif > dea and macd_val > 0:
                state = "中性偏强"
                op = "观察"
            elif dif <= 0 and dea >= 0 and macd_val < 0:
                state = "极弱"
                op = "不做多，下跌持续性极高"
            elif dif < dea < 0 and macd_val < 0:
                state = "弱"
                op = "做空胜率高"
            elif 0 < dif < dea and macd_val < 0:
                state = "中性偏弱"
                op = "观察"
            else:
                state = "其他"
                op = "观察"
            
            report.append(f"  {level_name:6s}: 【{state}】DIF={dif:8.2f}, DEA={dea:8.2f}, MACD={macd_val:8.2f}")
            report.append(f"          → {op}")
    
    report.append("")
    
    # 2. 第二步：极强/极弱三特征
    report.append("【第二步：极强/极弱三特征分析（SKILL.md）】")
    report.append("")
    
    # 找最大级别极端状态
    max_state = None
    for level in ['双日', '日线', '120F', '60F']:
        if level in levels_macd:
            d = levels_macd[level]
            if d['dif'] >= 0 and d['dea'] <= 0 and d['macd'] > 0:
                max_state = (level, '极强')
                break
            elif d['dif'] < d['dea'] < 0 and d['macd'] < 0:
                max_state = (level, '弱')
                break
    
    if max_state:
        level, state = max_state
        report.append(f"  最大级别状态: {level} 【{state}】")
        report.append("")
        
        if state == "弱":
            report.append(f"  【特征1：底背离失效】")
            report.append(f"  → {level}{state} → 引发次级别主跌段")
            report.append(f"  → 次级别以下的底背离，可能都是阶段性无效")
            report.append(f"  → 当{state}度过，小级别主跌特征失效，小级别底背离才会生效")
            report.append(f"  → 生效标志：突破该级别55线")
            report.append("")
            
            report.append(f"  【特征2：55均线大概率压制】")
            report.append(f"  → {level}{state}形态下，首次反弹次级别55线 → 极大概率受到压制")
            report.append(f"  → 这是技术体系里胜率极高的做空开仓点/减仓点")
            report.append(f"  → 如果次级别突破了55线 → 认为{level}{state}形态解除")
            report.append("")
            
            report.append(f"  【特征3：传递性】")
            report.append(f"  → {state}形态从高位下跌时出现")
            report.append(f"  → 可以理解为高位跌破本级别55均线的过程")
            report.append(f"  → 这个传递性可以衡量下跌的持续性")
            report.append(f"  → 指数有效跌破本级别55线后 → 有向更低级别运动的惯性")
    
    # 3. 第三步：N+2→N传导
    report.append("")
    report.append("【第三步：N+2→N级别传导（SKILL.md）】")
    report.append("")
    
    for n2, n in [('双日', '日线'), ('日线', '120F'), ('120F', '60F'), ('60F', '30F')]:
        if n2 in levels_macd and n in levels_macd:
            d1 = levels_macd[n2]
            d2 = levels_macd[n]
            if d1['dif'] < d1['dea'] < 0 and d1['macd'] < 0:
                report.append(f"  {n2}弱 → 引发{n}主跌段")
                if d2['dif'] < d2['dea'] < 0 and d2['macd'] < 0:
                    report.append(f"  → {n}当前处于弱状态，主跌段确认")
                else:
                    report.append(f"  → {n}当前处于震荡状态，等待主跌段启动")
    
    # 4. 第四步：零轴金叉/死叉
    report.append("")
    report.append("【第四步：零轴金叉/死叉（SKILL.md）】")
    report.append("")
    report.append("  零轴金叉=极强形态，零轴死叉=极弱形态")
    report.append("")
    
    for level in ['日线', '120F', '60F', '30F']:
        if level in levels_macd:
            d = levels_macd[level]
            if abs(d['dif']) < 10 and abs(d['dea']) < 10:
                if d['dif'] > d['dea']:
                    report.append(f"  {level}: 零轴金叉 → 极强形态，高胜率做多点")
                else:
                    report.append(f"  {level}: 零轴死叉 → 极弱形态，高胜率做空点")
    
    report.append("")
    report.append("="*70)
    return '\n'.join(report)


def analyze_macd_systematic(levels_macd, levels_55):
    """v4.2系统化MACD分析（简化版）"""
    return analyze_macd_systematic_core(levels_macd, levels_55)
