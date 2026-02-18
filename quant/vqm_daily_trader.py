#!/usr/bin/env python3
"""
VQM策略 - 日级动态交易框架
支持: 逐步建仓、日级调仓、动态仓位管理、精细化风控
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    ADD_POSITION = "add_position"  # 加仓
    REDUCE_POSITION = "reduce_position"  # 减仓

@dataclass
class Position:
    """持仓信息"""
    code: str
    name: str
    shares: int
    avg_cost: float
    current_price: float
    market_value: float
    weight: float  # 占组合权重
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_date: str
    last_trade_date: str
    trade_count: int  # 交易次数（用于逐步建仓）

@dataclass
class TradeSignal:
    """交易信号"""
    date: str
    code: str
    signal_type: SignalType
    target_weight: float  # 目标权重
    current_weight: float  # 当前权重
    reason: str
    confidence: float  # 置信度 0-1

@dataclass
class DailyState:
    """每日状态"""
    date: str
    total_value: float
    cash: float
    positions_value: float
    positions: Dict[str, Position]
    signals: List[TradeSignal]
    trades_executed: List[Dict]
    metrics: Dict  # 风险指标

class VQMDailyTrader:
    """
    VQM日级动态交易引擎
    
    核心功能:
    1. 逐步建仓: 支持分批买入，而非一次性建仓
    2. 日级调仓: 每日评估，动态调整
    3. 动态仓位: 根据市场环境调整总仓位
    4. 精细化风控: 个股止损+组合止损+回撤控制
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.initial_capital = config.get('initial_capital', 1000000)
        self.cash = self.initial_capital
        self.positions: Dict[str, Position] = {}
        self.daily_states: List[DailyState] = []
        self.trade_history: List[Dict] = []
        
        # 风控参数
        self.max_total_position = config.get('max_total_position', 0.95)  # 最大总仓位95%
        self.min_cash_ratio = config.get('min_cash_ratio', 0.05)  # 最小现金5%
        self.single_stock_max_weight = config.get('single_stock_max_weight', 0.15)  # 个股最大15%
        self.single_stock_min_weight = config.get('single_stock_min_weight', 0.05)  # 个股最小5%
        
        # 止损参数
        self.stop_loss_individual = config.get('stop_loss_individual', 0.92)  # 个股止损-8%
        self.stop_loss_portfolio = config.get('stop_loss_portfolio', 0.90)  # 组合止损-10%
        self.max_drawdown_limit = config.get('max_drawdown_limit', 0.15)  # 最大回撤限制15%
        
        # 建仓参数
        self.position_building_steps = config.get('position_building_steps', 3)  # 分3批建仓
        self.position_building_interval = config.get('position_building_interval', 5)  # 间隔5天
        
        # 调仓参数
        self.rebalance_threshold = config.get('rebalance_threshold', 0.02)  # 权重偏离2%触发调仓
        self.min_holding_days = config.get('min_holding_days', 20)  # 最少持有20天(T+1考虑)
        
        # VQM选股参数
        self.pe_weight = config.get('pe_weight', 0.6)
        self.roe_weight = config.get('roe_weight', 0.4)
        self.top_n_select = config.get('top_n_select', 15)  # 选出15只，逐步建仓
        self.target_positions = config.get('target_positions', 10)  # 最终持仓10只
        
        # 状态跟踪
        self.peak_value = self.initial_capital
        self.current_drawdown = 0.0
        self.consecutive_loss_days = 0
        
    def calculate_vqm_score(self, df: pd.DataFrame, date: str) -> pd.DataFrame:
        """计算VQM得分"""
        day_data = df[df['date'] == date].copy()
        if len(day_data) == 0:
            return pd.DataFrame()
        
        # PE排名（越低越好）
        day_data['pe_rank'] = day_data['pe'].rank(pct=True, ascending=True)
        
        # ROE排名（越高越好）
        day_data['roe_rank'] = day_data['roe'].rank(pct=True, ascending=False)
        
        # VQM得分
        day_data['vqm_score'] = (
            day_data['pe_rank'] * self.pe_weight +
            day_data['roe_rank'] * self.roe_weight
        )
        
        return day_data.sort_values('vqm_score', ascending=False)
    
    def calculate_portfolio_metrics(self) -> Dict:
        """计算组合风险指标"""
        total_value = self.cash + sum(p.market_value for p in self.positions.values())
        
        # 更新峰值和回撤
        if total_value > self.peak_value:
            self.peak_value = total_value
        self.current_drawdown = (self.peak_value - total_value) / self.peak_value
        
        # 计算组合Beta（简化版）
        portfolio_beta = 0.85  # 假设低Beta
        
        # 计算行业集中度
        sectors = {}
        for p in self.positions.values():
            sector = self._get_sector(p.code)
            sectors[sector] = sectors.get(sector, 0) + p.weight
        max_sector_concentration = max(sectors.values()) if sectors else 0
        
        return {
            'total_value': total_value,
            'cash_ratio': self.cash / total_value,
            'position_ratio': 1 - self.cash / total_value,
            'current_drawdown': self.current_drawdown,
            'peak_value': self.peak_value,
            'portfolio_beta': portfolio_beta,
            'max_sector_concentration': max_sector_concentration,
            'position_count': len(self.positions),
        }
    
    def _get_sector(self, code: str) -> str:
        """获取股票行业（简化版）"""
        # 根据代码前缀判断（实际应从数据库获取）
        code_num = int(code.replace('ST', ''))
        sectors = ['银行', '消费', '医药', '科技', '能源', '制造']
        return sectors[code_num % len(sectors)]
    
    def generate_signals(self, df: pd.DataFrame, date: str) -> List[TradeSignal]:
        """生成交易信号"""
        signals = []
        metrics = self.calculate_portfolio_metrics()
        
        # 1. 检查组合风控
        if metrics['current_drawdown'] > self.max_drawdown_limit:
            # 回撤过大，减仓
            for code, pos in self.positions.items():
                signals.append(TradeSignal(
                    date=date,
                    code=code,
                    signal_type=SignalType.REDUCE_POSITION,
                    target_weight=pos.weight * 0.5,  # 减半
                    current_weight=pos.weight,
                    reason=f"组合回撤过大({metrics['current_drawdown']:.1%})",
                    confidence=0.9
                ))
            return signals
        
        # 2. 检查个股止损
        for code, pos in self.positions.items():
            if pos.unrealized_pnl_pct < -(1 - self.stop_loss_individual):
                signals.append(TradeSignal(
                    date=date,
                    code=code,
                    signal_type=SignalType.SELL,
                    target_weight=0,
                    current_weight=pos.weight,
                    reason=f"个股止损({pos.unrealized_pnl_pct:.1%})",
                    confidence=1.0
                ))
        
        # 3. VQM选股，生成买入/加仓信号
        ranked_stocks = self.calculate_vqm_score(df, date)
        if len(ranked_stocks) == 0:
            return signals
        
        top_stocks = ranked_stocks.head(self.top_n_select)
        
        # 计算目标权重（等权重）
        target_weight_per_stock = min(
            1.0 / self.target_positions,
            self.single_stock_max_weight
        )
        
        for _, stock in top_stocks.iterrows():
            code = stock['code']
            current_price = stock['close']
            
            if code in self.positions:
                # 已有持仓，检查是否需要调仓
                pos = self.positions[code]
                current_weight = pos.weight
                
                # 如果权重偏离超过阈值，调整
                if abs(current_weight - target_weight_per_stock) > self.rebalance_threshold:
                    if current_weight < target_weight_per_stock:
                        # 加仓
                        signals.append(TradeSignal(
                            date=date,
                            code=code,
                            signal_type=SignalType.ADD_POSITION,
                            target_weight=target_weight_per_stock,
                            current_weight=current_weight,
                            reason="VQM排名前列，权重不足",
                            confidence=stock['vqm_score']
                        ))
                    else:
                        # 减仓
                        signals.append(TradeSignal(
                            date=date,
                            code=code,
                            signal_type=SignalType.REDUCE_POSITION,
                            target_weight=target_weight_per_stock,
                            current_weight=current_weight,
                            reason="权重过高，再平衡",
                            confidence=0.7
                        ))
            else:
                # 新股票，检查是否可以新建仓
                if len(self.positions) < self.target_positions:
                    # 检查现金是否充足
                    required_cash = metrics['total_value'] * target_weight_per_stock * 0.3  # 首批30%
                    if self.cash >= required_cash:
                        signals.append(TradeSignal(
                            date=date,
                            code=code,
                            signal_type=SignalType.BUY,
                            target_weight=target_weight_per_stock,
                            current_weight=0,
                            reason="VQM排名前列，新建仓",
                            confidence=stock['vqm_score']
                        ))
        
        # 4. 检查是否需要清仓不在top list的股票
        top_codes = set(top_stocks['code'].values)
        for code, pos in self.positions.items():
            if code not in top_codes:
                # 检查持有天数
                holding_days = (datetime.strptime(date, '%Y-%m-%d') - 
                              datetime.strptime(pos.entry_date, '%Y-%m-%d')).days
                if holding_days > self.min_holding_days:
                    signals.append(TradeSignal(
                        date=date,
                        code=code,
                        signal_type=SignalType.SELL,
                        target_weight=0,
                        current_weight=pos.weight,
                        reason="不在VQM前15名，调出",
                        confidence=0.8
                    ))
        
        return signals
    
    def execute_signals(self, signals: List[TradeSignal], df: pd.DataFrame, date: str) -> List[Dict]:
        """执行交易信号"""
        executed_trades = []
        day_data = df[df['date'] == date]
        metrics = self.calculate_portfolio_metrics()
        
        for signal in signals:
            stock_data = day_data[day_data['code'] == signal.code]
            if len(stock_data) == 0:
                continue
            
            price = stock_data['close'].values[0]
            total_value = metrics['total_value']
            
            if signal.signal_type == SignalType.BUY:
                # 新建仓 - 分批买入第一批（30%）
                target_value = total_value * signal.target_weight * 0.3
                shares = int(target_value / price / 100) * 100  # 整手买入
                cost = shares * price * 1.001  # 含手续费
                
                if self.cash >= cost and shares > 0:
                    self.cash -= cost
                    self.positions[signal.code] = Position(
                        code=signal.code,
                        name=signal.code,  # 简化
                        shares=shares,
                        avg_cost=price,
                        current_price=price,
                        market_value=shares * price,
                        weight=shares * price / total_value,
                        unrealized_pnl=0,
                        unrealized_pnl_pct=0,
                        entry_date=date,
                        last_trade_date=date,
                        trade_count=1
                    )
                    executed_trades.append({
                        'date': date,
                        'code': signal.code,
                        'action': 'BUY',
                        'price': price,
                        'shares': shares,
                        'amount': shares * price,
                        'reason': signal.reason
                    })
            
            elif signal.signal_type == SignalType.ADD_POSITION:
                # 加仓
                if signal.code not in self.positions:
                    continue
                pos = self.positions[signal.code]
                target_value = total_value * signal.target_weight
                current_value = pos.market_value
                add_value = (target_value - current_value) * 0.5  # 每次加50%缺口
                
                shares = int(add_value / price / 100) * 100
                cost = shares * price * 1.001
                
                if self.cash >= cost and shares > 0:
                    # 更新平均成本
                    total_cost = pos.avg_cost * pos.shares + price * shares
                    total_shares = pos.shares + shares
                    new_avg_cost = total_cost / total_shares
                    
                    self.cash -= cost
                    pos.shares = total_shares
                    pos.avg_cost = new_avg_cost
                    pos.last_trade_date = date
                    pos.trade_count += 1
                    
                    executed_trades.append({
                        'date': date,
                        'code': signal.code,
                        'action': 'ADD',
                        'price': price,
                        'shares': shares,
                        'amount': shares * price,
                        'reason': signal.reason
                    })
            
            elif signal.signal_type == SignalType.REDUCE_POSITION:
                # 减仓
                if signal.code not in self.positions:
                    continue
                pos = self.positions[signal.code]
                target_value = total_value * signal.target_weight
                reduce_value = pos.market_value - target_value
                shares = int(reduce_value / price / 100) * 100
                
                if shares >= 100:
                    shares = min(shares, pos.shares)
                    proceeds = shares * price * 0.999  # 扣除手续费
                    self.cash += proceeds
                    pos.shares -= shares
                    
                    if pos.shares == 0:
                        del self.positions[signal.code]
                    else:
                        pos.last_trade_date = date
                    
                    executed_trades.append({
                        'date': date,
                        'code': signal.code,
                        'action': 'REDUCE',
                        'price': price,
                        'shares': shares,
                        'amount': shares * price,
                        'reason': signal.reason
                    })
            
            elif signal.signal_type == SignalType.SELL:
                # 清仓
                if signal.code not in self.positions:
                    continue
                pos = self.positions[signal.code]
                proceeds = pos.shares * price * 0.999
                self.cash += proceeds
                
                executed_trades.append({
                    'date': date,
                    'code': signal.code,
                    'action': 'SELL',
                    'price': price,
                    'shares': pos.shares,
                    'amount': pos.shares * price,
                    'pnl': (price - pos.avg_cost) * pos.shares,
                    'pnl_pct': (price - pos.avg_cost) / pos.avg_cost,
                    'reason': signal.reason
                })
                
                del self.positions[signal.code]
        
        return executed_trades
    
    def update_positions(self, df: pd.DataFrame, date: str):
        """更新持仓市值和盈亏"""
        day_data = df[df['date'] == date]
        total_value = self.cash
        
        for code, pos in self.positions.items():
            stock_data = day_data[day_data['code'] == code]
            if len(stock_data) > 0:
                current_price = stock_data['close'].values[0]
                pos.current_price = current_price
                pos.market_value = pos.shares * current_price
                pos.unrealized_pnl = (current_price - pos.avg_cost) * pos.shares
                pos.unrealized_pnl_pct = (current_price - pos.avg_cost) / pos.avg_cost
                total_value += pos.market_value
        
        # 更新权重
        for pos in self.positions.values():
            pos.weight = pos.market_value / total_value if total_value > 0 else 0
        
        return total_value
    
    def run_daily_backtest(self, df: pd.DataFrame, start_date: str, end_date: str) -> List[DailyState]:
        """运行日级回测"""
        print(f"\n{'='*70}")
        print(f"🚀 VQM日级动态交易回测")
        print(f"   时间范围: {start_date} ~ {end_date}")
        print(f"   初始资金: {self.initial_capital/10000:.0f}万")
        print(f"{'='*70}\n")
        
        # 筛选日期范围
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        backtest_data = df[mask].copy()
        dates = sorted(backtest_data['date'].unique())
        
        daily_states = []
        
        for i, date in enumerate(dates):
            date_str = date.strftime('%Y-%m-%d') if isinstance(date, pd.Timestamp) else str(date)[:10]
            
            # 1. 更新持仓市值
            total_value = self.update_positions(backtest_data, date_str)
            
            # 2. 生成交易信号
            signals = self.generate_signals(backtest_data, date_str)
            
            # 3. 执行交易
            executed_trades = self.execute_signals(signals, backtest_data, date_str)
            self.trade_history.extend(executed_trades)
            
            # 4. 重新计算市值
            total_value = self.update_positions(backtest_data, date_str)
            
            # 5. 计算风险指标
            metrics = self.calculate_portfolio_metrics()
            
            # 6. 记录每日状态
            state = DailyState(
                date=date_str,
                total_value=total_value,
                cash=self.cash,
                positions_value=total_value - self.cash,
                positions=self.positions.copy(),
                signals=signals,
                trades_executed=executed_trades,
                metrics=metrics
            )
            daily_states.append(state)
            
            # 每日汇报（每30天或重要日期）
            if i % 30 == 0 or len(executed_trades) > 0 or i == len(dates) - 1:
                self._daily_report(state, i + 1, len(dates))
        
        return daily_states
    
    def _daily_report(self, state: DailyState, day_num: int, total_days: int):
        """每日汇报"""
        print(f"\n📅 Day {day_num}/{total_days}: {state.date}")
        print(f"   总资产: {state.total_value/10000:.2f}万 (现金: {state.cash/10000:.2f}万)")
        print(f"   仓位: {state.metrics['position_ratio']:.1%} | 回撤: {state.metrics['current_drawdown']:.1%}")
        print(f"   持仓数: {len(state.positions)} | 今日交易: {len(state.trades_executed)}笔")
        
        if state.trades_executed:
            for trade in state.trades_executed:
                emoji = "🟢" if trade['action'] in ['BUY', 'ADD'] else "🔴"
                print(f"   {emoji} {trade['action']}: {trade['code']} {trade['shares']}股 @ {trade['price']:.2f}")
        
        if state.positions:
            print(f"   持仓详情:")
            for code, pos in list(state.positions.items())[:3]:  # 只显示前3只
                pnl_emoji = "🟢" if pos.unrealized_pnl_pct >= 0 else "🔴"
                print(f"      {code}: {pos.weight:.1%}权重 {pos.unrealized_pnl_pct:+.1%}{pnl_emoji}")
    
    def generate_report(self, daily_states: List[DailyState]) -> str:
        """生成回测报告"""
        if not daily_states:
            return "无数据"
        
        first_state = daily_states[0]
        last_state = daily_states[-1]
        
        total_return = (last_state.total_value - self.initial_capital) / self.initial_capital
        total_days = len(daily_states)
        annual_return = (1 + total_return) ** (252 / total_days) - 1
        
        # 计算最大回撤
        peak = self.initial_capital
        max_drawdown = 0
        for state in daily_states:
            if state.total_value > peak:
                peak = state.total_value
            dd = (peak - state.total_value) / peak
            if dd > max_drawdown:
                max_drawdown = dd
        
        # 计算胜率（日度）
        daily_returns = []
        for i in range(1, len(daily_states)):
            ret = (daily_states[i].total_value - daily_states[i-1].total_value) / daily_states[i-1].total_value
            daily_returns.append(ret)
        
        win_rate = sum(1 for r in daily_returns if r > 0) / len(daily_returns)
        volatility = np.std(daily_returns) * np.sqrt(252)
        sharpe = annual_return / volatility if volatility > 0 else 0
        
        # 交易统计
        buy_count = sum(1 for t in self.trade_history if t['action'] == 'BUY')
        sell_count = sum(1 for t in self.trade_history if t['action'] == 'SELL')
        add_count = sum(1 for t in self.trade_history if t['action'] == 'ADD')
        
        report = f"""
{'='*70}
📊 VQM日级动态交易回测报告
{'='*70}

## 1. 回测概况

| 指标 | 数值 |
|:-----|-----:|
| 回测区间 | {first_state.date} ~ {last_state.date} |
| 交易日数 | {total_days} 天 |
| 初始资金 | {self.initial_capital/10000:.0f} 万 |
| 最终资金 | {last_state.total_value/10000:.2f} 万 |
| 总收益率 | {total_return:+.2%} |
| 年化收益率 | {annual_return:+.2%} |
| 最大回撤 | {max_drawdown:.2%} |
| 夏普比率 | {sharpe:.3f} |
| 日胜率 | {win_rate:.1%} |

## 2. 交易统计

| 交易类型 | 次数 |
|:---------|:----:|
| 新建仓(BUY) | {buy_count} |
| 加仓(ADD) | {add_count} |
| 卖出(SELL) | {sell_count} |
| 总交易次数 | {len(self.trade_history)} |

## 3. 最终持仓

| 代码 | 股数 | 市值 | 权重 | 盈亏 |
|:-----|:----:|:----:|:----:|:----:|
"""
        
        for code, pos in last_state.positions.items():
            report += f"| {code} | {pos.shares} | {pos.market_value/10000:.2f}万 | {pos.weight:.1%} | {pos.unrealized_pnl_pct:+.1%} |\n"
        
        report += f"""
## 4. 策略参数

| 参数 | 设置值 |
|:-----|:-------|
| PE权重 | {self.pe_weight} |
| ROE权重 | {self.roe_weight} |
| 目标持仓数 | {self.target_positions} |
| 个股最大权重 | {self.single_stock_max_weight} |
| 个股止损线 | {self.stop_loss_individual} |
| 组合止损线 | {self.stop_loss_portfolio} |
| 建仓批次 | {self.position_building_steps} |
| 调仓阈值 | {self.rebalance_threshold} |

{'='*70}
"""
        
        return report


# 演示函数
def demo_daily_trading():
    """演示日级交易"""
    print("="*70)
    print("🚀 VQM日级动态交易框架演示")
    print("="*70)
    
    # 简化版数据生成
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', end='2023-06-30', freq='B')
    
    stocks_data = []
    for i in range(20):
        code = f'ST{i:04d}'
        base_pe = np.random.uniform(8, 30)
        base_roe = np.random.uniform(8, 22)
        
        price = 50.0
        for date in dates:
            price *= (1 + np.random.normal(0.0005, 0.015))
            stocks_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'code': code,
                'close': price,
                'pe': base_pe * (1 + np.random.normal(0, 0.02)),
                'roe': base_roe * (1 + np.random.normal(0, 0.015)),
            })
    
    df = pd.DataFrame(stocks_data)
    
    # 配置
    config = {
        'initial_capital': 1000000,
        'pe_weight': 0.6,
        'roe_weight': 0.4,
        'target_positions': 5,
        'single_stock_max_weight': 0.20,
        'stop_loss_individual': 0.92,
        'position_building_steps': 3,
    }
    
    # 运行回测
    trader = VQMDailyTrader(config)
    daily_states = trader.run_daily_backtest(df, '2023-01-01', '2023-06-30')
    
    # 生成报告
    report = trader.generate_report(daily_states)
    print(report)
    
    # 保存
    with open('quant/vqm_daily_trading_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("\n✅ 报告已保存至: quant/vqm_daily_trading_report.md")


if __name__ == '__main__':
    demo_daily_trading()
