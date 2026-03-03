#!/usr/bin/env python3
"""
Heartbeat任务调度器 - 整点策略效果汇报
使用新的汇报格式：策略组合 + 因子使用 + 后续优化点
"""
import json
import os
import subprocess
import sqlite3
from datetime import datetime
import sys

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
OPT_PATH = f'{WORKSPACE}/quant/optimizer'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

def send_message(message):
    """发送消息到Feishu"""
    try:
        result = subprocess.run(
            ['openclaw', 'message', 'send', '--channel', 'feishu', '--target', USER_ID, '--message', message],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"发送失败: {e}")
        return False

def get_latest_strategy():
    """获取最新策略结果 - 优先读取WFO v5结果"""
    
    # 【修正】首先查找WFO v5结果 - 最高优先级
    wfo_v5_files = [f for f in os.listdir(OPT_PATH) if f.startswith('wfo_v5_optimized_') and f.endswith('.json')]
    if wfo_v5_files:
        wfo_v5_files.sort(reverse=True)
        latest_file = f'{OPT_PATH}/{wfo_v5_files[0]}'
        print(f"[策略读取] 找到WFO v5结果: {wfo_v5_files[0]}")
        with open(latest_file, 'r') as f:
            data = json.load(f)
        # 提取关键参数
        params = data.get('best_params', {})
        result = data.get('result', {})
        yearly = result.get('yearly_returns', [])
        cagr = result.get('cagr', 0)
        # 构建因子权重字典
        factor_weights = {}
        if params.get('ret_20_w'): factor_weights['ret_20'] = params.get('ret_20_w')
        if params.get('ret_60_w'): factor_weights['ret_60'] = params.get('ret_60_w')
        if params.get('vol_20_w'): factor_weights['vol_20'] = params.get('vol_20_w')
        if params.get('sharpe_w'): factor_weights['sharpe_like'] = params.get('sharpe_w')
        # 取前3个因子
        top_factors = [{'factor': k, 'weight': v} for k, v in sorted(factor_weights.items(), key=lambda x: abs(x[1]), reverse=True)[:3]]
        return {
            'version': 'v5_advanced',
            'params': params,
            'yearly': yearly,
            'avg_return': cagr,
            'top_factors': top_factors,
            'factor_weights': factor_weights,
            'factor_count': len(factor_weights),
            'source_file': wfo_v5_files[0]
        }
    
    # 【修正】其次查找wfo_v51_best结果
    wfo_v51_files = [f for f in os.listdir(OPT_PATH) if f.startswith('wfo_v51_best_') and f.endswith('.json')]
    if wfo_v51_files:
        wfo_v51_files.sort(reverse=True)
        print(f"[策略读取] 找到WFO v5.1结果: {wfo_v51_files[0]}")
        with open(f'{OPT_PATH}/{wfo_v51_files[0]}', 'r') as f:
            data = json.load(f)
        params = data.get('best_params', {})
        weights = params.get('weights', {})
        top_factors = [{'factor': k, 'weight': v} for k, v in sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True)[:3]]
        return {
            'version': 'v5.1',
            'params': params,
            'yearly': data.get('yearly', []),
            'avg_return': data.get('cagr', 0),
            'top_factors': top_factors,
            'factor_weights': weights,
            'factor_count': len(weights),
            'source_file': wfo_v51_files[0]
        }
    
    # 查找v26结果
    v26_files = [f for f in os.listdir(OPT_PATH) if f.startswith('v26_result_') and f.endswith('.json')]
    if v26_files:
        v26_files.sort(reverse=True)
        with open(f'{OPT_PATH}/{v26_files[0]}', 'r') as f:
            data = json.load(f)
        factor_count = data.get('factor_count', len(data.get('factors_used', [])))
        return {
            'version': 'v26',
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': [{'factor': f} for f in data.get('factors_used', [])][:3],
            'factor_weights': {f: 1.0 for f in data.get('factors_used', [])},
            'factor_count': factor_count
        }
    
    # 查找增强优化器结果
    enhanced_files = []
    for f in os.listdir(OPT_PATH):
        if f.startswith('enhanced_optimizer_v') and f.endswith('.json'):
            enhanced_files.append(f)
    
    if enhanced_files:
        enhanced_files.sort(reverse=True)
        with open(f'{OPT_PATH}/{enhanced_files[0]}', 'r') as f:
            data = json.load(f)
        return {
            'version': enhanced_files[0].split('_')[2],
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': data.get('top_factors', [])[:3],
            'factor_weights': data.get('factor_weights', {}),
        }
    
    # 查找v25结果
    v25_files = [f for f in os.listdir(OPT_PATH) if f.startswith('v25_result_') and f.endswith('.json')]
    if v25_files:
        v25_files.sort(reverse=True)
        with open(f'{OPT_PATH}/{v25_files[0]}', 'r') as f:
            data = json.load(f)
        return {
            'version': 'v25',
            'params': data.get('params', {}),
            'yearly': data.get('yearly_returns', []),
            'avg_return': data.get('avg_return', 0),
            'top_factors': data.get('top_factors', [])[:3],
            'factor_weights': data.get('factor_weights', {}),
        }
    
    return None

def get_factor_usage():
    """获取因子使用情况"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_factors WHERE trade_date >= "20250101"')
    sf = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_defensive_factors WHERE trade_date >= "20250101"')
    sdf = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM stock_fina')
    fina = cursor.fetchone()[0]
    
    conn.close()
    
    return {'tech': sf, 'def': sdf, 'fina': fina, 'total': 26}

def check_supplement_progress():
    """检查数据回补进度 - 整点汇报"""
    try:
        # 1. 检查回补进程状态
        result = subprocess.run(
            ['pgrep', '-f', 'supplement_batch_v2|supplement_daemon'],
            capture_output=True, text=True, timeout=5
        )
        is_running = result.returncode == 0 and result.stdout.strip()
        
        # 2. 查询数据库获取各年度数据量
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        yearly_data = {}
        for year in [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]:
            cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT ts_code) 
                FROM fina_tushare 
                WHERE period LIKE ?
            """, (f'{year}%',))
            records, stocks = cursor.fetchone()
            yearly_data[str(year)] = {'records': records, 'stocks': stocks}
        
        conn.close()
        
        # 3. 计算总体进度
        total_stocks = sum(d['stocks'] for d in yearly_data.values())
        total_records = sum(d['records'] for d in yearly_data.values())
        
        # 4. 构建汇报消息
        lines = []
        lines.append("📊 **数据回补进度**")
        lines.append("")
        
        # 进程状态
        status_emoji = "🟢" if is_running else "🔴"
        lines.append(f"【守护进程状态】")
        lines.append(f"  状态: {status_emoji} {'运行中' if is_running else '已停止'}")
        if is_running:
            pid = result.stdout.strip().split('\n')[0]
            lines.append(f"  PID: {pid}")
        lines.append("")
        
        # 年度进度
        lines.append("【年度数据进度】")
        target_stocks = 5000
        for year in ['2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025']:
            data = yearly_data[year]
            stocks = data['stocks']
            records = data['records']
            percent = (stocks / target_stocks) * 100 if target_stocks > 0 else 0
            
            # 进度条
            filled = int(percent / 10)
            bar = '█' * filled + '░' * (10 - filled)
            
            # 状态判断
            if percent >= 100:
                status = "✅"
            elif percent >= 50:
                status = "🟢"
            elif percent >= 20:
                status = "🟡"
            else:
                status = "🔴"
            
            lines.append(f"  {year}: {bar} {stocks}/{target_stocks} ({percent:.1f}%) {status} | {records}条")
        
        lines.append("")
        lines.append(f"【总体统计】")
        lines.append(f"  总计股票: {total_stocks}只")
        lines.append(f"  总计记录: {total_records}条")
        
        # 如果进程未运行，添加警告
        if not is_running:
            lines.append("")
            lines.append("⚠️ **警告**: 数据回补进程已停止")
            lines.append("  建议重启: `python3 tools/supplement_batch_v2.py`")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"⚠️ 数据回补进度检查失败: {str(e)[:100]}"


def generate_strategy_report():
    """生成策略效果报告 - 使用get_latest_strategy()读取正确路径"""
    from datetime import datetime
    
    now = datetime.now()
    
    # 【修正】使用get_latest_strategy()获取正确的策略结果
    strategy = get_latest_strategy()
    
    if not strategy:
        return f"📊 **整点汇报** ({now.strftime('%H:%M')})\n\n未找到策略优化结果"
    
    # 生成报告
    lines = [
        f"📊 **策略状态汇报** ({now.strftime('%H:%M')})",
        "",
        f"**版本**: {strategy.get('version', 'unknown')}",
        f"**源文件**: {strategy.get('source_file', 'N/A')}",
        "",
        "**【当前策略组合】**",
    ]
    
    # 显示因子权重
    factor_weights = strategy.get('factor_weights', {})
    top_factors = strategy.get('top_factors', [])
    
    if top_factors:
        lines.append(f"**核心因子**: {len(factor_weights)}个")
        for f in top_factors[:5]:
            factor_name = f.get('factor', 'N/A')
            weight = f.get('weight', 0)
            lines.append(f"- {factor_name}: {weight:.3f}")
    
    # 显示回测表现
    yearly = strategy.get('yearly', [])
    avg_return = strategy.get('avg_return', 0)
    
    lines.extend([
        "",
        "**【回测表现】**",
    ])
    
    if yearly and len(yearly) > 0:
        # 显示年度收益
        for i, ret in enumerate(yearly[-6:]):  # 最近6个周期
            if isinstance(ret, (int, float)):
                emoji = "🟢" if ret > 0 else "🔴"
                lines.append(f"{emoji} 周期{i+1}: {ret*100:+.2f}%")
    
    # 显示年化收益
    if avg_return:
        cagr_pct = avg_return * 100 if avg_return < 1 else avg_return
        emoji = "🟢" if cagr_pct > 0 else "🔴"
        lines.append(f"{emoji} 年化CAGR: {cagr_pct:+.2f}%")
    
    lines.extend([
        "",
        "**【因子使用情况】**",
        f"- 已采用因子: {len(factor_weights)}个",
    ])
    
    return "\n".join(lines)

def git_sync():
    """同步git变更 - 使用简单快速的方式"""
    try:
        # 快速检查
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=5
        )
        
        if not result.stdout.strip():
            return None
        
        # 提交并推送
        subprocess.run(['git', 'add', '-A'], cwd=WORKSPACE, capture_output=True, timeout=5)
        commit_msg = f"🫘 {datetime.now().strftime('%H:%M')} Heartbeat"
        subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=WORKSPACE, capture_output=True, timeout=5
        )
        
        # 异步推送
        subprocess.Popen(
            ['git', 'push'],
            cwd=WORKSPACE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return "已同步"
    except Exception as e:
        return f"失败: {str(e)[:50]}"

def is_hour_start():
    """检查是否为整点"""
    return datetime.now().minute == 0


def run_us_market_report():
    """执行美股报告任务 - 08:30"""
    try:
        print("🌙 执行美股报告任务...")
        script = f'{WORKSPACE}/skills/us-market-analysis/scripts/generate_report_longbridge.py'

        # 加载长桥API环境变量
        env = os.environ.copy()
        env_file = f'{WORKSPACE}/.longbridge.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        env[key] = value

        result = subprocess.run(
            ['python3', script],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=120,
            env=env
        )
        if result.returncode == 0:
            return "✅ 美股报告已生成并发送"
        else:
            return f"❌ 美股报告失败: {result.stderr[:100]}"
    except Exception as e:
        return f"❌ 美股报告异常: {str(e)[:100]}"


def run_ah_preopen_report():
    """执行A+H开盘前瞻任务 - 09:20"""
    try:
        print("🌅 执行A+H开盘前瞻任务...")
        script = f'{WORKSPACE}/skills/ah-market-preopen/scripts/generate_report_longbridge.py'
        
        # 加载长桥API环境变量（和美股报告保持一致）
        env = os.environ.copy()
        env_file = f'{WORKSPACE}/.longbridge.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        env[key] = value
        
        result = subprocess.run(
            ['python3', script],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=120,
            env=env
        )
        if result.returncode == 0:
            return "✅ A+H开盘前瞻已生成并发送"
        else:
            return f"❌ A+H开盘前瞻失败: {result.stderr[:100]}"
    except Exception as e:
        return f"❌ A+H开盘前瞻异常: {str(e)[:100]}"


def run_zsxq_fetcher():
    """执行知识星球日终抓取任务 - 23:30"""
    try:
        print("📚 执行知识星球日终抓取任务...")
        script = f'{WORKSPACE}/tools/zsxq_fetcher_prod.py'
        
        result = subprocess.run(
            ['python3', script],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            return "✅ 知识星球日终抓取已完成"
        else:
            return f"❌ 知识星球抓取失败: {result.stderr[:100]}"
    except Exception as e:
        return f"❌ 知识星球抓取异常: {str(e)[:100]}"


def run_sim_portfolio():
    """执行模拟盘交易任务 - 15:30"""
    try:
        print("💼 执行模拟盘交易任务...")
        script = f'{WORKSPACE}/skills/quant-data-system/scripts/sim_portfolio.py'
        
        result = subprocess.run(
            ['python3', script],
            cwd=WORKSPACE,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return "✅ 模拟盘交易已执行"
        else:
            return f"❌ 模拟盘交易失败: {result.stderr[:100]}"
    except Exception as e:
        return f"❌ 模拟盘交易异常: {str(e)[:100]}"


def run_wfo_optimizer():
    """运行WFO优化器"""
    try:
        wfo_optimizer = f'{WORKSPACE}/tools/heartbeat_wfo_optimizer.py'
        if os.path.exists(wfo_optimizer):
            result = subprocess.run(
                ['python3', wfo_optimizer],
                cwd=WORKSPACE,
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                return "WFO优化完成"
            else:
                return f"WFO优化出错: {result.stderr[:100]}"
        else:
            return "WFO优化器不存在"
    except Exception as e:
        return f"WFO优化异常: {str(e)[:100]}"

def generate_wfo_report():
    """生成WFO详细报告"""
    # 查找最新的WFO结果
    wfo_files = [f for f in os.listdir(OPT_PATH) if f.startswith('wfo_heartbeat_') and f.endswith('.json')]
    
    if not wfo_files:
        return "⚠️ 暂无WFO优化结果"
    
    # 按时间排序，取最新
    wfo_files.sort(reverse=True)
    latest_file = f'{OPT_PATH}/{wfo_files[0]}'
    
    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        # 构建详细报告
        report_lines = [
            "📊 **WFO优化详细报告**",
            "",
            f"**生成时间**: {data.get('generated_at', 'N/A')[:19]}",
            f"**数据文件**: {wfo_files[0]}",
            "",
            "**【最优权重配置】**",
        ]
        
        weights = data.get('weights', {})
        for factor, weight in sorted(weights.items()):
            report_lines.append(f"- {factor}: {weight:.3f}")
        
        report_lines.extend([
            "",
            "**【WFO回测结果】** (2018-2025)",
        ])
        
        periods = data.get('periods', [])
        for p in periods:
            year = p.get('year', 'N/A')
            ret = p.get('return', 0) * 100
            emoji = "🟢" if ret > 0 else "🔴" if ret < -10 else "⚪"
            report_lines.append(f"{emoji} {year}年: {ret:+.2f}%")
        
        years = data.get('years', len(periods))
        cagr = data.get('cagr', 0) * 100
        
        # 计算累计收益
        total_ret = 1.0
        for p in periods:
            total_ret *= (1 + p.get('return', 0))
        total_ret = (total_ret - 1) * 100
        
        report_lines.extend([
            "",
            f"**【汇总统计】**",
            f"- 回测年数: {years}年",
            f"- 累计收益: {total_ret:+.2f}%",
            f"- 年化CAGR: {cagr:+.2f}%",
        ])
        
        return "\n".join(report_lines)
        
    except Exception as e:
        return f"⚠️ 生成报告失败: {str(e)[:100]}"


def run_optimizer_if_needed():
    """检查并运行优化器 - 持续寻找最佳组合"""
    # 检查是否已有优化器在运行
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'heartbeat_wfo_optimizer|enhanced_optimizer|smart_optimizer'],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            print("⏭️ 优化器已在运行，跳过")
            return "已在运行"
    except:
        pass
    
    # 检查最新结果时间
    try:
        latest_time = None
        for f in os.listdir(OPT_PATH):
            if f.endswith('.json') and ('wfo_heartbeat' in f or 'result' in f or 'enhanced' in f):
                # 从文件名提取时间
                import re
                match = re.search(r'\d{8}_\d{6}', f)
                if match:
                    ts = match.group()
                    if latest_time is None or ts > latest_time:
                        latest_time = ts
        
        if latest_time:
            from datetime import datetime, timedelta
            last_dt = datetime.strptime(latest_time, '%Y%m%d_%H%M%S')
            hours_passed = (datetime.now() - last_dt).total_seconds() / 3600
            
            # 每4小时运行一次优化
            if hours_passed < 4:
                print(f"⏭️ 上次优化距今{hours_passed:.1f}小时，跳过")
                return f"{hours_passed:.1f}小时前已优化"
    except Exception as e:
        print(f"检查时间失败: {e}")
    
    # 启动WFO优化器（后台运行）
    print("🚀 启动WFO优化器...")
    try:
        wfo_optimizer = f'{WORKSPACE}/tools/heartbeat_wfo_optimizer.py'
        if os.path.exists(wfo_optimizer):
            subprocess.Popen(
                ['python3', wfo_optimizer],
                cwd=WORKSPACE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return "已启动 WFO优化器"
    except Exception as e:
        return f"启动失败: {e}"
    
    return "未找到优化器"

def main():
    now = datetime.now()
    print(f"🫘 Heartbeat检查 - {now.strftime('%H:%M:%S')}")
    
    # 08:30 美股报告
    if now.hour == 8 and now.minute == 30:
        print("🌙 08:30 执行美股报告...")
        us_status = run_us_market_report()
        send_message(f"📊 **美股报告执行**: {us_status}")
    
    # 09:20 A+H开盘前瞻
    if now.hour == 9 and now.minute == 20:
        print("🌅 09:20 执行A+H开盘前瞻...")
        ah_status = run_ah_preopen_report()
        send_message(f"📊 **A+H开盘前瞻执行**: {ah_status}")
    
    # 23:30 知识星球日终抓取
    if now.hour == 23 and now.minute == 30:
        print("📚 23:30 执行知识星球日终抓取...")
        zsxq_status = run_zsxq_fetcher()
        send_message(f"📚 **知识星球日终抓取**: {zsxq_status}")
    
    # 15:30 模拟盘
    if now.hour == 15 and now.minute == 30:
        print("💼 15:30 执行模拟盘...")
        sim_status = run_sim_portfolio()
        send_message(f"📊 **模拟盘执行**: {sim_status}")
    
    # === 每次Heartbeat都运行WFO优化器（后台） ===
    print("🚀 检查WFO优化器状态...")
    wfo_status = run_optimizer_if_needed()  # 改为检查/启动模式，避免重复运行
    print(f"   优化器状态: {wfo_status}")
    
    # 非整点跳过所有汇报
    if not is_hour_start():
        print(f"⏱️ 非整点({now.minute}分)，跳过汇报")
        return
    
    print(f"🕐 整点汇报 - {now.hour}:00")
    
    # 生成并发送数据回补进度报告
    print("📊 检查数据回补进度...")
    supplement_report = check_supplement_progress()
    print(supplement_report)
    send_message(supplement_report)
    
    # 生成并发送策略报告（使用正确的WFO v5路径）
    print("📊 生成策略效果报告...")
    report = generate_strategy_report()
    print(report)
    send_message(report)
    
    # Git同步
    git_result = git_sync()
    if git_result:
        git_msg = f"🔄 **Git同步**: {git_result}"
        print(git_msg)
        send_message(git_msg)
    
    print("✅ Heartbeat完成")

if __name__ == "__main__":
    main()
