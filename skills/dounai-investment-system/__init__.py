#!/usr/bin/env python3
"""
豆奶投资策略系统 - 主控模块
统一入口，整合所有功能
"""
import sys
import os
from typing import List, Dict, Optional
from datetime import datetime

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')
sys.path.insert(0, '/root/.openclaw/workspace')

from longbridge_api import get_longbridge_api, LongbridgeAPI
from zsxq_fetcher import search_industry_info, get_latest
try:
    from skills.a_sector_analysis import SectorRotationAnalyzer
    SECTOR_ANALYSIS_AVAILABLE = True
except ImportError:
    SECTOR_ANALYSIS_AVAILABLE = False

class DounaiSystem:
    """豆奶投资策略系统主类"""
    
    def __init__(self):
        """初始化系统"""
        self.longbridge = None
        self.sector_analyzer = None
        self._init_environment()
        self._init_apis()
    
    def _init_environment(self):
        """初始化环境变量"""
        # 加载长桥API配置
        env_file = '/root/.openclaw/workspace/.longbridge.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"')
            print("✅ 环境变量已加载")
    
    def _init_apis(self):
        """初始化API"""
        try:
            self.longbridge = get_longbridge_api()
            print("✅ 长桥API已连接")
        except Exception as e:
            print(f"⚠️ 长桥API连接失败: {e}")
        
        # 初始化板块分析器
        if SECTOR_ANALYSIS_AVAILABLE:
            try:
                self.sector_analyzer = SectorRotationAnalyzer()
                print("✅ 板块分析器已初始化")
            except Exception as e:
                print(f"⚠️ 板块分析器初始化失败: {e}")
    
    def analyze_industry(self, industry: str, 
                        include_zsxq: bool = True,
                        include_exa: bool = True,
                        include_quotes: bool = True,
                        generate_report: bool = True) -> Dict:
        """产业链深度分析
        
        一键完成:
        1. Exa全网新闻搜索（高优先级）
        2. 知识星球信息获取
        3. 相关股票实时行情
        4. 产业链逻辑分析
        5. 投资组合建议
        
        Args:
            industry: 行业名称 (存储芯片/PCB/半导体)
            include_zsxq: 是否包含知识星球
            include_exa: 是否包含Exa全网搜索
            include_quotes: 是否包含实时行情
            generate_report: 是否生成报告
            
        Returns:
            Dict: 完整分析报告
        """
        print(f"\n🔍 开始分析 {industry} 产业链...")
        print("="*80)
        
        result = {
            'industry': industry,
            'timestamp': datetime.now().isoformat(),
            'exa_news': None,  # Exa全网新闻
            'zsxq_info': None,  # 知识星球
            'quotes': [],
            'analysis': {},
            'portfolio': [],
            'report': None
        }
        
        # 1. Exa全网新闻搜索 (P1高优先级)
        if include_exa:
            print("\n🔥 [P1] Exa全网新闻搜索...")
            try:
                from skills.industry_chain_analysis.scripts.exa_news_search import search_industry_news
                exa_news = search_industry_news(industry)
                result['exa_news'] = exa_news
                print(f"✅ 获取到 {len(exa_news)} 条全网新闻")
            except Exception as e:
                print(f"⚠️ Exa搜索失败: {e}")
        
        # 2. 获取知识星球信息 (P2)
        if include_zsxq:
            print("\n📚 [P2] 获取知识星球调研信息...")
            try:
                topics = search_industry_info(industry, count=10)
                result['zsxq_info'] = topics
                print(f"✅ 获取到 {len(topics) if topics else 0} 条调研纪要")
            except Exception as e:
                print(f"⚠️ 知识星球获取失败: {e}")
        
        # 3. 获取实时行情 (P3)
        if include_quotes and self.longbridge:
            print("\n📊 [P3] 获取实时行情...")
            stocks = self._get_industry_stocks(industry)
            try:
                quotes = self.longbridge.get_quotes(stocks)
                result['quotes'] = quotes
                print(f"✅ 获取到 {len(quotes)} 只股票行情")
            except Exception as e:
                print(f"⚠️ 行情获取失败: {e}")
        
        # 4. 生成分析 (P4)
        print("\n🧠 [P4] 生成产业链分析...")
        result['analysis'] = self._analyze_industry_logic(industry, result['quotes'])
        
        # 5. 生成组合建议 (P5)
        print("\n🎯 [P5] 生成投资组合建议...")
        result['portfolio'] = self._generate_portfolio(industry, result['quotes'])
        
        # 6. 生成报告
        if generate_report:
            result['report'] = self._format_report(result)
            print("\n" + result['report'])
        
        return result
    
    def get_quotes(self, symbols: List[str]) -> List[Dict]:
        """获取实时行情
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            List[Dict]: 行情数据
        """
        if not self.longbridge:
            print("❌ 长桥API未初始化")
            return []
        
        return self.longbridge.get_quotes(symbols)
    
    def generate_us_report(self, send: bool = False) -> str:
        """生成美股报告"""
        print("\n🌙 生成美股隔夜报告...")
        script = '/root/.openclaw/workspace/skills/us-market-analysis/scripts/generate_report_longbridge.py'
        os.system(f'python3 {script}')
        return "美股报告已生成"
    
    def generate_ah_preopen(self, send: bool = False) -> str:
        """生成A+H开盘报告"""
        print("\n🌅 生成A+H开盘前瞻...")
        script = '/root/.openclaw/workspace/skills/ah-market-preopen/scripts/generate_report_longbridge.py'
        os.system(f'python3 {script}')
        return "A+H开盘报告已生成"
    
    def search_zsxq(self, keyword: str, count: int = 10) -> List[Dict]:
        """搜索知识星球"""
        return search_industry_info(keyword, count)
    
    def analyze_stock(self, symbol: str, stock_name: str = None, comprehensive: bool = True) -> str:
        """
        个股深度分析 - 10环节标准流程
        
        Args:
            symbol: 股票代码 (如: 002371.SZ)
            stock_name: 股票名称 (如: 北方华创)
            comprehensive: 是否使用完整10环节分析 (默认True)
            
        Returns:
            str: 完整分析报告 (Markdown格式)
        """
        if comprehensive:
            # 使用完整的10环节分析器
            from skills.dounai_investment_system.scripts.comprehensive_stock_analyzer import analyze_stock
            return analyze_stock(symbol, stock_name or "")
        else:
            # 使用简化版（保留旧逻辑用于快速查询）
            return self._analyze_stock_quick(symbol, stock_name)
    
    def _analyze_stock_quick(self, symbol: str, stock_name: str = None) -> Dict:
        """简化版个股分析（用于快速查询）"""
        print(f"\n🔍 快速分析个股: {symbol} {stock_name or ''}")
        print("="*80)
        
        result = {
            'symbol': symbol,
            'stock_name': stock_name,
            'timestamp': datetime.now().isoformat(),
            'exa_news': None,
            'quote': None,
            'recommendation': None
        }
        
        # 1. Exa全网新闻搜索
        print("\n🔥 [P1] Exa全网搜索个股新闻...")
        try:
            from skills.dounai_investment_system.scripts.stock_news_search import get_stock_news
            search_name = stock_name or symbol
            exa_news = get_stock_news(search_name, symbol)
            result['exa_news'] = exa_news
            print(f"✅ 获取到 {len(exa_news)} 条个股新闻")
        except Exception as e:
            print(f"⚠️ Exa搜索失败: {e}")
        
        # 2. 实时行情
        print("\n📊 [P2] 获取实时行情...")
        if self.longbridge:
            try:
                quotes = self.longbridge.get_quotes([symbol])
                if quotes:
                    result['quote'] = quotes[0]
                    print(f"✅ 当前价格: {quotes[0]['price']:.2f} ({quotes[0]['change']:+.2f}%)")
            except Exception as e:
                print(f"⚠️ 行情获取失败: {e}")
        
        # 3. 生成建议
        print("\n🎯 [P3] 生成建仓建议...")
        quote = result.get('quote')
        if quote:
            change = quote.get('change', 0)
            if change > 8:
                rec = {'action': '等回调', 'position': '5%', 'reason': '涨幅过大，等待回调'}
            elif change > 3:
                rec = {'action': '分批建仓', 'position': '8%', 'reason': '温和上涨，可分批介入'}
            elif change > -3:
                rec = {'action': '立即建仓', 'position': '10%', 'reason': '价格合理，适合建仓'}
            else:
                rec = {'action': '抄底买入', 'position': '12%', 'reason': '回调较深，可以抄底'}
            result['recommendation'] = rec
            print(f"✅ 建议: {rec['action']} {rec['position']} - {rec['reason']}")
        
        return result
    
    def fetch_zsxq(self) -> str:
        """获取最新知识星球内容"""
        print("\n📚 获取知识星球最新内容...")
        topics = get_latest(5)
        return f"获取到 {len(topics)} 条最新内容"

    # ========== 板块分析接口 ==========
    def analyze_sector(self, sector: str) -> Dict:
        """
        板块分析入口
        
        Args:
            sector: 板块名称 (如: AI算力、半导体设备)
            
        Returns:
            板块分析报告
        """
        if not self.sector_analyzer:
            print("❌ 板块分析器未初始化")
            return {}
        
        print(f"\n📊 分析板块: {sector}")
        result = self.sector_analyzer.analyze_sector(sector)
        print(self.sector_analyzer.format_report(result))
        return result

    def compare_sectors(self, sectors: List[str]) -> Dict:
        """
        板块对比分析
        
        Args:
            sectors: 板块名称列表
            
        Returns:
            对比分析结果
        """
        if not self.sector_analyzer:
            print("❌ 板块分析器未初始化")
            return {}
        
        print(f"\n📊 对比 {len(sectors)} 个板块: {', '.join(sectors)}")
        result = self.sector_analyzer.compare_sectors(sectors)
        
        # 打印排序结果
        print("\n【板块强弱排序】")
        for i, sector_data in enumerate(result['sectors'], 1):
            score = sector_data['score']
            print(f"{i}. {score['rating']} {sector_data['sector']} - {score['total_score']}分")
        
        if result['top_pick']:
            print(f"\n🏆 最强板块: {result['top_pick']['sector']}")
        
        return result

    def get_sector_rotation_signals(self) -> List[Dict]:
        """
        获取板块轮动信号
        
        Returns:
            轮动信号列表
        """
        if not self.sector_analyzer:
            print("❌ 板块分析器未初始化")
            return []
        
        print("\n📊 扫描全市场轮动信号...")
        signals = self.sector_analyzer.get_rotation_signals()
        
        print(f"\n发现 {len(signals)} 个轮动信号:")
        for s in signals:
            emoji = "🟢" if s['signal'] == 'buy' else "🔴"
            print(f"  {emoji} {s['sector']}: {s['type']} 强度{s['strength']:.1f}")
        
        return signals

    def detect_market_style(self) -> Dict:
        """
        判断市场风格
        
        Returns:
            风格判断结果
        """
        if not self.sector_analyzer:
            print("❌ 板块分析器未初始化")
            return {}
        
        print("\n📊 判断市场风格...")
        style = self.sector_analyzer.detect_market_style()
        
        print(f"\n当前风格: {style['description']}")
        print(f"成长板块评分: {style['growth_score']}")
        print(f"价值板块评分: {style['value_score']}")
        print(f"配置建议: {style['suggestion']}")
        
        return style

    def generate_sector_portfolio(self, risk_level: str = 'medium') -> Dict:
        """
        生成板块配置方案
        
        Args:
            risk_level: 风险等级 (low/medium/high)
            
        Returns:
            板块配置方案
        """
        if not self.sector_analyzer:
            print("❌ 板块分析器未初始化")
            return {}
        
        print(f"\n📊 生成{risk_level}风险等级板块配置...")
        portfolio = self.sector_analyzer.generate_portfolio_config(risk_level)
        
        print(f"\n分级配置: T0={portfolio['tier_allocation']['T0']}%, "
              f"T1={portfolio['tier_allocation']['T1']}%, "
              f"T2={portfolio['tier_allocation']['T2']}%, "
              f"T3={portfolio['tier_allocation']['T3']}%")
        
        print("\n板块权重TOP5:")
        for s in portfolio['sector_weights'][:5]:
            print(f"  - {s['sector']} ({s['tier']}): {s['weight']}%")
        
        return portfolio
    
    def _get_industry_stocks(self, industry: str) -> List[str]:
        """获取行业股票列表"""
        stock_map = {
            '存储芯片': [
                '002371.SZ', '688012.SH', '688072.SH', '688120.SH',
                '688019.SH', '300054.SZ', '600584.SH', '002156.SZ', '688525.SH'
            ],
            'PCB': [
                '600183.SH', '002916.SZ', '300476.SZ', '603228.SH'
            ],
            '半导体': [
                '688012.SH', '688072.SH', '688120.SH', '688019.SH',
                '688981.SH', '603501.SH'
            ]
        }
        return stock_map.get(industry, [])
    
    def _analyze_industry_logic(self, industry: str, quotes: List[Dict]) -> Dict:
        """分析产业链逻辑"""
        # 简化的分析逻辑
        logic_map = {
            '存储芯片': {
                'driver': '长鑫2300亿投资，设备占比65%',
                'focus': '设备商',
                'risk': '订单不及预期'
            },
            'PCB': {
                'driver': 'AI服务器需求爆发，覆铜板涨价',
                'focus': '覆铜板+设备',
                'risk': '涨价不可持续'
            }
        }
        return logic_map.get(industry, {})
    
    def _generate_portfolio(self, industry: str, quotes: List[Dict]) -> List[Dict]:
        """生成投资组合建议"""
        if not quotes:
            return []
        
        # 按涨跌幅排序
        sorted_quotes = sorted(quotes, key=lambda x: x.get('change', 0), reverse=True)
        
        portfolio = []
        for i, q in enumerate(sorted_quotes[:5]):
            change = q.get('change', 0)
            if change > 5:
                action = '等回调'
                position = '8%'
            elif change > 0:
                action = '分批建仓'
                position = '10%'
            else:
                action = '加仓买入'
                position = '12%'
            
            portfolio.append({
                'symbol': q['symbol'],
                'price': q['price'],
                'change': change,
                'action': action,
                'position': position
            })
        
        return portfolio
    
    def _format_report(self, result: Dict) -> str:
        """格式化报告"""
        lines = [
            "="*80,
            f"📊 {result['industry']} 产业链分析报告",
            "="*80,
            "",
            f"生成时间: {result['timestamp']}",
            "",
            "【🔥 Exa全网最新动态】",
        ]
        
        # Exa新闻
        exa_news = result.get('exa_news', [])
        if exa_news:
            for i, news in enumerate(exa_news[:5], 1):
                title = news.get('title', '')[:60]
                lines.append(f"{i}. {title}...")
        else:
            lines.append("暂无相关新闻")
        
        lines.extend(["", "【📚 知识星球调研纪要】"])
        
        # 知识星球
        zsxq_info = result.get('zsxq_info', [])
        if zsxq_info:
            for i, topic in enumerate(zsxq_info[:3], 1):
                title = topic.get('title', '')[:60]
                lines.append(f"{i}. {title}...")
        else:
            lines.append("暂无调研纪要")
        
        lines.extend(["", "【核心逻辑】"])
        
        analysis = result.get('analysis', {})
        if analysis:
            lines.append(f"驱动因素: {analysis.get('driver', 'N/A')}")
            lines.append(f"关注重点: {analysis.get('focus', 'N/A')}")
            lines.append(f"风险提示: {analysis.get('risk', 'N/A')}")
        
        lines.extend(["", "【实时行情】"])
        
        quotes = result.get('quotes', [])
        if quotes:
            for q in quotes:
                lines.append(f"- {q['symbol']}: {q['price']:.2f} ({q['change']:+.2f}%)")
        
        lines.extend(["", "【投资组合建议】"])
        
        portfolio = result.get('portfolio', [])
        if portfolio:
            for p in portfolio:
                lines.append(f"- {p['symbol']}: {p['action']} {p['position']}")
        
        lines.extend(["", "="*80])
        
        return "\n".join(lines)


# 便捷函数
def quick_analyze(industry: str) -> Dict:
    """快速分析入口"""
    system = DounaiSystem()
    return system.analyze_industry(industry)

def get_price(symbol: str) -> Optional[Dict]:
    """快速查价入口"""
    system = DounaiSystem()
    quotes = system.get_quotes([symbol])
    return quotes[0] if quotes else None


if __name__ == "__main__":
    # 测试
    system = DounaiSystem()
    
    # 测试产业链分析
    print("\n测试存储芯片分析...")
    result = system.analyze_industry("存储芯片")
    
    print("\n测试完成!")
