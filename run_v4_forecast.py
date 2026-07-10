#!/root/.openclaw/workspace/venv/bin/python3
"""
北京君正业务线拆分估值预测（使用配置好的v4.0 skill）
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/segmented-business-forecast/scripts')

from segmented_forecaster import V4Forecaster, FinancialData

# 创建分析器（强制确认年份2026）
f = V4Forecaster("300223.SZ", "北京君正", year=2026)

# 使用已验证的真实财报数据（2026Q1）
fin = FinancialData(
    year=2026, quarter=1,
    revenue=15.60,
    profit=3.19,
    margin=0.431,
    net_margin=0.204,
    source="Tushare Pro + 长桥API（已验证）"
)
f.financial_data = fin

# 验证数据
f.validate_data()

# 添加细分产品（强制evidence）
storage_total = 10.18
storage_dram = storage_total * 0.60
storage_sram = storage_total * 0.20
storage_nor = storage_total * 0.20

f.add_product("DRAM", storage_dram, 0.389, 0.10, 0.25,
    "7月2日调研纪要：DRAM涨价较多，Q1国内调价，Q2国内外跟涨；分货方式")
f.add_product("SRAM", storage_sram, 0.389, 0.15, 0.20,
    "7月2日调研纪要：DRAM供给紧张，部分客户转SRAM替代；Q2量价齐升")
f.add_product("NOR Flash", storage_nor, 0.389, 0.12, 0.18,
    "7月2日调研纪要：NOR Flash Q1/Q2连续涨价；2Gb车规已量产；AI服务器/光模块增长")
f.add_product("计算芯片(CPU/NPU)", 4.03, 0.519, 0.05, 0.35,
    "6月22日调研纪要：KGD缺货，控制出货节奏；Q1计算芯片增长近50%")
f.add_product("模拟与互联(LED/CAN/LIN)", 1.32, 0.509, 0.05, 0.05,
    "7月2日调研纪要：模拟芯片稳定增长，不受存储周期拉动")

# 预测
f.forecast()

# 打印报告
f.print_report()

# 保存报告
report = f.generate_markdown()
with open('/root/.openclaw/workspace/data/beijing_junzheng_v4_final.md', 'w', encoding='utf-8') as f_out:
    f_out.write(report)

print("\n✅ 报告已保存: data/beijing_junzheng_v4_final.md")
