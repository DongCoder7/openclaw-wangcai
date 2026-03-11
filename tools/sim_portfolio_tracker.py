#!/root/.openclaw/workspace/venv/bin/python3
"""
模拟盘跟踪系统 v3 - 全市场5000+股票，实时数据
策略: v23优化成果 (仓位100%, 止损5%, 持仓3只)
"""
import json
import os
import sys
import sqlite3
import pandas as pd
import subprocess
from datetime import datetime, timedelta

sys.path.insert(0, '/root/.openclaw/workspace/tools')

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
PORTFOLIO_FILE = '/root/.openclaw/workspace/data/sim_portfolio.json'
USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'

STRATEGY_CONFIG = {
    'position_ratio': 1.0,
    'stop_loss': 0.05,
    'max_positions': 3,
    'initial_capital': 1000000.0
}

class DataProvider:
    """数据提供 - 支持全市场5000+股票"""
    
    def get_all_stock_codes(self):
        """从数据库获取所有股票代码"""
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql("SELECT DISTINCT ts_code FROM stock_factors WHERE ret_20 IS NOT NULL", conn)
            conn.close()
            return df['ts_code'].tolist()
        except Exception as e:
            print(f'获取股票列表失败: {e}')
            return []
    
    def get_stock_factors(self, codes):
        """获取股票因子数据"""
        try:
            conn = sqlite3.connect(DB_PATH)
            latest_date = pd.read_sql(
                "SELECT MAX(trade_date) FROM stock_factors", conn
            ).iloc[0, 0]
            
            # 分批查询避免SQL过长
            batch_size = 500
            all_data = []
            
            for i in range(0, len(codes), batch_size):
                batch = codes[i:i+batch_size]
                codes_str = "','".join(batch)
                
                df = pd.read_sql(f"""
                    SELECT e.ts_code, 
                           f.ret_20, f.ret_60, f.vol_20, 
                           f.money_flow, f.price_pos_20, f.mom_accel
                    FROM stock_efinance e
                    LEFT JOIN stock_factors f ON e.ts_code = f.ts_code 
                        AND e.trade_date = f.trade_date
                    WHERE e.ts_code IN ('{codes_str}')
                    AND e.trade_date = '{latest_date}'
                    AND f.ret_20 IS NOT NULL
                """, conn)
                
                all_data.append(df)
            
            conn.close()
            
            if all_data:
                return pd.concat(all_data, ignore_index=True)
            return pd.DataFrame()
            
        except Exception as e:
            print(f'获取因子数据失败: {e}')
            return pd.DataFrame()
    
    def get_realtime_quotes_batch(self, codes):
        """批量获取实时行情 - 使用腾讯API"""
        import requests
        import re
        
        results = {}
        batch_size = 800  # 腾讯API支持批量查询
        
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i+batch_size]
            
            # 转换代码格式
            symbols = []
            code_mapping = {}  # 记录原始code和转换后的symbol对应关系
            
            for code in batch:
                clean_code = code.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
                if clean_code.startswith('6'):
                    symbol = f"sh{clean_code}"
                elif clean_code.startswith('0') or clean_code.startswith('3') or clean_code.startswith('4') or clean_code.startswith('8'):
                    symbol = f"sz{clean_code}"
                else:
                    symbol = clean_code
                symbols.append(symbol)
                code_mapping[symbol] = code  # 记录映射
            
            try:
                url = f"https://qt.gtimg.cn/q={','.join(symbols)}"
                response = requests.get(url, timeout=60)
                
                if response.status_code == 200:
                    # 解析返回数据 - 腾讯返回格式: v_sh600000="1~股票名~代码~当前价~..."
                    lines = response.text.strip().split(';')
                    for line in lines:
                        if 'v_' in line and '"' in line and '=' in line:
                            try:
                                # 提取symbol (v_sh600000)
                                var_name = line.split('=')[0].strip()
                                # 从var_name提取代码 (sh600000 -> 600000.SH)
                                if var_name.startswith('v_sh'):
                                    extracted_code = var_name.replace('v_sh', '')
                                    original_code = None
                                    for sym, orig in code_mapping.items():
                                        if extracted_code in sym:
                                            original_code = orig
                                            break
                                elif var_name.startswith('v_sz'):
                                    extracted_code = var_name.replace('v_sz', '')
                                    original_code = None
                                    for sym, orig in code_mapping.items():
                                        if extracted_code in sym:
                                            original_code = orig
                                            break
                                else:
                                    continue
                                
                                if not original_code:
                                    continue
                                
                                # 解析数据
                                data_part = line.split('"')[1]
                                parts = data_part.split('~')
                                
                                if len(parts) > 45:
                                    results[original_code] = {
                                        'code': original_code,
                                        'name': parts[1],
                                        'price': float(parts[3]),
                                        'change_pct': float(parts[32]),
                                        'open': float(parts[5]),
                                        'high': float(parts[33]),
                                        'low': float(parts[34]),
                                        'volume': int(parts[36]) if parts[36].isdigit() else 0
                                    }
                            except Exception as e:
                                continue
            except Exception as e:
                print(f'批量获取行情失败: {e}')
        
        return results

class SimulatedPortfolio:
    """模拟盘管理"""
    
    def __init__(self):
        self.data = self.load_portfolio()
        
    def load_portfolio(self):
        if os.path.exists(PORTFOLIO_FILE):
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
                if 'pending_orders' not in data:
                    data['pending_orders'] = {'buy': [], 'sell': []}
                return data
        
        return {
            'cash': STRATEGY_CONFIG['initial_capital'],
            'positions': {},
            'pending_orders': {'buy': [], 'sell': []},
            'total_value': STRATEGY_CONFIG['initial_capital'],
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'trade_history': []
        }
    
    def save_portfolio(self):
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def record_trade(self, action, code, shares, price, reason):
        trade = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': action,
            'code': code,
            'shares': shares,
            'price': price,
            'amount': shares * price,
            'reason': reason
        }
        self.data['trade_history'].append(trade)

class StrategyEngine:
    """策略引擎 - 全市场选股"""
    
    def __init__(self):
        self.config = STRATEGY_CONFIG
        self.portfolio = SimulatedPortfolio()
        self.data_provider = DataProvider()
    
    def calculate_factors(self, df):
        """计算因子评分"""
        df = df[df['ret_20'].notna()]
        
        # v23因子权重
        df['score'] = (
            df['ret_20'].rank(pct=True) * 0.20 +
            df['ret_60'].rank(pct=True) * 0.15 +
            df['mom_accel'].rank(pct=True) * 0.15 +
            (1 - df['vol_20'].rank(pct=True)) * 0.15 +
            df['money_flow'].rank(pct=True) * 0.15 +
            df['price_pos_20'].rank(pct=True) * 0.20
        )
        
        return df
    
    def select_stocks(self, n=10):
        """全市场选股 - 5000+只股票"""
        print("📊 获取全市场股票代码...")
        all_codes = self.data_provider.get_all_stock_codes()
        print(f"   共 {len(all_codes)} 只股票")
        
        print("📊 获取历史因子数据...")
        factors_df = self.data_provider.get_stock_factors(all_codes)
        
        if factors_df.empty:
            print("❌ 获取因子数据失败")
            return []
        
        print(f"   获取到 {len(factors_df)} 只股票的因子数据")
        
        # 计算评分
        factors_df = self.calculate_factors(factors_df)
        
        # 获取Top N候选
        top_candidates = factors_df.nlargest(min(n * 3, len(factors_df)), 'score')
        top_codes = top_candidates['ts_code'].tolist()
        
        print(f"📊 获取Top {len(top_codes)} 只股票的实时价格...")
        realtime_quotes = self.data_provider.get_realtime_quotes_batch(top_codes)
        
        # 合并数据和实时价格
        result = []
        for _, row in top_candidates.iterrows():
            code = row['ts_code']
            if code in realtime_quotes:
                quote = realtime_quotes[code]
                result.append({
                    'ts_code': code,
                    'name': quote['name'],
                    'price': quote['price'],
                    'change_pct': quote['change_pct'],
                    'score': row['score'],
                    'ret_20': row['ret_20']
                })
        
        # 按评分排序
        result.sort(key=lambda x: x['score'], reverse=True)
        print(f"   最终候选: {len(result)} 只")
        
        return result[:n]
    
    def analyze_portfolio(self):
        """分析当前持仓"""
        portfolio = self.portfolio.data
        positions = portfolio['positions']
        
        if not positions:
            return {'can_sell': [], 'holdings': [], 'total_market_value': 0}
        
        codes = list(positions.keys())
        quotes = self.data_provider.get_realtime_quotes_batch(codes)
        
        can_sell = []
        holdings = []
        total_market_value = 0
        today = datetime.now().strftime('%Y-%m-%d')
        
        for code, pos in positions.items():
            if code in quotes:
                quote = quotes[code]
                current_price = quote['price']
                market_value = pos['shares'] * current_price
                total_market_value += market_value
                
                cost = pos['cost']
                pnl_pct = (current_price - cost) / cost
                
                holding = {
                    'code': code,
                    'name': quote['name'],
                    'shares': pos['shares'],
                    'cost': cost,
                    'price': current_price,
                    'market_value': market_value,
                    'pnl_pct': pnl_pct,
                    'buy_date': pos['buy_date']
                }
                holdings.append(holding)
                
                if pos['buy_date'] != today:
                    can_sell.append(holding)
        
        return {
            'can_sell': can_sell,
            'holdings': holdings,
            'total_market_value': total_market_value,
            'quotes': quotes
        }
    
    def generate_decision(self):
        """生成交易决策"""
        analysis = self.analyze_portfolio()
        portfolio = self.portfolio.data
        
        decisions = []
        actions = []
        
        cash = portfolio['cash']
        total_value = cash + analysis['total_market_value']
        
        # 1. 检查止损
        for holding in analysis['holdings']:
            if holding['pnl_pct'] < -self.config['stop_loss']:
                if holding in analysis['can_sell']:
                    decisions.append(f"🔴 **止损卖出** {holding['code']}: 亏损{holding['pnl_pct']*100:.1f}%")
                    actions.append({
                        'action': 'SELL',
                        'code': holding['code'],
                        'shares': holding['shares'],
                        'price': holding['price'],
                        'reason': f'止损: 亏损{holding["pnl_pct"]*100:.1f}%'
                    })
                else:
                    decisions.append(f"🟡 **待止损** {holding['code']}: T+1限制，明日卖出")
        
        # 2. 全市场选股
        print("\n🔍 全市场选股...")
        top_stocks = self.select_stocks(self.config['max_positions'] + 3)
        
        if top_stocks:
            print(f"\n📈 Top候选股票:")
            for i, s in enumerate(top_stocks[:5], 1):
                print(f"   {i}. {s['name']} ({s['ts_code']}): 评分{s['score']:.3f}, 价格{s['price']:.2f}")
        
        target_codes = [s['ts_code'] for s in top_stocks]
        current_codes = set(portfolio['positions'].keys())
        
        # 3. 调仓逻辑
        if len(portfolio['positions']) >= self.config['max_positions']:
            # 持仓已满，检查调仓
            sellable = [h for h in analysis['holdings'] if h['pnl_pct'] > -self.config['stop_loss']]
            
            if sellable and top_stocks:
                worst_holding = min(sellable, key=lambda x: x['pnl_pct'])
                best_stock = top_stocks[0]
                
                if worst_holding['code'] not in target_codes[:3] and best_stock['ts_code'] not in current_codes:
                    decisions.append(f"🟡 **建议调仓**: 卖出{worst_holding['code']}({worst_holding['pnl_pct']*100:+.1f}%)，买入{best_stock['name']}(评分{best_stock['score']:.3f})")
                    
                    if worst_holding in analysis['can_sell']:
                        actions.append({
                            'action': 'SELL',
                            'code': worst_holding['code'],
                            'shares': worst_holding['shares'],
                            'price': worst_holding['price'],
                            'reason': f'调仓卖出，换入{best_stock["name"]}'
                        })
                        
                        cash_from_sell = worst_holding['shares'] * worst_holding['price']
                        shares_to_buy = int(cash_from_sell / best_stock['price'] / 100) * 100
                        
                        if shares_to_buy >= 100:
                            actions.append({
                                'action': 'BUY',
                                'code': best_stock['ts_code'],
                                'shares': shares_to_buy,
                                'price': best_stock['price'],
                                'reason': f'调仓买入: 评分{best_stock["score"]:.3f}'
                            })
                    else:
                        decisions.append(f"   ⏳ T+1限制，明日执行调仓")
        
        # 4. 建仓
        elif len(portfolio['positions']) < self.config['max_positions'] and cash > 10000:
            for stock in top_stocks:
                code = stock['ts_code']
                if code not in current_codes:
                    target_cash = total_value * self.config['position_ratio'] / self.config['max_positions']
                    shares = int(min(target_cash, cash) / stock['price'] / 100) * 100
                    
                    if shares >= 100:
                        decisions.append(f"🟢 **建议建仓** {stock['name']}({code}): 买入{shares}股 @ {stock['price']:.2f} (评分{stock['score']:.3f})")
                        actions.append({
                            'action': 'BUY',
                            'code': code,
                            'shares': shares,
                            'price': stock['price'],
                            'reason': f'建仓: 评分{stock["score"]:.3f}, 20日收益{stock["ret_20"]*100:.1f}%'
                        })
                        break
        
        if not decisions:
            if not portfolio['positions']:
                decisions.append("⏸️ **观望**: 等待合适建仓时机")
            else:
                avg_pnl = sum(h['pnl_pct'] for h in analysis['holdings']) / len(analysis['holdings']) if analysis['holdings'] else 0
                decisions.append(f"⏸️ **持仓观望**: 当前{len(portfolio['positions'])}只持仓，平均收益{avg_pnl*100:+.1f}%")
        
        return {
            'decisions': decisions,
            'actions': actions,
            'analysis': analysis,
            'total_value': total_value,
            'cash': cash,
            'top_stocks': top_stocks[:5]
        }
    
    def execute_actions(self, actions):
        """执行交易"""
        executed = []
        portfolio = self.portfolio.data
        today = datetime.now().strftime('%Y-%m-%d')
        
        for action in actions:
            act_type = action['action']
            code = action['code']
            shares = action['shares']
            price = action['price']
            reason = action['reason']
            
            if act_type == 'SELL':
                if code in portfolio['positions']:
                    amount = shares * price
                    portfolio['cash'] += amount
                    del portfolio['positions'][code]
                    self.portfolio.record_trade('SELL', code, shares, price, reason)
                    executed.append(f"卖出 {code}: {shares}股 @ {price:.2f}")
            
            elif act_type == 'BUY':
                cost = shares * price
                if portfolio['cash'] >= cost:
                    portfolio['cash'] -= cost
                    portfolio['positions'][code] = {
                        'shares': shares,
                        'cost': price,
                        'buy_date': today
                    }
                    self.portfolio.record_trade('BUY', code, shares, price, reason)
                    executed.append(f"买入 {code}: {shares}股 @ {price:.2f}")
        
        self.portfolio.save_portfolio()
        return executed

def generate_report(engine, decision_result, executed_trades):
    """生成报告"""
    portfolio = engine.portfolio.data
    cash = portfolio['cash']
    analysis = decision_result['analysis']
    initial_value = STRATEGY_CONFIG['initial_capital']
    
    total_value = cash + analysis['total_market_value']
    total_return = (total_value - initial_value) / initial_value * 100
    
    holdings_detail = []
    for h in analysis.get('holdings', []):
        emoji = "🟢" if h['pnl_pct'] > 0 else "🔴"
        t1_status = "(T+1)" if h['buy_date'] == datetime.now().strftime('%Y-%m-%d') else ""
        holdings_detail.append(
            f"• {emoji} **{h['code']}** {h['name']}: {h['shares']}股 | "
            f"成本¥{h['cost']:.2f} | 现价¥{h['price']:.2f} | "
            f"盈亏{h['pnl_pct']*100:+.1f}% {t1_status}"
        )
    
    top_stocks_detail = []
    for i, s in enumerate(decision_result.get('top_stocks', []), 1):
        top_stocks_detail.append(
            f"{i}. {s['name']}({s['ts_code']}): 评分{s['score']:.3f}, "
            f"价格¥{s['price']:.2f}, 涨跌{s['change_pct']:+.2f}%"
        )
    
    actions_str = '\n'.join([f"• {t}" for t in executed_trades]) if executed_trades else '• 无操作'
    
    report = f"""📊 **模拟盘跟踪报告** {datetime.now().strftime('%Y-%m-%d %H:%M')}

**策略配置**: 仓位100% | 止损5% | 持仓3只 | 全市场5000+选股

**组合表现**:
• 初始资金: ¥{initial_value:,.0f}
• 当前总价值: ¥{total_value:,.0f} (现金¥{cash:,.0f} + 持仓¥{analysis['total_market_value']:,.0f})
• 总收益: {total_return:+.2f}%

**当前持仓** ({len(portfolio['positions'])}只):
{chr(10).join(holdings_detail) if holdings_detail else '• 空仓'}

**交易决策**:
{chr(10).join(decision_result['decisions'])}

**已执行操作**:
{actions_str}

**Top 5候选股票**:
{chr(10).join(top_stocks_detail) if top_stocks_detail else '• 无'}

---
💡 基于v23因子模型，全市场5000+股票实时选股
"""
    return report

def send_report(report):
    try:
        subprocess.run(
            ['openclaw', 'message', 'send', '--target', USER_ID, '--message', report],
            capture_output=True, text=True, timeout=30
        )
        print("✅ 报告已发送")
    except Exception as e:
        print(f"发送失败: {e}")

def main():
    print("="*60)
    print("📈 模拟盘跟踪系统 v3 - 全市场5000+股票")
    print("="*60)
    
    engine = StrategyEngine()
    
    print("\n🔍 全市场选股分析...")
    decision = engine.generate_decision()
    
    print("\n💼 执行交易...")
    executed = engine.execute_actions(decision['actions'])
    
    # 重新分析获取最新数据
    final_analysis = engine.analyze_portfolio()
    decision['analysis'] = final_analysis
    decision['total_value'] = engine.portfolio.data['cash'] + final_analysis['total_market_value']
    
    print("\n📝 生成报告...")
    report = generate_report(engine, decision, executed)
    print(report)
    
    send_report(report)
    print("\n✅ 完成")

if __name__ == "__main__":
    main()
