#!/root/.openclaw/workspace/venv/bin/python3
"""
A股行业平均PE查询工具 - 最佳实践封装
基于Tushare Pro + stock_basic行业分类 + daily_basic逐个计算
"""
import tushare as ts
import pandas as pd
from datetime import datetime

class IndustryPEAnalyzer:
    """行业PE分析器"""
    
    def __init__(self, token=None):
        """初始化"""
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()
        self._cache = {}  # 缓存行业数据
    
    def get_industry_pe(self, ts_code, trade_date=None, sample_size=20):
        """
        获取个股所在行业的平均PE
        
        参数:
            ts_code: 股票代码 (如 '300666.SZ')
            trade_date: 交易日期 (如 '20250228'), None则使用最新交易日
            sample_size: 样本数量 (默认20只可比公司)
        
        返回:
            dict: {
                'stock_code': 股票代码,
                'stock_name': 股票名称,
                'stock_pe': 个股PE,
                'industry': 行业名称,
                'industry_avg_pe': 行业平均PE,
                'industry_median_pe': 行业中位数PE,
                'sample_size': 样本数量,
                'percentile': 估值分位 (0-100),
                'valuation': 估值判断 ('高估'/'偏高'/'合理'/'低估'),
                'comparable_stocks': [可比公司列表]
            }
        """
        # 1. 获取个股信息
        df_stock = self.pro.stock_basic(ts_code=ts_code, fields='ts_code,name,industry')
        if len(df_stock) == 0:
            return None
        
        stock_name = df_stock.iloc[0]['name']
        industry = df_stock.iloc[0]['industry']
        
        # 2. 获取交易日
        if trade_date is None:
            # 使用最近交易日
            df_trade = self.pro.trade_cal(exchange='SSE', start_date='20250101', end_date=datetime.now().strftime('%Y%m%d'))
            trade_date = df_trade[df_trade['is_open'] == 1]['cal_date'].max()
        
        # 3. 获取个股PE
        df_pe = self.pro.daily_basic(ts_code=ts_code, trade_date=trade_date, fields='ts_code,pe_ttm,pb,total_mv')
        if len(df_pe) == 0:
            return None
        
        stock_pe = df_pe.iloc[0]['pe_ttm']
        stock_pb = df_pe.iloc[0]['pb']
        stock_mv = df_pe.iloc[0]['total_mv'] / 10000  # 万元转亿元
        
        # 4. 获取同行业股票
        if industry not in self._cache:
            df_industry = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,industry')
            self._cache[industry] = df_industry[df_industry['industry'] == industry]
        
        same_industry = self._cache[industry]
        same_industry = same_industry[same_industry['ts_code'] != ts_code]
        
        # 5. 获取可比公司PE
        sample = same_industry.head(sample_size)
        pe_data = []
        comparable_stocks = []
        
        for _, row in sample.iterrows():
            try:
                df_comp = self.pro.daily_basic(ts_code=row['ts_code'], trade_date=trade_date, 
                                               fields='ts_code,pe_ttm,pb,total_mv')
                if len(df_comp) > 0 and df_comp.iloc[0]['pe_ttm'] and df_comp.iloc[0]['pe_ttm'] > 0:
                    pe = df_comp.iloc[0]['pe_ttm']
                    pb = df_comp.iloc[0]['pb']
                    mv = df_comp.iloc[0]['total_mv'] / 10000
                    
                    pe_data.append(pe)
                    comparable_stocks.append({
                        'ts_code': row['ts_code'],
                        'name': row['name'],
                        'pe': pe,
                        'pb': pb,
                        'mv': mv
                    })
            except:
                pass
        
        # 6. 计算行业统计
        if not pe_data:
            return None
        
        avg_pe = sum(pe_data) / len(pe_data)
        median_pe = sorted(pe_data)[len(pe_data) // 2]
        min_pe = min(pe_data)
        max_pe = max(pe_data)
        
        # 7. 计算估值分位
        all_pe = sorted(pe_data + [stock_pe])
        percentile = (all_pe.index(stock_pe) + 1) / len(all_pe) * 100
        
        # 8. 估值判断
        if percentile > 80:
            valuation = '高估'
        elif percentile > 60:
            valuation = '偏高'
        elif percentile > 40:
            valuation = '合理'
        else:
            valuation = '低估'
        
        return {
            'stock_code': ts_code,
            'stock_name': stock_name,
            'stock_pe': round(stock_pe, 2),
            'stock_pb': round(stock_pb, 2),
            'stock_mv': round(stock_mv, 2),
            'industry': industry,
            'trade_date': trade_date,
            'industry_avg_pe': round(avg_pe, 2),
            'industry_median_pe': round(median_pe, 2),
            'industry_min_pe': round(min_pe, 2),
            'industry_max_pe': round(max_pe, 2),
            'sample_size': len(pe_data),
            'percentile': round(percentile, 1),
            'valuation': valuation,
            'vs_industry_pct': round((stock_pe - avg_pe) / avg_pe * 100, 1),
            'comparable_stocks': comparable_stocks
        }
    
    def print_report(self, result):
        """打印分析报告"""
        if not result:
            print("❌ 无法获取数据")
            return
        
        print("=" * 70)
        print(f"📊 {result['stock_name']} ({result['stock_code']}) 行业PE分析报告")
        print("=" * 70)
        
        print(f"\n【个股信息】")
        print(f"  股票名称: {result['stock_name']}")
        print(f"  股票代码: {result['stock_code']}")
        print(f"  所属行业: {result['industry']}")
        print(f"  数据日期: {result['trade_date']}")
        
        print(f"\n【个股估值】")
        print(f"  PE_TTM: {result['stock_pe']}")
        print(f"  PB: {result['stock_pb']}")
        print(f"  市值: {result['stock_mv']}亿元")
        
        print(f"\n【行业估值统计】（基于{result['sample_size']}只可比公司）")
        print(f"  行业平均PE: {result['industry_avg_pe']}")
        print(f"  行业中位数PE: {result['industry_median_pe']}")
        print(f"  行业最低PE: {result['industry_min_pe']}")
        print(f"  行业最高PE: {result['industry_max_pe']}")
        
        print(f"\n【估值对比】")
        vs = result['vs_industry_pct']
        print(f"  个股PE vs 行业平均: {'+' if vs > 0 else ''}{vs}%")
        print(f"  估值分位: {result['percentile']}%")
        
        # 估值判断颜色
        val = result['valuation']
        emoji = {'高估': '🔴', '偏高': '🟡', '合理': '🟢', '低估': '🔵'}.get(val, '⚪')
        print(f"  估值判断: {emoji} {val}")
        
        print(f"\n【可比公司TOP5】")
        for i, comp in enumerate(result['comparable_stocks'][:5], 1):
            print(f"  {i}. {comp['name'][:8]} ({comp['ts_code'][:6]}): PE={comp['pe']:.2f}")
        
        print("=" * 70)

# 使用示例
if __name__ == '__main__':
    # 初始化（使用默认token）
    analyzer = IndustryPEAnalyzer('cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30')
    
    # 分析个股
    result = analyzer.get_industry_pe('300666.SZ')
    analyzer.print_report(result)
    
    # 获取建议给予PE
    if result:
        print(f"\n【目标PE建议】")
        print(f"  保守: {result['industry_median_pe'] * 0.8:.0f}x")
        print(f"  中性: {result['industry_median_pe']:.0f}x")
        print(f"  乐观: {result['industry_median_pe'] * 1.2:.0f}x")
