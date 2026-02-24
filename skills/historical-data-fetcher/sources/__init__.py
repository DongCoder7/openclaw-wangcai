#!/usr/bin/env python3
"""
数据源基类和通用接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
import pandas as pd
from datetime import datetime

class DataSource(ABC):
    """数据源基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.available = False
    
    @abstractmethod
    def test_connection(self) -> bool:
        """测试连接是否可用"""
        pass
    
    @abstractmethod
    def get_daily_data(self, code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        获取日线数据
        
        Args:
            code: 股票代码 (如: 000001.SZ)
            start: 开始日期 (YYYYMMDD)
            end: 结束日期 (YYYYMMDD)
        
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        pass
    
    @abstractmethod
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表"""
        pass
    
    def get_fundamental_data(self, code: str) -> Optional[pd.DataFrame]:
        """获取基本面数据 (可选)"""
        return None
    
    def get_realtime_quotes(self, codes: List[str]) -> Optional[pd.DataFrame]:
        """获取实时行情 (可选)"""
        return None


class DataFetcher:
    """
    统一数据获取器 - 自动选择可用数据源
    """
    
    def __init__(self):
        self.sources: Dict[str, DataSource] = {}
        self.primary_source: Optional[DataSource] = None
        self._init_sources()
    
    def _init_sources(self):
        """初始化所有数据源"""
        # Import and register all sources
        try:
            from .akshare_source import AKShareSource
            source = AKShareSource()
            self.sources['akshare'] = source
            if source.test_connection():
                self.primary_source = source
        except Exception as e:
            print(f"AKShare source not available: {e}")
        
        try:
            from .tencent_source import TencentSource
            source = TencentSource()
            self.sources['tencent'] = source
            if source.test_connection() and not self.primary_source:
                self.primary_source = source
        except Exception as e:
            print(f"Tencent source not available: {e}")
        
        try:
            from .local_source import LocalSource
            source = LocalSource()
            self.sources['local'] = source
            if source.test_connection() and not self.primary_source:
                self.primary_source = source
        except Exception as e:
            print(f"Local source not available: {e}")
    
    def test_sources(self) -> Dict[str, bool]:
        """测试所有数据源"""
        results = {}
        for name, source in self.sources.items():
            results[name] = source.test_connection()
        return results
    
    def get_daily_data(self, code: str, start: str, end: str, 
                      sources: List[str] = None) -> Optional[pd.DataFrame]:
        """
        获取日线数据，自动回退
        
        Args:
            code: 股票代码
            start: 开始日期
            end: 结束日期
            sources: 指定数据源优先级列表，如 ['akshare', 'tencent', 'local']
        
        Returns:
            DataFrame or None
        """
        if sources is None:
            # Use all available sources in priority order
            sources = ['akshare', 'tencent', 'local']
        
        for source_name in sources:
            if source_name not in self.sources:
                continue
            
            source = self.sources[source_name]
            if not source.available:
                continue
            
            try:
                df = source.get_daily_data(code, start, end)
                if df is not None and not df.empty:
                    print(f"✅ Data from {source_name}: {code}")
                    return df
            except Exception as e:
                print(f"⚠️ {source_name} failed for {code}: {e}")
                continue
        
        print(f"❌ No data available for {code}")
        return None
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表"""
        for source_name in ['akshare', 'tencent', 'local']:
            if source_name in self.sources:
                source = self.sources[source_name]
                if source.available:
                    try:
                        df = source.get_stock_list()
                        if df is not None and not df.empty:
                            return df
                    except:
                        continue
        return None
    
    def batch_fetch(self, codes: List[str], start: str, end: str,
                   progress_callback=None) -> Dict[str, pd.DataFrame]:
        """
        批量获取数据
        
        Returns:
            Dict mapping code to DataFrame
        """
        results = {}
        total = len(codes)
        
        for i, code in enumerate(codes):
            df = self.get_daily_data(code, start, end)
            if df is not None:
                results[code] = df
            
            if progress_callback:
                progress_callback(i + 1, total, code)
        
        return results
