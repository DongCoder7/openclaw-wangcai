#!/usr/bin/env python3
"""
投资策略分析套件 - 统一调度入口
整合所有分析功能，一键调用
"""
import sys
import os
from typing import List, Dict, Optional
from datetime import datetime

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')

# 导入各个模块
from longbridge_api import get_longbridge_api, LongbridgeAPI
from zsxq_fetcher import get_latest, search_industry_info

class InvestmentAnalysisSuite:
    """投资策略分析套件主类"""
    
    def __init__(self):
        """初始化"""
        self.longbridge = None
        self._init_apis()
    
    def _init_apis(self):
        """初始化API连接"""
        try:
            self.longbridge = get_longbridge_api()
            print("✅ 长桥API初始化成功")
        except Exception as e:
            print(f"⚠️ 长桥API初始化失败: {e}")
    
    def get_quotes(self, symbols: List[str]) -> List[Dict]:
        """获取实时行情
        
        Args:
            symbols: 股票代码列表 (如 ['002371.SZ', 'AAPL.US'])
            
        Returns:
            List[Dict]: 行情数据列表
        """
        if not self.longbridge:
            print("❌ 长桥API未初始化")
            return []
        
        return self.longbridge.get_quotes(symbols)
    
    def analyze_industry_chain(self, industry: str, 
                               include_zsxq: bool = True,
                               include_factors: bool = True) -> Dict:
        """产业链深度分析
        
        Args:
            industry: 行业名称 (如 '存储芯片', 'PCB')
            include_zsxq: 是否包含知识星球信息
            include_factors: 是否包含v26因子分析
            
        Returns:
            Dict: 分析报告
        """
        result = {
            'industry': industry,
            'timestamp': datetime.now().isoformat(),
            'zsxq_data': None,
            'quotes': None,
            'factors': None,
            'recommendations': []
        }
        
        # 1. 获取知识星球信息
        if include_zsxq:
            print(f"🔍 获取知识星球'{industry}'相关信息...")
            try:
                topics = search_industry_info(industry, count=10)
                result['zsxq_data'] = topics
            except Exception as e:
                print(f"⚠️ 知识星球获取失败: {e}")
        
        # 2. 获取实时行情
        # 根据行业获取相关股票
        industry_stocks = self._get_industry_stocks(industry)
        if industry_stocks:
            print(f"📊 获取{len(industry_stocks)}只相关股票行情...")
            try:
                quotes = self.get_quotes(industry_stocks)
                result['quotes'] = quotes
            except Exception as e:
                print(f"⚠️ 行情获取失败: {e}")
        
        return result
    
    def generate_us_report(self, send_message: bool = False) -> str:
        """生成美股市场报告"""
        script_path = '/root/.openclaw/workspace/skills/us-market-analysis/scripts/generate_report_longbridge.py'
        os.system(f'python3 {script_path}')
        return "美股报告已生成"
    
    def generate_ah_preopen(self, send_message: bool = False) -> str:
        """生成A+H开盘前瞻报告"""
        script_path = '/root/.openclaw/workspace/skills/ah-market-preopen/scripts/generate_report_longbridge.py'
        os.system(f'python3 {script_path}')
        return "A+H开盘报告已生成"
    
    def search_zsxq(self, keyword: str, count: int = 10) -> List[Dict]:
        """搜索知识星球"""
        return search_industry_info(keyword, count)
    
    def _get_industry_stocks(self, industry: str) -> List[str]:
        """获取行业相关股票代码"""
        stock_map = {
            '存储芯片': [
                '002371.SZ', '688012.SH', '688072.SH', '688120.SH',  # 设备
                '688019.SH', '300054.SZ',  # 材料
                '600584.SH', '002156.SZ', '688525.SH',  # 封测/模组
            ],
            'PCB': [
                '600183.SH', '002916.SZ',  # 生益/深南
                '300476.SZ', '603228.SH',  # 胜宏/景旺
            ],
            '半导体': [
                '688012.SH', '688072.SH', '688120.SH',  # 设备
                '688019.SH', '688200.SH',  # 材料
                '688981.SH', '603501.SH',  # 制造/设计
            ]
        }
        return stock_map.get(industry, [])
    
    def get_industry_quotes(self, industry: str) -> List[Dict]:
        """获取行业股票实时行情"""
        stocks = self._get_industry_stocks(industry)
        if not stocks:
            return []
        return self.get_quotes(stocks)


# 便捷函数接口
def get_analysis_suite() -> InvestmentAnalysisSuite:
    """获取分析套件实例"""
    return InvestmentAnalysisSuite()

def get_quotes(symbols: List[str]) -> List[Dict]:
    """便捷函数：获取实时行情"""
    suite = get_analysis_suite()
    return suite.get_quotes(symbols)

def analyze_industry(industry: str) -> Dict:
    """便捷函数：产业链分析"""
    suite = get_analysis_suite()
    return suite.analyze_industry_chain(industry)

def search_zsxq(keyword: str, count: int = 10) -> List[Dict]:
    """便捷函数：搜索知识星球"""
    suite = get_analysis_suite()
    return suite.search_zsxq(keyword, count)


if __name__ == "__main__":
    # 测试
    suite = get_analysis_suite()
    
    # 测试获取行情
    print("\n测试获取行情...")
    quotes = suite.get_quotes(['002371.SZ', '00700.HK'])
    for q in quotes:
        print(f"{q['symbol']}: {q['price']:.2f} ({q['change']:+.2f}%)")
    
    # 测试行业分析
    print("\n测试存储芯片分析...")
    result = suite.analyze_industry_chain('存储芯片')
    print(f"获取到{len(result.get('quotes', []))}只股票行情")
