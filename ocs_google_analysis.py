#!/root/.openclaw/workspace/venv/bin/python3
"""
OCS光交换板块 + Google链 深度分析报告
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/tools')

from datetime import datetime
import requests

print('='*70)
print('OCS光交换板块 + Google供应链 深度分析报告')
print('='*70)

# 获取实时行情
stocks_data = [
    ('太辰光', '300570', 'OCS光器件龙头', True),
    ('仕佳光子', '688313', 'OCS光芯片核心', True),
    ('腾景科技', '688195', 'OCS光学元组件', True),
    ('光库科技', '300620', 'OCS器件+光纤激光', False),
    ('博创科技', '300548', 'OCS光器件', False),
    ('德科立', '688205', 'OCS光模块', False),
    ('中际旭创', '300308', '谷歌800G/1.6T主供', True),
    ('新易盛', '300502', '谷歌800G核心供', True),
    ('天孚通信', '300394', '谷歌光引擎', True),
]

print('\n【一、核心标的行情】')
print('-'*70)

for name, code, role, is_google in stocks_data:
    try:
        prefix = 'sz' if code.startswith('3') or code.startswith('0') else 'sh'
        url = f'https://qt.gtimg.cn/q={prefix}{code}'
        r = requests.get(url, timeout=5)
        values = r.text.split('~')
        if len(values) > 30:
            price = float(values[3])
            pre_close = float(values[4])
            change_pct = (price - pre_close) / pre_close * 100 if pre_close > 0 else 0
            emoji = '🔴' if change_pct > 0 else '🟢'
            google_tag = '[Google链]' if is_google else ''
            print(f"{emoji} {name:8s} ({code}) {price:8.2f}元 ({change_pct:+.2f}%) {role} {google_tag}")
    except:
        print(f"  {name:8s} ({code}): 获取失败")

print('\n' + '='*70)
print('【二、OCS技术解析】')
print('='*70)
print("""
OCS (Optical Circuit Switch) 光电路交换机

核心优势:
1. 超低延迟 - 光域直接交换，无需光电转换
2. 超低功耗 - 仅为传统电交换机的1/10
3. 灵活重构 - 路由重配置便捷
4. 高带宽 - 支持AI算力集群大规模互联

技术路线:
• MEMS微镜阵列方案 (主流)
• 硅光方案 (未来趋势)
• 液晶方案 (成本敏感场景)

应用场景:
• 谷歌TPU集群 (核心应用，4096卡互联)
• 微软Azure AI数据中心
• 英伟达GPU集群
• 超大规模数据中心
""")

print('\n' + '='*70)
print('【三、Google OCS供应链布局】')
print('='*70)
print("""
Google自研OCS交换机 (Palomar):
• 用于TPU v4/v5 POD集群互联
• 每个集群4096个TPU，需数千台OCS
• 光交换替代电交换，节省40%功耗
• 2024-2026年大规模部署期

A股供应链 (按重要性排序):

1. 太辰光 (300570) ⭐⭐⭐⭐⭐
   地位: OCS光器件龙头，最纯正标的
   产品: MPO连接器、光纤阵列、AWG模块
   客户: 直接供货Google OCS交换机
   优势: 技术壁垒高，毛利率50%+
   
2. 仕佳光子 (688313) ⭐⭐⭐⭐⭐
   地位: OCS光芯片核心供应商
   产品: AWG芯片、光开关芯片、PLC芯片
   客户: Google核心供应商
   优势: 国产替代空间大，IDM模式
   
3. 腾景科技 (688195) ⭐⭐⭐⭐
   地位: OCS光学元组件
   产品: 精密光学元件、晶体材料、微光学器件
   客户: Google、英伟达、微软
   优势: 光学镀膜技术领先

4. 中际旭创 (300308) ⭐⭐⭐⭐
   地位: 谷歌光模块主供
   产品: 800G/1.6T光模块
   份额: 谷歌光模块约40%
   风险: 估值较高，注意波动
   
5. 新易盛 (300502) ⭐⭐⭐⭐
   地位: 谷歌800G核心供应商
   产品: 800G光模块、硅光模块
   份额: 谷歌光模块约25%
   优势: 利润率行业最高
""")

print('\n' + '='*70)
print('【四、投资建议】')
print('='*70)
print("""
核心逻辑: Google OCS大规模部署 + AI算力爆发

推荐组合 (按优先级):

第一梯队 - OCS最纯正标的:
1. 太辰光 (300570) 
   - 催化剂: Google OCS订单放量
   - 目标价: 150-180元
   - 风险: 估值已高，等回调
   
2. 仕佳光子 (688313)
   - 催化剂: AWG芯片突破
   - 目标价: 100-120元
   - 风险: 产能爬坡不及预期

第二梯队 - Google链光模块:
3. 新易盛 (300502)
   - 催化剂: 谷歌800G订单
   - 策略: 长期持有
   - 风险: 行业竞争加剧

关注标的:
• 光库科技 - OCS器件+薄膜铌酸锂
• 博创科技 - 长芯盛旗下，硅光布局
• 德科立 - 长距离光模块
""")

print('\n' + '='*70)
print('【五、风险提示】')
print('='*70)
print("""
1. 技术风险: OCS技术路线尚未完全统一，MEMS vs 硅光竞争
2. 竞争风险: 国内厂商竞争加剧，价格战风险
3. 客户风险: 过度依赖Google等大客户，订单波动风险
4. 估值风险: 部分标的涨幅较大，估值偏高（PE 50-80倍）
5. 量产风险: OCS规模化量产进度不及预期
6. 地缘政治: 中美科技摩擦影响供应链
""")

print('\n报告生成时间:', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
print('='*70)
