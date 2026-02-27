#!/usr/bin/env python3
"""
个股数据收集器 - A股深度分析专用
整合Tushare Pro + 新浪财经 + 因子重新计算
"""

import tushare as ts
import requests
import pandas as pd
import numpy as np
import json
import sys
from datetime import datetime, timedelta

# Tushare Token
TUSHARE_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'

class StockDataCollector:
    """
    个股数据收集器
    
    使用方法:
        collector = StockDataCollector()
        data = collector.get_full_data('600875.SH')
    """
    
    def __init__(self, token=TUSHARE_TOKEN):
        ts.set_token(token)
        self.pro = ts.pro_api()
    
    def get_price_cross_verify(self, ts_code):
        """
        多源交叉验证股价
        
        Returns:
            dict: {
                'tushare': {...},
                'sina': {...},
                'verified': bool,
                'final_price': float
            }
        """
        results = {'sources': []}
        
        # 1. Tushare Pro
        try:
            df = self.pro.daily(ts_code=ts_code, limit=1)
            if not df.empty:
                results['tushare'] = {
                    'close': df.iloc[0]['close'],
                    'open': df.iloc[0]['open'],
                    'high': df.iloc[0]['high'],
                    'low': df.iloc[0]['low'],
                    'pct_chg': df.iloc[0]['pct_chg'],
                    'vol': df.iloc[0]['vol'],
                    'amount': df.iloc[0]['amount'],
                    'trade_date': df.iloc[0]['trade_date']
                }
                results['sources'].append('tushare')
        except Exception as e:
            print(f"Tushare获取失败: {e}")
        
        # 2. 新浪财经
        try:
            code = ts_code.lower().replace('.sz', '').replace('.sh', '')
            prefix = 'sz' if ts_code.endswith('.SZ') else 'sh'
            url = f'https://hq.sinajs.cn/list={prefix}{code}'
            headers = {'Referer': 'https://finance.sina.com.cn'}
            r = requests.get(url, headers=headers, timeout=10)
            data = r.text.split('"')[1].split(',')
            
            results['sina'] = {
                'name': data[0],
                'open': float(data[1]),
                'close': float(data[3]),
                'high': float(data[4]),
                'low': float(data[5]),
                'vol': int(data[8]),
                'amount': float(data[9])
            }
            results['sources'].append('sina')
        except Exception as e:
            print(f"新浪财经获取失败: {e}")
        
        # 3. 交叉验证
        if 'tushare' in results and 'sina' in results:
            diff = abs(results['tushare']['close'] - results['sina']['close'])
            results['verified'] = diff < 0.01
            results['final_price'] = results['tushare']['close']
            results['price_diff'] = diff
        elif 'tushare' in results:
            results['verified'] = True
            results['final_price'] = results['tushare']['close']
        elif 'sina' in results:
            results['verified'] = True
            results['final_price'] = results['sina']['close']
        else:
            results['verified'] = False
            results['final_price'] = None
        
        return results
    
    def get_basic_info(self, ts_code):
        """获取基本信息"""
        try:
            df = self.pro.stock_basic(ts_code=ts_code)
            if not df.empty:
                return df.iloc[0].to_dict()
        except Exception as e:
            print(f"基本信息获取失败: {e}")
        return {}
    
    def get_valuation(self, ts_code):
        """获取估值数据"""
        try:
            df = self.pro.daily_basic(ts_code=ts_code)
            if not df.empty:
                return {
                    'pe_ttm': df.iloc[0]['pe_ttm'],
                    'pb': df.iloc[0]['pb'],
                    'ps_ttm': df.iloc[0]['ps_ttm'],
                    'total_mv': df.iloc[0]['total_mv'] / 1e8,  # 亿
                    'circ_mv': df.iloc[0]['circ_mv'] / 1e8,
                    'turnover_rate': df.iloc[0]['turnover_rate'],
                    'dv_ttm': df.iloc[0]['dv_ttm']
                }
        except Exception as e:
            print(f"估值数据获取失败: {e}")
        return {}
    
    def get_financial_data(self, ts_code):
        """获取财务数据"""
        data = {}
        
        # 最新季度利润表
        try:
            df = self.pro.income(ts_code=ts_code, period='20240930')
            if not df.empty:
                data['income_q3'] = {
                    'total_revenue': df.iloc[0]['total_revenue'] / 1e8,
                    'revenue': df.iloc[0]['revenue'] / 1e8,
                    'n_income': df.iloc[0]['n_income'] / 1e8,
                    'n_income_attr_p': df.iloc[0]['n_income_attr_p'] / 1e8,
                    'basic_eps': df.iloc[0]['basic_eps'],
                    'oper_cost': df.iloc[0]['oper_cost'] / 1e8
                }
        except Exception as e:
            print(f"利润表获取失败: {e}")
        
        # 财务指标
        try:
            df = self.pro.fina_indicator(ts_code=ts_code, period='20240930')
            if not df.empty:
                data['fina_q3'] = {
                    'roe': df.iloc[0]['roe'],
                    'roe_diluted': df.iloc[0]['roe_diluted'],
                    'grossprofit_margin': df.iloc[0]['grossprofit_margin'],
                    'netprofit_margin': df.iloc[0]['netprofit_margin'],
                    'roa': df.iloc[0]['roa'],
                    'debt_to_assets': df.iloc[0]['debt_to_assets']
                }
        except Exception as e:
            print(f"财务指标获取失败: {e}")
        
        # 业绩预告
        try:
            df = self.pro.forecast(ts_code=ts_code)
            if not df.empty:
                data['forecast'] = {
                    'type': df.iloc[0]['type'],
                    'p_change_min': df.iloc[0]['p_change_min'],
                    'p_change_max': df.iloc[0]['p_change_max'],
                    'net_profit_min': df.iloc[0]['net_profit_min'],
                    'net_profit_max': df.iloc[0]['net_profit_max']
                }
        except Exception as e:
            print(f"业绩预告获取失败: {e}")
        
        return data
    
    def calculate_factors(self, ts_code, days=90):
        """
        从Tushare日线重新计算因子
        不用本地数据库
        """
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if df.empty or len(df) < 20:
                return None
            
            df = df.sort_values('trade_date')
            
            # 计算因子
            df['ret_5'] = df['close'].pct_change(5)
            df['ret_10'] = df['close'].pct_change(10)
            df['ret_20'] = df['close'].pct_change(20)
            df['ret_60'] = df['close'].pct_change(60)
            
            df['vol_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
            df['ma_5'] = df['close'].rolling(5).mean()
            df['ma_20'] = df['close'].rolling(20).mean()
            df['ma_60'] = df['close'].rolling(60).mean()
            
            df['price_pos_20'] = (df['close'] - df['low'].rolling(20).min()) / \
                                 (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 0.001)
            
            df['vol_ratio'] = df['vol'] / df['vol'].rolling(20).mean()
            
            latest = df.iloc[-1]
            
            return {
                'close': latest['close'],
                'ret_5': latest['ret_5'],
                'ret_10': latest['ret_10'],
                'ret_20': latest['ret_20'],
                'ret_60': latest['ret_60'],
                'vol_20': latest['vol_20'],
                'ma_5': latest['ma_5'],
                'ma_20': latest['ma_20'],
                'ma_60': latest['ma_60'],
                'price_pos_20': latest['price_pos_20'],
                'vol_ratio': latest['vol_ratio'],
                'price_to_ma20': latest['close'] / latest['ma_20'] if latest['ma_20'] else None
            }
        except Exception as e:
            print(f"因子计算失败: {e}")
            return None
    
    def get_concepts(self, ts_code):
        """获取概念板块"""
        try:
            df = self.pro.concept_detail(ts_code=ts_code)
            if not df.empty:
                return df['concept_name'].tolist()
        except Exception as e:
            print(f"概念板块获取失败: {e}")
        return []
    
    def get_moneyflow(self, ts_code, days=10):
        """获取资金流向"""
        try:
            df = self.pro.moneyflow(ts_code=ts_code, limit=days)
            if not df.empty:
                return df.to_dict('records')
        except Exception as e:
            print(f"资金流向获取失败: {e}")
        return []
    
    def get_industry_comparison(self, ts_codes):
        """获取行业对比数据"""
        results = []
        for code in ts_codes:
            try:
                df_basic = self.pro.daily_basic(ts_code=code)
                df_stock = self.pro.stock_basic(ts_code=code)
                
                if not df_basic.empty and not df_stock.empty:
                    results.append({
                        'ts_code': code,
                        'name': df_stock.iloc[0]['name'],
                        'pe': df_basic.iloc[0]['pe_ttm'],
                        'pb': df_basic.iloc[0]['pb'],
                        'total_mv': df_basic.iloc[0]['total_mv'] / 1e8
                    })
            except Exception as e:
                print(f"{code}对比数据获取失败: {e}")
        return results
    
    def get_full_data(self, ts_code):
        """获取完整数据"""
        print(f"正在获取 {ts_code} 的完整数据...")
        
        data = {
            'ts_code': ts_code,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 1. 基本信息
        print("1. 获取基本信息...")
        data['basic'] = self.get_basic_info(ts_code)
        
        # 2. 股价多源验证
        print("2. 多源股价验证...")
        data['price_verify'] = self.get_price_cross_verify(ts_code)
        
        # 3. 估值数据
        print("3. 获取估值数据...")
        data['valuation'] = self.get_valuation(ts_code)
        
        # 4. 财务数据
        print("4. 获取财务数据...")
        data['financial'] = self.get_financial_data(ts_code)
        
        # 5. 因子计算
        print("5. 重新计算因子...")
        data['factors'] = self.calculate_factors(ts_code)
        
        # 6. 概念板块
        print("6. 获取概念板块...")
        data['concepts'] = self.get_concepts(ts_code)
        
        # 7. 资金流向
        print("7. 获取资金流向...")
        data['moneyflow'] = self.get_moneyflow(ts_code)
        
        print("数据获取完成!")
        return data


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print("Usage: python stock_data_collector.py <ts_code>")
        print("Example: python stock_data_collector.py 600875.SH")
        sys.exit(1)
    
    ts_code = sys.argv[1]
    
    collector = StockDataCollector()
    data = collector.get_full_data(ts_code)
    
    # 输出JSON
    output_file = f"/tmp/{ts_code.replace('.', '_')}_data.json"
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"\n数据已保存到: {output_file}")
    
    # 打印摘要
    print("\n数据摘要:")
    print(f"公司名称: {data.get('basic', {}).get('name', 'N/A')}")
    print(f"最新价格: {data.get('price_verify', {}).get('final_price', 'N/A')}")
    print(f"PE(TTM): {data.get('valuation', {}).get('pe_ttm', 'N/A')}")
    print(f"ROE: {data.get('financial', {}).get('fina_q3', {}).get('roe', 'N/A')}")
    print(f"ret_20: {data.get('factors', {}).get('ret_20', 'N/A')}")


if __name__ == '__main__':
    main()
