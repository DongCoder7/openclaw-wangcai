#!/bin/bash
# 无用脚本清理清单 (待执行)
# 这些脚本已被新系统替代或重复

cd /root/.openclaw/workspace/tools

# 1. 测试脚本 - 可删除
echo "删除测试脚本..."
rm -f test_longbridge.py

# 2. 旧版数据补充脚本 - 已被 supplement_daily.py 和 skills/quant-data-system/scripts/* 替代
echo "删除旧版数据补充脚本..."
rm -f supplement_historical_factors_v2.py
rm -f supplement_batch_v3.py
rm -f supplement_fina_v2.py

# 3. 旧版计算脚本 - 已被 supplement_daily.py 整合
echo "删除旧版计算脚本..."
rm -f calc_factors_fast_batch.py
rm -f calc_factors_from_daily.py
rm -f calc_tech_batch.py
rm -f calc_tech_expand.py
rm -f calc_technical_from_local.py
rm -f calc_technical_full.py

# 4. 旧版获取脚本 - 功能重复
echo "删除旧版获取脚本..."
rm -f fetch_all_stocks_factors.py
rm -f fetch_history_fast.py
rm -f fetch_technical_history.py
rm -f fetch_tencent_data.py
rm -f fetch_tushare_factors.py
rm -f fetch_tushare_factors_fast.py
rm -f fetch_tushare_history.py
rm -f fetch_valuation_full.py

# 5. 旧版报告脚本 - 已被 skills/* 替代
echo "删除旧版报告脚本..."
rm -f ah_market_preopen.py
rm -f us_market_summary.py
rm -f daily_market_report.py

# 6. 早期版本系统 - 已被新架构替代
echo "删除早期版本系统..."
rm -f dounai_investment_system.py
rm -f simple_data_utils.py

# 7. 备份/压缩脚本
echo "删除工具脚本..."
rm -f md_compress.py

echo "清理完成!"
echo "剩余脚本数量: $(ls *.py 2>/dev/null | wc -l)"
