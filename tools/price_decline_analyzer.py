#!/root/.openclaw/workspace/venv/bin/python3
"""
股价回撤分析工具 v2.0
用途：筛选最新价低于8-10月最高价的股票
数据源策略：
- 最新价: 优先长桥（实际交易价格），失败则用Tushare（复权价）
- 8-10月最高价: Tushare（历史数据完整）
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

sys.path.insert(0, '/root/.openclaw/workspace')
sys.path.insert(0, '/root/.openclaw/workspace/tools')

import pandas as pd


@dataclass
class StockPriceData:
    ts_code: str
    name: str
    latest_price: float
    max_price_aug_oct: float
    decline_pct: float
    market: Optional[str] = None
    data_source: str = "unknown"


class RateLimiter:
    def __init__(self, calls_per_second: float = 3.0, calls_per_minute: float = 200.0):
        self.calls_per_second = calls_per_second
        self.calls_per_minute = calls_per_minute
        self.last_call_time = 0
        self.minute_calls = []
        self.minute_window = 60
    
    def wait_if_needed(self):
        now = time.time()
        self.minute_calls = [t for t in self.minute_calls if now - t < self.minute_window]
        
        time_since_last = now - self.last_call_time
        if time_since_last < (1.0 / self.calls_per_second):
            sleep_time = (1.0 / self.calls_per_second) - time_since_last
            time.sleep(sleep_time)
            now = time.time()
        
        if len(self.minute_calls) >= self.calls_per_minute:
            oldest = self.minute_calls[0]
            wait_time = self.minute_window - (now - oldest) + 0.1
            if wait_time > 0:
                print(f"    ⚠️ 触发分钟限流，等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)
                now = time.time()
            self.minute_calls = [t for t in self.minute_calls if now - t < self.minute_window]
        
        self.last_call_time = time.time()
        self.minute_calls.append(self.last_call_time)


class TushareProvider:
    def __init__(self):
        self.api = None
        self.limiter = RateLimiter(calls_per_second=3.0, calls_per_minute=200.0)
        self._init_api()
    
    def _init_api(self):
        try:
            import tushare as ts
            token = None
            try:
                with open('/root/.openclaw/workspace/.tushare.env', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if 'TUSHARE_TOKEN' in line and '=' in line and not line.startswith('#'):
                            token = line.split('=')[1].strip().strip('"').strip("'")
                            break
            except FileNotFoundError:
                pass
            
            if not token:
                token = os.getenv('TUSHARE_TOKEN')
            
            if not token:
                raise ValueError("TUSHARE_TOKEN not found")
            
            ts.set_token(token)
            self.api = ts.pro_api()
            print("✅ Tushare API initialized")
        except Exception as e:
            print(f"❌ Tushare API init failed: {e}")
            self.api = None
    
    def _call_with_limit(self, func, *args, **kwargs):
        if self.api is None:
            return None
        self.limiter.wait_if_needed()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e).lower()
            if 'limit' in error_msg or 'minute' in error_msg or 'frequency' in error_msg:
                print(f"    ⚠️ 触发Tushare限流，等待60秒...")
                time.sleep(60)
                return func(*args, **kwargs)
            raise e
    
    def get_stock_list(self, limit: Optional[int] = None) -> pd.DataFrame:
        if self.api is None:
            return pd.DataFrame()
        
        print("📋 获取A股股票列表...")
        df = self._call_with_limit(self.api.stock_basic, 
                                   exchange='', 
                                   list_status='L', 
                                   fields='ts_code,name,industry,market')
        
        df = df[df['ts_code'].str.endswith(('.SH', '.SZ'))]
        df = df[~df['name'].str.contains('ST', na=False)]
        df = df[~df['ts_code'].str.startswith(('900', '200'))]
        
        if limit:
            df = df.head(limit)
        
        print(f"   获取到 {len(df)} 只股票")
        return df
    
    def get_latest_price(self, ts_code: str) -> Optional[float]:
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=15)).strftime('%Y%m%d')
            
            df = self._call_with_limit(self.api.daily,
                                       ts_code=ts_code,
                                       start_date=start_date,
                                       end_date=end_date)
            
            if df is not None and not df.empty:
                return float(df.iloc[-1]['close'])
            return None
        except Exception as e:
            print(f"    ⚠️ 获取{ts_code}最新价失败: {e}")
            return None
    
    def get_aug_oct_high(self, ts_code: str, year: Optional[int] = None) -> Optional[float]:
        try:
            if year is None:
                current_year = datetime.now().year
                current_month = datetime.now().month
                if current_month < 8:
                    year = current_year - 1
                else:
                    year = current_year
            
            start_date = f"{year}0801"
            end_date = f"{year}1031"
            
            df = self._call_with_limit(self.api.daily,
                                       ts_code=ts_code,
                                       start_date=start_date,
                                       end_date=end_date)
            
            if df is not None and not df.empty:
                return float(df['high'].max())
            return None
        except Exception as e:
            print(f"    ⚠️ 获取{ts_code}8-10月高价失败: {e}")
            return None


class LongbridgeProvider:
    def __init__(self):
        self.api = None
        self.limiter = RateLimiter(calls_per_second=8.0, calls_per_minute=500.0)
        self._init_api()
    
    def _init_api(self):
        try:
            from longport.openapi import QuoteContext, Config
            
            app_key = os.getenv('LONGBRIDGE_APP_KEY') or os.getenv('LONGPORT_APP_KEY')
            app_secret = os.getenv('LONGBRIDGE_APP_SECRET') or os.getenv('LONGPORT_APP_SECRET')
            access_token = os.getenv('LONGBRIDGE_ACCESS_TOKEN') or os.getenv('LONGPORT_ACCESS_TOKEN')
            
            if not app_key or not app_secret:
                try:
                    with open('/root/.openclaw/workspace/.longbridge.env', 'r') as f:
                        for line in f:
                            line = line.strip()
                            if '=' in line and not line.startswith('#'):
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip().strip('"\'')
                                if key == 'LONGBRIDGE_APP_KEY':
                                    app_key = value
                                elif key == 'LONGBRIDGE_APP_SECRET':
                                    app_secret = value
                                elif key == 'LONGBRIDGE_ACCESS_TOKEN':
                                    access_token = value
                except FileNotFoundError:
                    pass
            
            if not app_key or not app_secret:
                raise ValueError("Longbridge credentials not found")
            
            config = Config(app_key=app_key, app_secret=app_secret, access_token=access_token)
            self.api = QuoteContext(config)
            print("✅ Longbridge API initialized")
        except Exception as e:
            print(f"❌ Longbridge API init failed: {e}")
            self.api = None
    
    def _call_with_limit(self, func, *args, **kwargs):
        if self.api is None:
            return None
        self.limiter.wait_if_needed()
        return func(*args, **kwargs)
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        try:
            resp = self._call_with_limit(self.api.quote, [symbol])
            if resp and len(resp) > 0:
                return float(resp[0].last_done)
            return None
        except Exception as e:
            print(f"    ⚠️ 获取{symbol}最新价失败: {e}")
            return None


class PriceDeclineAnalyzer:
    def __init__(self):
        self.tushare = TushareProvider()
        self.longbridge = LongbridgeProvider()
    
    def get_hybrid_stock_data(self, ts_code: str, name: str = "", market: str = "") -> Optional[StockPriceData]:
        print(f"  [{ts_code}] {name}...")
        
        latest = None
        price_source = "unknown"
        
        if self.longbridge.api is not None:
            latest = self.longbridge.get_latest_price(ts_code)
            if latest:
                price_source = "longbridge"
                print(f"     最新价: {latest} (长桥/实际价)")
        
        if latest is None and self.tushare.api is not None:
            latest = self.tushare.get_latest_price(ts_code)
            if latest:
                price_source = "tushare"
                print(f"     最新价: {latest} (Tushare/复权价)")
        
        if latest is None:
            print(f"     ❌ 无法获取最新价")
            return None
        
        max_aug_oct = None
        if self.tushare.api is not None:
            max_aug_oct = self.tushare.get_aug_oct_high(ts_code)
            if max_aug_oct:
                print(f"     8-10月最高: {max_aug_oct}")
        
        if max_aug_oct is None or max_aug_oct == 0:
            print(f"     ❌ 无法获取8-10月最高价")
            return None
        
        decline_pct = (latest - max_aug_oct) / max_aug_oct * 100
        
        return StockPriceData(
            ts_code=ts_code,
            name=name,
            latest_price=round(latest, 2),
            max_price_aug_oct=round(max_aug_oct, 2),
            decline_pct=round(decline_pct, 1),
            market=market,
            data_source=price_source
        )
    
    def analyze(self, sample_size: int = 50, 
                decline_threshold: float = -10.0,
                output_file: Optional[str] = None) -> pd.DataFrame:
        print("=" * 60)
        print("股价回撤分析 - 最新价 vs 8-10月最高价")
        print("=" * 60)
        
        stocks_df = self.tushare.get_stock_list(limit=sample_size)
        if stocks_df.empty:
            print("❌ 无法获取股票列表")
            return pd.DataFrame()
        
        results = []
        
        print(f"\n📊 开始分析 {len(stocks_df)} 只股票...")
        print(f"   跌幅阈值: {decline_threshold}%")
        print(f"   最新价: 长桥(实际价) > Tushare(复权价)")
        print(f"   历史高: Tushare")
        print("-" * 60)
        
        for idx, row in stocks_df.iterrows():
            ts_code = row['ts_code']
            name = row.get('name', '')
            market = row.get('market', '')
            
            data = self.get_hybrid_stock_data(ts_code, name, market)
            
            if data:
                if data.decline_pct <= decline_threshold:
                    results.append({
                        'ts_code': data.ts_code,
                        'name': data.name,
                        'latest_price': data.latest_price,
                        'max_price_aug_oct': data.max_price_aug_oct,
                        'decline_pct': data.decline_pct,
                        'market': data.market,
                        'price_source': data.data_source
                    })
                    print(f"   ✅ {ts_code}: {data.latest_price} vs {data.max_price_aug_oct} ({data.decline_pct:+.1f}%)")
                else:
                    print(f"   ⏭️ {ts_code}: 跌幅 {data.decline_pct:+.1f}% 未达阈值")
            else:
                print(f"   ❌ {ts_code}: 数据获取失败")
        
        print("-" * 60)
        
        result_df = pd.DataFrame(results)
        
        if not result_df.empty:
            result_df = result_df.sort_values('decline_pct', ascending=True)
            
            print(f"\n📈 分析完成: {len(result_df)} 只股票符合筛选条件")
            print(f"   平均跌幅: {result_df['decline_pct'].mean():.1f}%")
            print(f"   最大跌幅: {result_df['decline_pct'].min():.1f}%")
            
            if output_file:
                result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"\n💾 结果已保存: {output_file}")
        else:
            print("\n⚠️ 没有股票符合筛选条件")
        
        return result_df
    
    def test_rate_limits(self, test_count: int = 10):
        print("\n" + "=" * 60)
        print("限流测试")
        print("=" * 60)
        
        test_stocks = ['000001.SZ', '000002.SZ', '600000.SH', '600519.SH', '000858.SZ']
        
        print("\n🧪 测试Tushare限流...")
        start = time.time()
        for i, code in enumerate(test_stocks[:test_count]):
            try:
                price = self.tushare.get_latest_price(code)
                print(f"   {i+1}. {code}: {price} (耗时 {time.time()-start:.2f}s)")
            except Exception as e:
                print(f"   {i+1}. {code}: 错误 - {e}")
        tushare_time = time.time() - start
        print(f"   Tushare {test_count}次调用总耗时: {tushare_time:.2f}s (平均 {tushare_time/test_count:.2f}s/次)")
        
        print("\n🧪 测试Longbridge限流...")
        start = time.time()
        for i, code in enumerate(test_stocks[:test_count]):
            try:
                price = self.longbridge.get_latest_price(code)
                print(f"   {i+1}. {code}: {price} (耗时 {time.time()-start:.2f}s)")
            except Exception as e:
                print(f"   {i+1}. {code}: 错误 - {e}")
        longbridge_time = time.time() - start
        print(f"   Longbridge {test_count}次调用总耗时: {longbridge_time:.2f}s (平均 {longbridge_time/test_count:.2f}s/次)")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='股价回撤分析工具 v2.0')
    parser.add_argument('--sample', type=int, default=50, help='样本股票数量（默认50）')
    parser.add_argument('--threshold', type=float, default=-10.0, help='跌幅阈值百分比（默认-10）')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径（CSV格式）')
    parser.add_argument('--test-limits', action='store_true', help='测试限流机制')
    parser.add_argument('--full', action='store_true', help='分析全部A股（约5000+只）')
    
    args = parser.parse_args()
    
    analyzer = PriceDeclineAnalyzer()
    
    if args.test_limits:
        analyzer.test_rate_limits(test_count=10)
        return
    
    sample_size = None if args.full else args.sample
    output_file = args.output or f"data/price_decline_{datetime.now().strftime('%Y%m%d')}.csv"
    
    result = analyzer.analyze(
        sample_size=sample_size,
        decline_threshold=args.threshold,
        output_file=output_file
    )
    
    if not result.empty:
        print("\n📋 符合条件的股票列表:")
        print(result.to_string(index=False))


if __name__ == '__main__':
    main()
