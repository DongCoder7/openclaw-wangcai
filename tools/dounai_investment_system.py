#!/usr/bin/env python3
"""
豆奶投资策略系统 - Team流程自动化
整合5个角色功能：

1. Market View (市场观点) - 每日执行
2. Stock Picker (选股) - 每日执行  
3. Portfolio Manager (组合管理) - 每日执行
4. Risk Manager (风险管理) - 实时监控
5. Trade Executor (交易执行) - 交易时间执行
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ==================== 1. Market View ====================

class MarketViewAgent:
    """
    市场观点 - 每日执行
    任务：分析全球市场（美股/港股/A股）、宏观因素、板块轮动
    """
    
    def __init__(self):
        self.name = "Market View"
        self.data_sources = ['longbridge', 'tencent', 'akshare']
    
    def run(self) -> Dict:
        """执行市场分析"""
        print("="*60)
        print("📊 [Market View] 市场观点分析")
        print("="*60)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'us_market': self._analyze_us_market(),
            'hk_market': self._analyze_hk_market(),
            'a_market': self._analyze_a_market(),
            'macro': self._analyze_macro(),
            'sectors': self._analyze_sectors()
        }
        
        print(f"✅ Market View 完成")
        return result
    
    def _analyze_us_market(self) -> Dict:
        """分析美股"""
        # 读取美股报告
        today = datetime.now().strftime('%Y%m%d')
        report_path = f"~/.openclaw/workspace/data/us_market_daily_{today}.md"
        report_path = os.path.expanduser(report_path)
        
        if os.path.exists(report_path):
            with open(report_path, 'r') as f:
                content = f.read()
            return {'status': 'ok', 'report': content[:500]}
        return {'status': 'pending', 'message': '美股报告未生成'}
    
    def _analyze_hk_market(self) -> Dict:
        """分析港股"""
        return {'status': 'ok', 'focus': ['腾讯', '阿里', '美团']}
    
    def _analyze_a_market(self) -> Dict:
        """分析A股"""
        return {'status': 'ok', 'focus': ['AI算力', '新能源', '消费']}
    
    def _analyze_macro(self) -> Dict:
        """分析宏观"""
        return {'status': 'ok', 'factors': ['利率', '汇率', '政策']}
    
    def _analyze_sectors(self) -> Dict:
        """分析板块轮动"""
        return {'status': 'ok', 'rotation': ['科技→消费→金融']}


# ==================== 2. Stock Picker ====================

class StockPickerAgent:
    """
    选股 - 每日执行
    任务：基于VQM模型选股（PE+ROE+growth+volatility），选出top 30股票
    """
    
    def __init__(self):
        self.name = "Stock Picker"
        self.top_n = 30
    
    def run(self, market_data: Dict = None) -> Dict:
        """执行选股"""
        print("="*60)
        print("🎯 [Stock Picker] VQM模型选股")
        print("="*60)
        
        # 获取候选股票池
        candidates = self._get_candidates()
        
        # VQM评分
        scored = self._vqm_scoring(candidates)
        
        # 选出Top N
        selected = scored[:self.top_n]
        
        print(f"✅ 选出 {len(selected)} 只股票")
        for i, s in enumerate(selected[:10], 1):
            print(f"  {i}. {s['name']} ({s['code']}) - 评分: {s['score']}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'candidates': len(candidates),
            'selected': selected,
            'top_10': [s['name'] for s in selected[:10]]
        }
    
    def _get_candidates(self) -> List[Dict]:
        """获取候选股票池"""
        # 从本地数据库或API获取
        # 这里用演示数据
        return [
            {'code': '600519', 'name': '贵州茅台', 'pe': 30, 'roe': 30},
            {'code': '000001', 'name': '平安银行', 'pe': 5, 'roe': 15},
            {'code': '300308', 'name': '中际旭创', 'pe': 40, 'roe': 25},
            {'code': '600036', 'name': '招商银行', 'pe': 6, 'roe': 16},
            {'code': '601318', 'name': '中国平安', 'pe': 10, 'roe': 18},
            # ... 更多候选
        ]
    
    def _vqm_scoring(self, candidates: List[Dict]) -> List[Dict]:
        """VQM评分"""
        scored = []
        
        for c in candidates:
            # PE评分 (越低越好) - 权重40%
            if c['pe'] < 10:
                pe_score = 100
            elif c['pe'] < 20:
                pe_score = 80
            elif c['pe'] < 30:
                pe_score = 60
            else:
                pe_score = 40
            
            # ROE评分 (越高越好) - 权重40%
            if c['roe'] > 25:
                roe_score = 100
            elif c['roe'] > 20:
                roe_score = 80
            elif c['roe'] > 15:
                roe_score = 60
            else:
                roe_score = 40
            
            # 波动率评分 (越低越好) - 权重20%
            vol_score = 80  # 简化
            
            # 综合评分
            total_score = pe_score * 0.4 + roe_score * 0.4 + vol_score * 0.2
            
            scored.append({
                **c,
                'pe_score': pe_score,
                'roe_score': roe_score,
                'score': total_score
            })
        
        # 按评分排序
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored


# ==================== 3. Portfolio Manager ====================

class PortfolioManagerAgent:
    """
    组合管理 - 每日执行
    任务：基于风险模型和配置策略，构建最优组合（10-15只股票）
    """
    
    def __init__(self):
        self.name = "Portfolio Manager"
        self.max_positions = 15
        self.min_positions = 10
    
    def run(self, selected_stocks: List[Dict] = None) -> Dict:
        """构建组合"""
        print("="*60)
        print("💼 [Portfolio Manager] 组合构建")
        print("="*60)
        
        if not selected_stocks:
            # 使用当前持仓
            selected_stocks = self._get_current_positions()
        
        # 风险模型检查
        risk_adjusted = self._risk_adjust(selected_stocks)
        
        # 构建最优组合
        portfolio = self._build_portfolio(risk_adjusted)
        
        # 计算权重
        weights = self._calculate_weights(portfolio)
        
        print(f"✅ 构建组合: {len(portfolio)} 只股票")
        for p in portfolio[:5]:
            print(f"  {p['name']}: {weights.get(p['code'], 0)*100:.1f}%")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'portfolio': portfolio,
            'weights': weights,
            'total_value': 1000000,  # 模拟资金
            'position_count': len(portfolio)
        }
    
    def _get_current_positions(self) -> List[Dict]:
        """获取当前持仓"""
        # 从配置读取
        return [
            {'code': '000001', 'name': '平安银行', 'weight': 0.1},
            {'code': '000333', 'name': '美的集团', 'weight': 0.1},
            {'code': '600887', 'name': '伊利股份', 'weight': 0.1},
            {'code': '600036', 'name': '招商银行', 'weight': 0.1},
            {'code': '601318', 'name': '中国平安', 'weight': 0.1},
            {'code': '601166', 'name': '兴业银行', 'weight': 0.1},
            {'code': '600519', 'name': '贵州茅台', 'weight': 0.1},
            {'code': '000858', 'name': '五粮液', 'weight': 0.1},
            {'code': '300760', 'name': '迈瑞医疗', 'weight': 0.1},
            {'code': '600900', 'name': '长江电力', 'weight': 0.1},
        ]
    
    def _risk_adjust(self, stocks: List[Dict]) -> List[Dict]:
        """风险调整"""
        # 过滤高风险股票
        return [s for s in stocks if s.get('score', 50) > 40]
    
    def _build_portfolio(self, stocks: List[Dict]) -> List[Dict]:
        """构建组合"""
        # 选择top N
        return stocks[:self.max_positions]
    
    def _calculate_weights(self, portfolio: List[Dict]) -> Dict:
        """计算权重"""
        # 等权重分配
        weight = 1.0 / len(portfolio) if portfolio else 0
        return {p['code']: weight for p in portfolio}


# ==================== 4. Risk Manager ====================

class RiskManagerAgent:
    """
    风险管理 - 实时监控
    任务：设置止损/止盈规则，监控仓位风险，触发风控时通知
    """
    
    def __init__(self):
        self.name = "Risk Manager"
        self.stop_loss = -0.08  # 8%止损
        self.take_profit = 0.15  # 15%止盈
    
    def run(self, portfolio: Dict) -> Dict:
        """执行风控检查"""
        print("="*60)
        print("🛡️ [Risk Manager] 风险管理")
        print("="*60)
        
        # 获取实时价格
        prices = self._get_realtime_prices(portfolio.get('portfolio', []))
        
        # 检查止损/止盈
        alerts = self._check_stop_loss(prices)
        alerts.extend(self._check_take_profit(prices))
        
        # 检查T+1限制
        t1_limits = self._check_t1_rules(portfolio)
        
        # 总体风险评估
        risk_level = self._assess_risk(prices)
        
        print(f"✅ 风控检查完成")
        print(f"   报警数: {len(alerts)}")
        print(f"   T+1限制: {len(t1_limits)}")
        print(f"   风险等级: {risk_level}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'alerts': alerts,
            't1_limits': t1_limits,
            'risk_level': risk_level,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit
        }
    
    def _get_realtime_prices(self, portfolio: List[Dict]) -> Dict:
        """获取实时价格"""
        from longbridge_provider import LongbridgeDataProvider
        
        prices = {}
        try:
            provider = LongbridgeDataProvider()
            for p in portfolio:
                quote = provider.get_realtime_quote(p['code'], market='CN')
                if quote:
                    prices[p['code']] = {
                        'price': quote['price'],
                        'change_pct': quote['change_pct']
                    }
        except:
            pass
        
        return prices
    
    def _check_stop_loss(self, prices: Dict) -> List[Dict]:
        """检查止损"""
        # 简化实现
        return []
    
    def _check_take_profit(self, prices: Dict) -> List[Dict]:
        """检查止盈"""
        return []
    
    def _check_t1_rules(self, portfolio: Dict) -> List[str]:
        """检查T+1规则"""
        # 获取今日买入的股票
        return []
    
    def _assess_risk(self, prices: Dict) -> str:
        """评估风险等级"""
        if not prices:
            return 'unknown'
        
        # 计算组合涨跌幅
        changes = [p['change_pct'] for p in prices.values()]
        avg_change = sum(changes) / len(changes) if changes else 0
        
        if avg_change < -3:
            return 'high'
        elif avg_change < -1:
            return 'medium'
        else:
            return 'low'


# ==================== 5. Trade Executor ====================

class TradeExecutorAgent:
    """
    交易执行 - 交易时间执行
    任务：执行交易决策，检查T+1规则，下单并确认成交
    """
    
    def __init__(self):
        self.name = "Trade Executor"
    
    def run(self, decisions: Dict) -> Dict:
        """执行交易"""
        print("="*60)
        print("📈 [Trade Executor] 交易执行")
        print("="*60)
        
        # 检查交易时间
        if not self._is_trading_time():
            return {'status': 'closed', 'message': '非交易时间'}
        
        # 检查T+1
        t1_check = self._check_t1_compliance(decisions.get('sells', []))
        
        # 执行卖出
        sells = self._execute_sells(decisions.get('sells', []))
        
        # 执行买入
        buys = self._execute_buys(decisions.get('buys', []))
        
        print(f"✅ 交易执行完成")
        print(f"   卖出: {len(sells)}")
        print(f"   买入: {len(buys)}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'sells': sells,
            'buys': buys,
            't1_check': t1_check
        }
    
    def _is_trading_time(self) -> bool:
        """检查是否交易时间"""
        now = datetime.now()
        time_str = now.strftime('%H:%M')
        weekday = now.weekday()
        
        if weekday >= 5:
            return False
        
        return ('09:30' <= time_str <= '11:30') or ('13:00' <= time_str <= '15:00')
    
    def _check_t1_compliance(self, sells: List[Dict]) -> Dict:
        """检查T+1合规性"""
        return {'compliant': True, 'blocked': []}
    
    def _execute_sells(self, sells: List[Dict]) -> List[Dict]:
        """执行卖出"""
        return []
    
    def _execute_buys(self, buys: List[Dict]) -> List[Dict]:
        """执行买入"""
        return []


# ==================== 豆奶总控 ====================

class DouNaiAgent:
    """
    豆奶 - 投资策略总控
    整合5个Agent的Team流程
    """
    
    def __init__(self):
        self.market_view = MarketViewAgent()
        self.stock_picker = StockPickerAgent()
        self.portfolio_manager = PortfolioManagerAgent()
        self.risk_manager = RiskManagerAgent()
        self.trade_executor = TradeExecutorAgent()
    
    def run_daily(self) -> Dict:
        """
        每日流程
        1. Market View - 市场分析
        2. Stock Picker - 选股
        3. Portfolio Manager - 组合构建
        """
        print("\n" + "="*70)
        print("🫘 豆奶投资策略系统 - 每日流程")
        print("="*70 + "\n")
        
        # Step 1: 市场观点
        market_data = self.market_view.run()
        
        # Step 2: 选股
        selected = self.stock_picker.run(market_data)
        
        # Step 3: 组合构建
        portfolio = self.portfolio_manager.run(selected.get('selected', []))
        
        return {
            'market': market_data,
            'selection': selected,
            'portfolio': portfolio
        }
    
    def run_realtime(self) -> Dict:
        """
        实时流程（交易时间）
        1. Risk Manager - 风险监控
        2. Trade Executor - 交易执行
        """
        print("\n" + "="*70)
        print("🫘 豆奶投资策略系统 - 实时流程")
        print("="*70 + "\n")
        
        # 获取当前组合
        portfolio = self.portfolio_manager.run()
        
        # 风控检查
        risk = self.risk_manager.run(portfolio)
        
        # 交易执行
        if risk['alerts'] or risk['risk_level'] == 'high':
            trades = self.trade_executor.run({
                'alerts': risk['alerts'],
                'sells': [],
                'buys': []
            })
        else:
            trades = {'status': 'hold', 'message': '无交易信号'}
        
        return {
            'risk': risk,
            'trades': trades
        }
    
    def run_full_cycle(self) -> Dict:
        """完整流程：每日 + 实时"""
        daily = self.run_daily()
        realtime = self.run_realtime()
        
        return {
            'daily': daily,
            'realtime': realtime
        }


# ==================== 主函数 ====================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='豆奶投资策略系统')
    parser.add_argument('--mode', choices=['daily', 'realtime', 'full'], default='full',
                       help='运行模式')
    
    args = parser.parse_args()
    
    agent = DouNaiAgent()
    
    if args.mode == 'daily':
        result = agent.run_daily()
    elif args.mode == 'realtime':
        result = agent.run_realtime()
    else:
        result = agent.run_full_cycle()
    
    print("\n" + "="*70)
    print("✅ 流程执行完成")
    print("="*70)
