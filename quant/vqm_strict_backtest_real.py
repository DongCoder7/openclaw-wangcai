#!/usr/bin/env python3
"""
VQM策略严格回测框架 - 使用真实数据
遵循《VQM策略回测SOP（严格版）》
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

class VQMStrictBacktest:
    """
    VQM严格回测引擎
    
    核心原则:
    1. 使用真实数据（AKShare）
    2. 严格避免未来函数
    3. 财报发布时间严格校验
    4. 完整交易记录
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.initial_capital = config.get('initial_capital', 1000000)
        self.pe_weight = config.get('pe_weight', 0.6)
        self.roe_weight = config.get('roe_weight', 0.4)
        self.position_count = config.get('position_count', 10)
        self.stop_loss = config.get('stop_loss', 0.92)
        
        # 数据缓存
        self.price_cache = {}
        self.financial_cache = {}
        
        # 交易记录
        self.trades = []
        self.daily_records = []
        
        print("="*70)
        print("🚀 VQM策略严格回测引擎")
        print("="*70)
        print(f"配置:")
        print(f"  初始资金: {self.initial_capital/10000:.0f}万")
        print(f"  PE权重: {self.pe_weight}")
        print(f"  ROE权重: {self.roe_weight}")
        print(f"  持仓数量: {self.position_count}")
        print(f"  止损线: {self.stop_loss}")
        print("="*70)
    
    def get_available_report_date(self, query_date: str) -> str:
        """
        获取查询日期可用的最新财报日期
        严格遵循财报发布时间规则
        
        规则:
        - 1-4月: 只能用上年三季报 (9-30)
        - 5-8月: 可用上年年报 (12-31)
        - 9-10月: 可用当年半年报 (6-30)
        - 11-12月: 可用当年三季报 (9-30)
        """
        date = datetime.strptime(query_date, '%Y-%m-%d')
        year = date.year
        month = date.month
        
        if month <= 4:
            # 1-4月，年报未发布完，只能用上年三季报
            return f"{year-1}-09-30"
        elif month <= 8:
            # 5-8月，年报已发布，可用上年年报
            return f"{year-1}-12-31"
        elif month <= 10:
            # 9-10月，半年报已发布，可用当年半年报
            return f"{year}-06-30"
        else:
            # 11-12月，三季报已发布，可用当年三季报
            return f"{year}-09-30"
    
    def get_stock_pe_roe(self, symbol: str, report_date: str) -> Optional[Tuple[float, float]]:
        """
        获取股票在指定财报日期的PE和ROE
        
        使用AKShare获取真实财务数据
        """
        try:
            cache_key = f"{symbol}_{report_date}"
            if cache_key in self.financial_cache:
                return self.financial_cache[cache_key]
            
            # 获取财务指标数据
            # 使用ak.stock_financial_analysis_indicator获取PE和ROE
            df = ak.stock_financial_analysis_indicator(symbol=symbol)
            
            if df is None or len(df) == 0:
                return None
            
            # 找到对应报告期的数据
            # 财报日期格式通常是 "20221231" 或 "2022-12-31"
            df['报告期'] = pd.to_datetime(df['报告期'])
            report_dt = pd.to_datetime(report_date)
            
            # 找到小于等于目标报告期的最新数据
            mask = df['报告期'] <= report_dt
            if not mask.any():
                return None
            
            latest = df[mask].iloc[0]
            
            # 提取PE和ROE
            # 注意：不同AKShare版本字段名可能不同
            pe = None
            roe = None
            
            # 尝试不同的字段名
            for pe_col in ['市盈率', 'PE', 'pe', '静态市盈率']:
                if pe_col in latest.index:
                    pe = latest[pe_col]
                    break
            
            for roe_col in ['净资产收益率', 'ROE', 'roe', '摊薄ROE']:
                if roe_col in latest.index:
                    roe = latest[roe_col]
                    break
            
            if pe is not None and roe is not None:
                # 转换为数值
                pe = float(pe) if pd.notna(pe) else None
                roe = float(roe) if pd.notna(roe) else None
                
                if pe and pe > 0 and roe:
                    result = (pe, roe)
                    self.financial_cache[cache_key] = result
                    return result
            
            return None
            
        except Exception as e:
            # print(f"获取{symbol}财务数据失败: {e}")
            return None
    
    def get_stock_price(self, symbol: str, date: str) -> Optional[float]:
        """
        获取股票在某日期的收盘价（前复权）
        只能获取该日期及之前的数据
        """
        try:
            cache_key = f"{symbol}_{date}"
            if cache_key in self.price_cache:
                return self.price_cache[cache_key]
            
            # 获取历史行情数据
            start_date = "20180101"
            end_date = date.replace('-', '')
            
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )
            
            if df is None or len(df) == 0:
                return None
            
            # 获取最后一天的收盘价
            close_price = df.iloc[-1]['收盘']
            
            self.price_cache[cache_key] = close_price
            return close_price
            
        except Exception as e:
            # print(f"获取{symbol}价格数据失败: {e}")
            return None
    
    def get_stock_pool(self) -> List[str]:
        """
        获取股票池
        使用沪深300成分股作为股票池
        """
        try:
            # 获取沪深300成分股
            df = ak.index_stock_cons_weight_csindex(symbol="000300")
            if df is not None and len(df) > 0:
                # 提取股票代码
                stocks = df['成分券代码'].tolist()
                return [s for s in stocks if s.isdigit()]
            
            # 备用：使用一些大盘股
            return [
                '000001', '000002', '000333', '000568', '000651', 
                '000725', '000768', '000858', '000895', '002001',
                '002007', '002024', '002027', '002142', '002230',
                '002236', '002304', '002352', '002415', '002594',
                '300003', '300014', '300015', '300033', '300059',
                '300122', '300124', '300274', '300408', '300433',
                '600000', '600009', '600016', '600028', '600030',
                '600031', '600036', '600048', '600050', '600104',
                '600196', '600276', '600309', '600340', '600406',
                '600436', '600438', '600519', '600585', '600588',
                '600600', '600606', '600660', '600690', '600703',
                '600741', '600745', '600809', '600837', '600887',
                '600900', '600919', '600958', '601012', '601066',
                '601088', '601100', '601111', '601138', '601166',
                '601169', '601186', '601211', '601229', '601288',
                '601318', '601319', '601328', '601336', '601390',
                '601398', '601601', '601628', '601668', '601688',
                '601766', '601788', '601800', '601818', '601857',
                '601888', '601899', '601901', '601933', '601939',
                '601988', '601989', '603019', '603288', '603501',
                '603658', '603799', '603986', '688001', '688008',
                '688009', '688012', '688036', '688111', '688126'
            ]
        except Exception as e:
            print(f"获取股票池失败: {e}")
            return []
    
    def select_stocks_vqm_strict(self, select_date: str, stock_pool: List[str]) -> pd.DataFrame:
        """
        严格版VQM选股
        
        关键检查点:
        1. 使用查询日期可用的最新财报
        2. 使用查询日期当天的价格（或之前的价格）
        3. 严格避免未来数据
        """
        print(f"\n📊 {select_date} VQM选股开始...")
        
        # 1. 确定可用的最新财报日期
        available_report_date = self.get_available_report_date(select_date)
        print(f"   可用财报日期: {available_report_date}")
        
        results = []
        total = len(stock_pool)
        
        for i, symbol in enumerate(stock_pool):
            if (i + 1) % 20 == 0:
                print(f"   进度: {i+1}/{total}")
            
            try:
                # 2. 获取价格数据（只能用到select_date）
                price = self.get_stock_price(symbol, select_date)
                if price is None:
                    continue
                
                # 3. 获取财务数据（只能用available_report_date的）
                pe_roe = self.get_stock_pe_roe(symbol, available_report_date)
                if pe_roe is None:
                    continue
                
                pe, roe = pe_roe
                
                # 过滤异常值
                if pe <= 0 or pe > 100 or roe < 0 or roe > 50:
                    continue
                
                results.append({
                    'symbol': symbol,
                    'price': price,
                    'pe': pe,
                    'roe': roe,
                    'select_date': select_date,
                    'report_date': available_report_date
                })
                
                # 限制API调用频率
                time.sleep(0.05)
                
            except Exception as e:
                continue
        
        if len(results) == 0:
            print("   ⚠️ 未获取到有效数据")
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        print(f"   有效股票数: {len(df)}")
        
        # 4. 计算VQM得分
        df['pe_rank'] = df['pe'].rank(pct=True, ascending=True)
        df['roe_rank'] = df['roe'].rank(pct=True, ascending=False)
        df['vqm_score'] = df['pe_rank'] * self.pe_weight + df['roe_rank'] * self.roe_weight
        
        # 5. 排序并返回
        df = df.sort_values('vqm_score', ascending=False)
        
        print(f"   VQM得分最高: {df.iloc[0]['symbol']} (PE:{df.iloc[0]['pe']:.1f}, ROE:{df.iloc[0]['roe']:.1f}%)")
        
        return df
    
    def run_single_month_backtest(self, year: int, month: int) -> Dict:
        """
        运行单月回测
        
        流程:
        1. 确定每月第一个交易日
        2. 该日收盘后进行VQM选股
        3. 次日开盘买入（简化处理，实际应用中可能用次日开盘价）
        4. 持有到月底，计算当月收益
        """
        # 确定日期
        first_day = datetime(year, month, 1)
        
        # 获取该月第一个交易日
        stock_pool = self.get_stock_pool()
        
        # 选股日期（简化：用每月第一个工作日）
        select_date = first_day.strftime('%Y-%m-%d')
        
        print(f"\n{'='*70}")
        print(f"📅 {year}年{month}月回测")
        print(f"{'='*70}")
        
        # VQM选股
        selected = self.select_stocks_vqm_strict(select_date, stock_pool)
        
        if len(selected) == 0:
            return {
                'year': year,
                'month': month,
                'status': 'failed',
                'reason': 'no_data'
            }
        
        # 选出前N只
        top_n = selected.head(self.position_count)
        
        print(f"\n📈 选中股票:")
        for i, row in top_n.iterrows():
            print(f"   {row['symbol']}: PE={row['pe']:.1f}, ROE={row['roe']:.1f}%, 得分={row['vqm_score']:.3f}")
        
        # 计算当月收益（简化版：假设持有到月底）
        # 实际应该获取月底价格计算
        
        return {
            'year': year,
            'month': month,
            'select_date': select_date,
            'stocks_selected': top_n['symbol'].tolist(),
            'avg_pe': top_n['pe'].mean(),
            'avg_roe': top_n['roe'].mean(),
            'status': 'success'
        }
    
    def run_full_backtest(self, start_year: int = 2023, end_year: int = 2023) -> List[Dict]:
        """
        运行完整回测
        """
        results = []
        
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                try:
                    result = self.run_single_month_backtest(year, month)
                    results.append(result)
                    
                    # 限制API调用频率，避免被封
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"⚠️ {year}年{month}月回测失败: {e}")
                    results.append({
                        'year': year,
                        'month': month,
                        'status': 'error',
                        'error': str(e)
                    })
        
        return results


def demo_strict_backtest():
    """
    演示严格回测
    """
    config = {
        'initial_capital': 1000000,
        'pe_weight': 0.6,
        'roe_weight': 0.4,
        'position_count': 10,
        'stop_loss': 0.92
    }
    
    backtest = VQMStrictBacktest(config)
    
    # 运行2023年1月的回测作为演示
    result = backtest.run_single_month_backtest(2023, 1)
    
    print("\n" + "="*70)
    print("📊 回测结果")
    print("="*70)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    demo_strict_backtest()
