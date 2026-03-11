#!/root/.openclaw/workspace/venv/bin/python3
"""
每日股票估值数据更新脚本
更新daily_basic数据（PE、PB、市值等）到本地数据库
用于支持行业PE分析器的本地数据查询
"""
import sqlite3
import pandas as pd
import tushare as ts
from datetime import datetime, timedelta
import time
import sys

# 配置
WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'
BATCH_SIZE = 100  # 每批处理100只股票

def log(msg):
    """记录日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()

def init_db():
    """初始化数据库表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建daily_basic表（如果不存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_basic (
            ts_code TEXT,
            trade_date TEXT,
            close REAL,
            turnover_rate REAL,
            turnover_rate_f REAL,
            volume_ratio REAL,
            pe REAL,
            pe_ttm REAL,
            pb REAL,
            ps REAL,
            ps_ttm REAL,
            dv_ratio REAL,
            dv_ttm REAL,
            total_share REAL,
            float_share REAL,
            free_share REAL,
            total_mv REAL,
            circ_mv REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    ''')
    
    conn.commit()
    conn.close()
    log("✅ 数据库表初始化完成")

def get_stock_list(pro):
    """获取所有上市股票列表"""
    try:
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        return df['ts_code'].tolist()
    except Exception as e:
        log(f"❌ 获取股票列表失败: {e}")
        return []

def get_trade_date(pro):
    """获取最近交易日"""
    try:
        today = datetime.now()
        start_date = (today - timedelta(days=10)).strftime('%Y%m%d')
        end_date = today.strftime('%Y%m%d')
        
        df = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
        trade_date = df[df['is_open'] == 1]['cal_date'].max()
        return trade_date
    except Exception as e:
        log(f"❌ 获取交易日失败: {e}")
        return None

def update_daily_basic(pro, trade_date, stock_list):
    """更新daily_basic数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total = len(stock_list)
    updated = 0
    failed = 0
    
    log(f"🔄 开始更新 {total} 只股票的估值数据（交易日: {trade_date}）")
    
    for i, ts_code in enumerate(stock_list):
        if i % 100 == 0:
            log(f"  进度: {i}/{total} | 成功: {updated} | 失败: {failed}")
        
        try:
            # 获取daily_basic数据
            df = pro.daily_basic(ts_code=ts_code, trade_date=trade_date)
            
            if len(df) > 0:
                row = df.iloc[0]
                
                # 插入或更新数据
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_basic 
                    (ts_code, trade_date, close, turnover_rate, turnover_rate_f, volume_ratio,
                     pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_share, float_share,
                     free_share, total_mv, circ_mv)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    row.get('ts_code'),
                    row.get('trade_date'),
                    row.get('close'),
                    row.get('turnover_rate'),
                    row.get('turnover_rate_f'),
                    row.get('volume_ratio'),
                    row.get('pe'),
                    row.get('pe_ttm'),
                    row.get('pb'),
                    row.get('ps'),
                    row.get('ps_ttm'),
                    row.get('dv_ratio'),
                    row.get('dv_ttm'),
                    row.get('total_share'),
                    row.get('float_share'),
                    row.get('free_share'),
                    row.get('total_mv'),
                    row.get('circ_mv')
                ))
                
                updated += 1
                
                # 每100条提交一次
                if updated % 100 == 0:
                    conn.commit()
            
            # 频率控制（Tushare限流200次/分钟）
            time.sleep(0.35)
            
        except Exception as e:
            failed += 1
            if failed % 10 == 1:  # 每10次失败记录一次
                log(f"  ⚠️ {ts_code} 获取失败: {str(e)[:50]}")
            time.sleep(0.5)
    
    conn.commit()
    conn.close()
    
    return updated, failed

def verify_update(trade_date):
    """验证更新结果"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT COUNT(*), COUNT(DISTINCT ts_code) FROM daily_basic WHERE trade_date=?",
        (trade_date,)
    )
    count, unique = cursor.fetchone()
    
    cursor.execute(
        "SELECT COUNT(*) FROM daily_basic WHERE trade_date=? AND pe_ttm IS NOT NULL",
        (trade_date,)
    )
    with_pe = cursor.fetchone()[0]
    
    conn.close()
    
    log(f"\n📊 更新验证:")
    log(f"  总记录数: {count}")
    log(f"  唯一股票数: {unique}")
    log(f"  有PE数据: {with_pe}")

def main():
    """主函数"""
    log("=" * 70)
    log("🚀 每日股票估值数据更新开始")
    log("=" * 70)
    
    # 初始化
    init_db()
    
    # 初始化Tushare
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    
    # 获取最近交易日
    trade_date = get_trade_date(pro)
    if not trade_date:
        log("❌ 无法获取交易日，退出")
        return
    log(f"📅 最近交易日: {trade_date}")
    
    # 获取股票列表
    stock_list = get_stock_list(pro)
    if not stock_list:
        log("❌ 无法获取股票列表，退出")
        return
    log(f"📋 获取到 {len(stock_list)} 只上市股票")
    
    # 检查是否已有数据
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM daily_basic WHERE trade_date=?",
        (trade_date,)
    )
    existing = cursor.fetchone()[0]
    conn.close()
    
    if existing >= len(stock_list) * 0.9:  # 如果已有90%以上的数据
        log(f"✅ 交易日 {trade_date} 的数据已存在（{existing}条），跳过更新")
        verify_update(trade_date)
        return
    
    # 更新数据
    updated, failed = update_daily_basic(pro, trade_date, stock_list)
    
    log(f"\n{'=' * 70}")
    log(f"✅ 更新完成")
    log(f"  成功: {updated} 只")
    log(f"  失败: {failed} 只")
    log(f"{'=' * 70}")
    
    # 验证
    verify_update(trade_date)

if __name__ == '__main__':
    main()
