#!/bin/bash
# 分段并行计算 - 2026年因子
# 启动4个独立进程，分别计算不同日期段

cd /root/.openclaw/workspace

echo "启动4个分段计算进程..."

# 分段1: 1月上半月
python3 -c "
import sys
sys.path.insert(0, 'tools')
from calc_factors_segment import calc_segment
calc_segment('20260101', '20260115', 'seg1')" > logs/seg1.log 2>&1 &

# 分段2: 1月下半月  
python3 -c "
import sys
sys.path.insert(0, 'tools')
from calc_factors_segment import calc_segment
calc_segment('20260116', '20260131', 'seg2')" > logs/seg2.log 2>&1 &

# 分段3: 2月上半月
python3 -c "
import sys
sys.path.insert(0, 'tools')
from calc_factors_segment import calc_segment
calc_segment('20260201', '20260215', 'seg3')" > logs/seg3.log 2>&1 &

# 分段4: 2月下半月+3月
python3 -c "
import sys
sys.path.insert(0, 'tools')
from calc_factors_segment import calc_segment
calc_segment('20260216', '20260302', 'seg4')" > logs/seg4.log 2>&1 &

echo "4个分段进程已启动"
