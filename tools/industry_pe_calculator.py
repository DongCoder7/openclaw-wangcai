#!/usr/bin/env python3
"""
A股行业平均PE查询工具 - 通用实现版
基于Tushare Pro API，但支持缓存和批量优化
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

class IndustryPECalculator:
    """
    行业PE计算器
    
    使用本地数据库缓存 + Tushare API补充的方式，高效获取行业PE数据
    """
    
    def __init__(self, db_path: str = None, tushare_token: str = None):
        """
        初始化
        
        参数:
            db_path: SQLite数据库路径，默认使用workspace下的historical.db
            tushare_token: Tushare Pro token
        """
        if db_path is None:
            self.db_path = '/root/.openclaw/workspace/data/historical/historical.db'
        else:
            self.db_path = db_path
        
        self.tushare_token = tushare_token
        self.pro = None
        self._industry_cache = {}  # 行业成分股缓存
        self._pe_cache = {}  # PE数据缓存
        
        self._init_db()
        self._init_tushare()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建行业PE缓存表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS industry_pe_cache (
                industry TEXT PRIMARY KEY,
                avg_pe REAL,
                median_pe REAL,
                min_pe REAL,
                max_pe REAL,
                sample_count INTEGER,
                trade_date TEXT,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建个股行业映射表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_industry (
                ts_code TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _init_tushare(self):
        """初始化Tushare"""
        if self.tushare_token:
            try:
                import tushare as ts
                ts.set_token(self.tushare_token)
                self.pro = ts.pro_api()
            except Exception as e:
                print(f"Tushare初始化失败: {e}")
    
    def get_stock_industry(self, ts_code: str) -> Optional[str]:
        """获取个股所属行业"""
        # 先查缓存
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT industry FROM stock_industry WHERE ts_code=?", (ts_code,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        
        # 缓存未命中，查Tushare
        if self.pro:
            try:
                df = self.pro.stock_basic(ts_code=ts_code, fields='ts_code,name,industry')
                if len(df) > 0:
                    industry = df.iloc[0]['industry']
                    name = df.iloc[0]['name']
                    
                    # 写入缓存
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO stock_industry (ts_code, name, industry) VALUES (?,?,?)",
                        (ts_code, name, industry)
                    )
                    conn.commit()
                    conn.close()
                    
                    return industry
            except Exception as e:
                print(f"获取个股行业失败: {e}")
        
        return None
    
    def get_industry_stocks(self, industry: str) -> List[str]:
        """获取某行业的所有股票代码"""
        if industry in self._industry_cache:
            return self._industry_cache[industry]
        
        if not self.pro:
            return []
        
        try:
            df = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,industry')
            industry_stocks = df[df['industry'] == industry]['ts_code'].tolist()
            self._industry_cache[industry] = industry_stocks
            return industry_stocks
        except Exception as e:
            print(f"获取行业股票列表失败: {e}")
            return []
    
    def get_stock_pe(self, ts_code: str, trade_date: str = None) -> Optional[float]:
        """获取个股PE"""
        cache_key = f"{ts_code}_{trade_date}"
        if cache_key in self._pe_cache:
            return self._pe_cache[cache_key]
        
        if not self.pro:
            return None
        
        try:
            if trade_date is None:
                # 获取最近交易日
                df_trade = self.pro.trade_cal(exchange='SSE', start_date='20250101', 
                                              end_date=datetime.now().strftime('%Y%m%d'))
                trade_date = df_trade[df_trade['is_open'] == 1]['cal_date'].max()
            
            df = self.pro.daily_basic(ts_code=ts_code, trade_date=trade_date, 
                                      fields='ts_code,pe_ttm')
            if len(df) > 0 and df.iloc[0]['pe_ttm'] is not None:
                pe_val = df.iloc[0]['pe_ttm']
                # 处理numpy类型
                if hasattr(pe_val, 'item'):
                    pe = float(pe_val.item())
                else:
                    pe = float(pe_val)
                if pe > 0:
                    self._pe_cache[cache_key] = pe
                    return pe
            else:
                # 如果最新日期没有数据，尝试前几天
                if trade_date:
                    for days_back in [1, 2, 3, 4, 5]:
                        try:
                            prev_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=days_back)).strftime('%Y%m%d')
                            df_prev = self.pro.daily_basic(ts_code=ts_code, trade_date=prev_date, 
                                                           fields='ts_code,pe_ttm')
                            if len(df_prev) > 0 and df_prev.iloc[0]['pe_ttm'] is not None:
                                pe_val = df_prev.iloc[0]['pe_ttm']
                                pe = float(pe_val.item()) if hasattr(pe_val, 'item') else float(pe_val)
                                if pe > 0:
                                    self._pe_cache[cache_key] = pe
                                    return pe
                        except:
                            continue
        except Exception as e:
            pass
        
        return None
    
    def calculate_industry_pe(self, industry: str, sample_size: int = 30,
                              force_update: bool = False) -> Dict:
        """
        计算行业PE统计数据
        
        参数:
            industry: 行业名称
            sample_size: 样本数量
            force_update: 强制更新缓存
        
        返回:
            Dict: {
                'industry': 行业名称,
                'avg_pe': 平均PE,
                'median_pe': 中位数PE,
                'min_pe': 最低PE,
                'max_pe': 最高PE,
                'sample_count': 样本数量,
                'trade_date': 数据日期,
                'stocks': [个股PE详情列表]
            }
        """
        # 检查缓存
        if not force_update:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT avg_pe, median_pe, min_pe, max_pe, sample_count, trade_date, update_time "
                "FROM industry_pe_cache WHERE industry=? "
                "AND update_time > datetime('now', '-1 day')",
                (industry,)
            )
            cached = cursor.fetchone()
            conn.close()
            
            if cached:
                return {
                    'industry': industry,
                    'avg_pe': cached[0],
                    'median_pe': cached[1],
                    'min_pe': cached[2],
                    'max_pe': cached[3],
                    'sample_count': cached[4],
                    'trade_date': cached[5],
                    'from_cache': True
                }
        
        # 获取行业股票
        stocks = self.get_industry_stocks(industry)
        if not stocks:
            return {'error': '无法获取行业股票列表'}
        
        # 获取PE数据
        pe_data = []
        trade_date = None
        
        for ts_code in stocks[:sample_size]:
            pe = self.get_stock_pe(ts_code, trade_date)
            if pe:
                pe_data.append({
                    'ts_code': ts_code,
                    'pe': pe
                })
                if trade_date is None:
                    # 记录数据日期
                    try:
                        df_trade = self.pro.trade_cal(exchange='SSE', start_date='20250101',
                                                      end_date=datetime.now().strftime('%Y%m%d'))
                        trade_date = df_trade[df_trade['is_open'] == 1]['cal_date'].max()
                    except:
                        pass
        
        if not pe_data:
            return {'error': '无法获取PE数据'}
        
        # 计算统计值
        pe_values = [d['pe'] for d in pe_data]
        avg_pe = sum(pe_values) / len(pe_values)
        median_pe = sorted(pe_values)[len(pe_values) // 2]
        min_pe = min(pe_values)
        max_pe = max(pe_values)
        
        result = {
            'industry': industry,
            'avg_pe': round(avg_pe, 2),
            'median_pe': round(median_pe, 2),
            'min_pe': round(min_pe, 2),
            'max_pe': round(max_pe, 2),
            'sample_count': len(pe_data),
            'trade_date': trade_date,
            'stocks': pe_data,
            'from_cache': False
        }
        
        # 写入缓存
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO industry_pe_cache 
            (industry, avg_pe, median_pe, min_pe, max_pe, sample_count, trade_date)
            VALUES (?,?,?,?,?,?,?)
        ''', (industry, avg_pe, median_pe, min_pe, max_pe, len(pe_data), trade_date))
        conn.commit()
        conn.close()
        
        return result
    
    def analyze_stock_valuation(self, ts_code: str, trade_date: str = None) -> Dict:
        """
        分析个股估值（对比行业）
        
        返回:
            Dict: {
                'ts_code': 股票代码,
                'name': 股票名称,
                'industry': 行业,
                'stock_pe': 个股PE,
                'industry_avg_pe': 行业平均PE,
                'industry_median_pe': 行业中位数PE,
                'percentile': 估值分位,
                'valuation': 估值判断,
                'suggested_pe_low': 建议保守PE,
                'suggested_pe_mid': 建议中性PE,
                'suggested_pe_high': 建议乐观PE
            }
        """
        # 获取个股行业
        industry = self.get_stock_industry(ts_code)
        if not industry:
            return {'error': '无法获取个股行业信息'}
        
        # 获取个股PE
        stock_pe = self.get_stock_pe(ts_code, trade_date)
        if not stock_pe:
            return {'error': '无法获取个股PE'}
        
        # 获取行业PE
        industry_data = self.calculate_industry_pe(industry)
        if 'error' in industry_data:
            return industry_data
        
        # 计算估值分位
        stock_pe_val = stock_pe
        pe_values = [s['pe'] for s in industry_data.get('stocks', [])]
        all_pe = sorted(pe_values + [stock_pe_val])
        percentile = (all_pe.index(stock_pe_val) + 1) / len(all_pe) * 100
        
        # 估值判断
        if percentile > 80:
            valuation = '高估'
            emoji = '🔴'
        elif percentile > 60:
            valuation = '偏高'
            emoji = '🟡'
        elif percentile > 40:
            valuation = '合理'
            emoji = '🟢'
        else:
            valuation = '低估'
            emoji = '🔵'
        
        return {
            'ts_code': ts_code,
            'industry': industry,
            'stock_pe': round(stock_pe, 2),
            'industry_avg_pe': industry_data['avg_pe'],
            'industry_median_pe': industry_data['median_pe'],
            'industry_min_pe': industry_data['min_pe'],
            'industry_max_pe': industry_data['max_pe'],
            'sample_count': industry_data['sample_count'],
            'percentile': round(percentile, 1),
            'valuation': f"{emoji} {valuation}",
            'vs_industry': round((stock_pe - industry_data['avg_pe']) / industry_data['avg_pe'] * 100, 1),
            'suggested_pe_low': round(industry_data['median_pe'] * 0.8, 0),
            'suggested_pe_mid': round(industry_data['median_pe'], 0),
            'suggested_pe_high': round(industry_data['median_pe'] * 1.2, 0),
            'trade_date': industry_data.get('trade_date')
        }
    
    def print_analysis(self, result: Dict):
        """打印分析报告"""
        if 'error' in result:
            print(f"❌ {result['error']}")
            return
        
        print("=" * 70)
        print(f"📊 {result['ts_code']} ({result['industry']}) 估值分析报告")
        print("=" * 70)
        
        print(f"\n【个股估值】")
        print(f"  PE_TTM: {result['stock_pe']}")
        
        print(f"\n【行业估值】（基于{result['sample_count']}只样本）")
        print(f"  行业平均PE: {result['industry_avg_pe']}")
        print(f"  行业中位数PE: {result['industry_median_pe']}")
        print(f"  行业最低PE: {result['industry_min_pe']}")
        print(f"  行业最高PE: {result['industry_max_pe']}")
        
        print(f"\n【估值对比】")
        vs = result['vs_industry']
        print(f"  个股 vs 行业平均: {'+' if vs > 0 else ''}{vs}%")
        print(f"  估值分位: {result['percentile']}%")
        print(f"  估值判断: {result['valuation']}")
        
        print(f"\n【目标PE建议】")
        print(f"  保守: {result['suggested_pe_low']:.0f}x")
        print(f"  中性: {result['suggested_pe_mid']:.0f}x")
        print(f"  乐观: {result['suggested_pe_high']:.0f}x")
        
        print("=" * 70)


# 使用示例
if __name__ == '__main__':
    # 初始化
    calc = IndustryPECalculator(
        tushare_token='cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'
    )
    
    # 分析个股
    result = calc.analyze_stock_valuation('300666.SZ')
    calc.print_analysis(result)
    
    # 批量分析多个行业
    print("\n" + "=" * 70)
    print("批量行业PE统计")
    print("=" * 70)
    
    industries = ['半导体', '白酒', '银行', '医药制造']
    for industry in industries:
        data = calc.calculate_industry_pe(industry)
        if 'error' not in data:
            print(f"\n{industry}:")
            print(f"  平均PE: {data['avg_pe']}")
            print(f"  中位数PE: {data['median_pe']}")
            print(f"  样本: {data['sample_count']}只")
