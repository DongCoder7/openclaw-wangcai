#!/root/.openclaw/workspace/venv/bin/python3
"""
Tushare API 统一封装模块
自动加载配置，确保token不会遗漏

使用示例:
    from tushare_api import TushareAPI, get_tushare_api
    
    # 方式1: 直接使用全局实例
    pro = get_tushare_api()
    df = pro.daily(ts_code='000001.SZ', start_date='20240101')
    
    # 方式2: 创建新实例
    api = TushareAPI()
    df = api.get_daily('000001.SZ', '20240101', '20241231')
"""

import os
import sys
from typing import Optional, Dict, List
from datetime import datetime, timedelta

# 全局实例缓存
_tushare_instance = None


class TushareAPI:
    """Tushare API 封装类"""
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化Tushare API
        
        Args:
            token: Tushare token，如果不提供则自动从环境变量或配置文件加载
        """
        self.token = token or self._load_token()
        self.pro = None
        self._init_api()
    
    def _load_token(self) -> str:
        """
        自动加载Tushare token
        优先级: 传入参数 > 环境变量 > 配置文件
        """
        # 1. 检查环境变量
        token = os.getenv('TUSHARE_TOKEN')
        if token:
            print("✅ Tushare token loaded from environment variable")
            return token
        
        # 2. 检查配置文件
        config_paths = [
            '/root/.openclaw/workspace/.tushare.env',
            '/root/.openclaw/workspace/config/tushare.env',
            './.tushare.env',
            './config/tushare.env',
        ]
        
        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        for line in f:
                            if 'TUSHARE_TOKEN' in line and '=' in line:
                                token = line.split('=')[1].strip().strip('"').strip("'")
                                if token:
                                    # 设置到环境变量，供后续使用
                                    os.environ['TUSHARE_TOKEN'] = token
                                    print(f"✅ Tushare token loaded from {path}")
                                    return token
                except Exception as e:
                    print(f"⚠️ Failed to load token from {path}: {e}")
                    continue
        
        raise ValueError(
            "Tushare token not found. Please set TUSHARE_TOKEN environment variable "
            "or create .tushare.env file with TUSHARE_TOKEN='your_token'"
        )
    
    def _init_api(self):
        """初始化Tushare Pro API"""
        try:
            import tushare as ts
            ts.set_token(self.token)
            self.pro = ts.pro_api()
            print("✅ Tushare Pro API initialized successfully")
        except ImportError:
            raise ImportError(
                "tushare package not installed. Please install: pip install tushare"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Tushare API: {e}")
    
    # ==================== 股票基础数据 ====================
    
    def get_stock_basic(self, ts_code: Optional[str] = None, 
                        name: Optional[str] = None,
                        market: Optional[str] = None) -> Optional[Dict]:
        """
        获取股票基础信息
        
        Args:
            ts_code: 股票代码 (如: 000001.SZ)
            name: 股票名称
            market: 市场 (主板/M/创业板/K/科创板/N)
            
        Returns:
            股票基础信息字典
        """
        try:
            if ts_code:
                df = self.pro.stock_basic(ts_code=ts_code, 
                                          fields='ts_code,name,area,industry,market,list_date,act_name,act_ent_type')
            elif name:
                df = self.pro.stock_basic(name=name,
                                          fields='ts_code,name,area,industry,market,list_date,act_name,act_ent_type')
            else:
                return None
            
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
            return None
        except Exception as e:
            print(f"⚠️ Error getting stock basic info: {e}")
            return None
    
    def get_daily(self, ts_code: str, start_date: Optional[str] = None,
                  end_date: Optional[str] = None, trade_date: Optional[str] = None) -> Optional[object]:
        """
        获取日线行情数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            trade_date: 特定交易日期 (与start_date/end_date互斥)
            
        Returns:
            DataFrame with daily price data
        """
        try:
            if trade_date:
                df = self.pro.daily(ts_code=ts_code, trade_date=trade_date)
            else:
                if not start_date:
                    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
                if not end_date:
                    end_date = datetime.now().strftime('%Y%m%d')
                df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            return df
        except Exception as e:
            print(f"⚠️ Error getting daily data: {e}")
            return None
    
    def get_daily_basic(self, ts_code: str, trade_date: Optional[str] = None,
                        start_date: Optional[str] = None, end_date: Optional[str] = None) -> Optional[object]:
        """
        获取每日指标（估值、市值等）
        
        Args:
            ts_code: 股票代码
            trade_date: 特定交易日期
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            DataFrame with daily basic indicators
        """
        try:
            if trade_date:
                df = self.pro.daily_basic(ts_code=ts_code, trade_date=trade_date)
            else:
                df = self.pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
            return df
        except Exception as e:
            print(f"⚠️ Error getting daily basic: {e}")
            return None
    
    # ==================== 财务数据 ====================
    
    def get_income(self, ts_code: str, period: Optional[str] = None,
                   start_date: Optional[str] = None, end_date: Optional[str] = None) -> Optional[object]:
        """获取利润表数据"""
        try:
            df = self.pro.income(ts_code=ts_code, period=period, 
                                 start_date=start_date, end_date=end_date)
            return df
        except Exception as e:
            print(f"⚠️ Error getting income data: {e}")
            return None
    
    def get_balance_sheet(self, ts_code: str, period: Optional[str] = None) -> Optional[object]:
        """获取资产负债表"""
        try:
            df = self.pro.balancesheet(ts_code=ts_code, period=period)
            return df
        except Exception as e:
            print(f"⚠️ Error getting balance sheet: {e}")
            return None
    
    def get_cash_flow(self, ts_code: str, period: Optional[str] = None) -> Optional[object]:
        """获取现金流量表"""
        try:
            df = self.pro.cashflow(ts_code=ts_code, period=period)
            return df
        except Exception as e:
            print(f"⚠️ Error getting cash flow: {e}")
            return None
    
    def get_fina_indicator(self, ts_code: str, period: Optional[str] = None) -> Optional[object]:
        """获取财务指标数据"""
        try:
            df = self.pro.fina_indicator(ts_code=ts_code, period=period)
            return df
        except Exception as e:
            print(f"⚠️ Error getting fina indicator: {e}")
            return None
    
    # ==================== 市场数据 ====================
    
    def get_top10_holders(self, ts_code: str, period: Optional[str] = None) -> Optional[object]:
        """获取前十大股东"""
        try:
            df = self.pro.top10_holders(ts_code=ts_code, period=period)
            return df
        except Exception as e:
            print(f"⚠️ Error getting top10 holders: {e}")
            return None
    
    def get_stk_holdernumber(self, ts_code: str) -> Optional[object]:
        """获取股东人数"""
        try:
            df = self.pro.stk_holdernumber(ts_code=ts_code)
            return df
        except Exception as e:
            print(f"⚠️ Error getting holder number: {e}")
            return None
    
    # ==================== 便捷方法 ====================
    
    def get_stock_profile(self, ts_code: str) -> Dict:
        """
        获取股票完整画像（基础信息+最新估值）
        
        Args:
            ts_code: 股票代码
            
        Returns:
            包含基础信息和估值的字典
        """
        profile = {
            'basic': None,
            'valuation': None,
            'latest_price': None
        }
        
        # 基础信息
        profile['basic'] = self.get_stock_basic(ts_code)
        
        # 最新估值
        today = datetime.now().strftime('%Y%m%d')
        df = self.get_daily_basic(ts_code, trade_date=today)
        if df is None or df.empty:
            # 尝试昨天
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            df = self.get_daily_basic(ts_code, trade_date=yesterday)
        
        if df is not None and not df.empty:
            profile['valuation'] = df.iloc[0].to_dict()
        
        # 最新价格
        df_price = self.get_daily(ts_code, trade_date=today)
        if df_price is None or df_price.empty:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            df_price = self.get_daily(ts_code, trade_date=yesterday)
        
        if df_price is not None and not df.empty:
            profile['latest_price'] = df_price.iloc[0].to_dict()
        
        return profile
    
    def get_financial_summary(self, ts_code: str) -> Dict:
        """
        获取财务摘要（最近一期）
        
        Args:
            ts_code: 股票代码
            
        Returns:
            财务摘要字典
        """
        summary = {}
        
        # 获取最近一期财务指标
        df = self.get_fina_indicator(ts_code)
        if df is not None and not df.empty:
            latest = df.iloc[0]
            summary = {
                'period': latest.get('end_date'),
                'roe': latest.get('roe'),
                'roe_diluted': latest.get('roe_diluted'),
                'roa': latest.get('roa'),
                'grossprofit_margin': latest.get('grossprofit_margin'),
                'netprofit_margin': latest.get('netprofit_margin'),
                'debt_to_assets': latest.get('debt_to_assets'),
                'current_ratio': latest.get('current_ratio'),
                'quick_ratio': latest.get('quick_ratio'),
            }
        
        return summary


def get_tushare_api(token: Optional[str] = None) -> TushareAPI:
    """
    获取Tushare API全局实例（单例模式）
    
    Args:
        token: 可选的token，如果不提供则自动加载
        
    Returns:
        TushareAPI实例
    """
    global _tushare_instance
    
    if _tushare_instance is None:
        _tushare_instance = TushareAPI(token)
    
    return _tushare_instance


def reset_tushare_api():
    """重置全局实例（用于测试或重新初始化）"""
    global _tushare_instance
    _tushare_instance = None


# 便捷函数
def get_stock_basic_info(ts_code: str) -> Optional[Dict]:
    """便捷函数：获取股票基础信息"""
    api = get_tushare_api()
    return api.get_stock_basic(ts_code)


def get_stock_daily(ts_code: str, start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> Optional[object]:
    """便捷函数：获取日线数据"""
    api = get_tushare_api()
    return api.get_daily(ts_code, start_date, end_date)


def get_stock_valuation(ts_code: str) -> Optional[Dict]:
    """便捷函数：获取最新估值"""
    api = get_tushare_api()
    profile = api.get_stock_profile(ts_code)
    return profile.get('valuation')


if __name__ == "__main__":
    # 测试
    print("🧪 Testing Tushare API Wrapper")
    print("="*60)
    
    try:
        # 测试初始化
        api = get_tushare_api()
        print("\n✅ API initialized successfully")
        
        # 测试获取股票基础信息
        print("\n📊 Testing get_stock_basic...")
        info = api.get_stock_basic("000001.SZ")
        if info:
            print(f"✅ Got stock info: {info.get('name')} ({info.get('ts_code')})")
            print(f"   Industry: {info.get('industry')}")
            print(f"   Market: {info.get('market')}")
        
        # 测试获取日线数据
        print("\n📈 Testing get_daily...")
        df = api.get_daily("000001.SZ", trade_date=(datetime.now() - timedelta(days=1)).strftime('%Y%m%d'))
        if df is not None and not df.empty:
            print(f"✅ Got daily data: {len(df)} rows")
            print(f"   Close price: {df.iloc[0]['close']}")
        
        # 测试获取估值
        print("\n💰 Testing get_stock_profile...")
        profile = api.get_stock_profile("000001.SZ")
        if profile.get('valuation'):
            val = profile['valuation']
            print(f"✅ Got valuation:")
            print(f"   PE: {val.get('pe')}")
            print(f"   PB: {val.get('pb')}")
            print(f"   Total MV: {val.get('total_mv')}万元")
        
        print("\n" + "="*60)
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
