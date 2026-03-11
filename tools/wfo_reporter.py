#!/root/.openclaw/workspace/venv/bin/python3
"""
WFO结果汇报器 - 固定读取路径
支持: v5_advanced, v5_simple, heartbeat_wfo 结果
"""
import json
import os
from datetime import datetime

RESULT_DIR = '/root/.openclaw/workspace/quant/optimizer'

def get_latest_wfo_result():
    """获取最新的WFO结果 - 按优先级查找"""
    # 优先级1: v5_advanced (最完整)
    # 优先级2: v5_simple  
    # 优先级3: heartbeat_wfo
    
    patterns = [
        'wfo_v5_optimized_*.json',    # v5 advanced
        'wfo_v51_best_*.json',         # v5.1 simple
        'wfo_heartbeat_*.json',        # heartbeat
        'wfo_v5_best_*.json',          # v5 best
    ]
    
    all_files = []
    for pattern in patterns:
        prefix = pattern.split('*')[0]
        suffix = pattern.split('*')[1]
        for f in os.listdir(RESULT_DIR):
            if f.startswith(prefix) and f.endswith(suffix):
                # 获取文件修改时间
                mtime = os.path.getmtime(os.path.join(RESULT_DIR, f))
                all_files.append((f, mtime, pattern))
    
    if not all_files:
        return None
    
    # 按修改时间排序，取最新的
    all_files.sort(key=lambda x: x[1], reverse=True)
    latest_file = os.path.join(RESULT_DIR, all_files[0][0])
    
    print(f"[读取结果] {latest_file}")
    
    with open(latest_file, 'r') as f:
        data = json.load(f)
        data['_source_file'] = latest_file
        return data

def format_report(data):
    """格式化报告 - 支持多种结果格式"""
    if not data:
        return "❌ 未找到WFO结果"
    
    source = data.get('_source_file', '未知')
    
    # 处理v5_advanced格式
    if 'best_params' in data:
        params = data.get('best_params', {})
        result = data.get('result', {})
        yearly = result.get('yearly_returns', [])
        
        report = f"""📊 **WFO v5 Advanced 最新结果**
📁 来源: {source.split('/')[-1]}

**最优参数:**
- 因子权重: ret_20={params.get('ret_20_w')}, ret_60={params.get('ret_60_w')}, vol_20={params.get('vol_20_w')}, sharpe={params.get('sharpe_w')}
- 仓位: 牛市{params.get('bull_position', 0)*100:.0f}%, 熊市{params.get('bear_position', 0)*100:.0f}%
- 止损: {params.get('stop_loss', 0)*100:.0f}%, 调仓{params.get('rebalance_days')}天

**回测结果:**
- CAGR: **{result.get('cagr', 0)*100:.2f}%** ✅
- 最大回撤: {result.get('max_dd', 0)*100:.1f}%
- 胜率: {result.get('win_rate', 0)*100:.0f}%
- 综合评分: {result.get('score', 0):.2f}

**各周期收益:**"""
        
        for i, ret in enumerate(yearly, 1):
            emoji = "🟢" if ret > 0 else "🔴"
            report += f"\n- 周期{i}: {emoji} {ret*100:+.2f}%"
        
        return report
    
    # 处理heartbeat格式
    elif 'summary' in data and 'results' in data:
        summary = data.get('summary', {})
        results = data.get('results', [])
        
        report = f"""📊 **WFO Heartbeat 最新结果**
📁 来源: {source.split('/')[-1]}

**汇总:**
- CAGR: **{summary.get('cagr', 0)*100:.2f}%**
- 总收益: {summary.get('total_return', 0)*100:.2f}%

**各周期收益:**"""
        
        for r in results:
            ret = r.get('result', {}).get('total', 0)
            emoji = "🟢" if ret > 0 else "🔴"
            report += f"\n- 周期{r.get('period')}: {emoji} {ret*100:+.2f}% ({r.get('test', 'N/A')})"
        
        return report
    
    # 处理简单格式
    else:
        return f"📊 **WFO结果**\n📁 来源: {source}\n```json\n{json.dumps(data, indent=2)[:500]}\n```"

if __name__ == '__main__':
    data = get_latest_wfo_result()
    print(format_report(data))
