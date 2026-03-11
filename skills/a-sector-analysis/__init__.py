#!/root/.openclaw/workspace/venv/bin/python3
"""
A股板块分析与轮动监控Skill
核心功能：
1. 板块五维景气度评分（政策/订单/业绩/估值/资金）
2. 板块轮动信号识别
3. 板块强弱排序与资金流向
4. 市场风格判断（成长vs价值）
"""
import sys
import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')

try:
    from longbridge_api import get_longbridge_api, LongbridgeAPI
    from zsxq_fetcher import search_industry_info
    LONGAPI_AVAILABLE = True
except ImportError:
    LONGAPI_AVAILABLE = False


@dataclass
class SectorScore:
    """板块五维评分"""
    sector: str  # 板块名称
    policy: int = 3  # 政策维度 1-5
    orders: int = 3  # 订单维度 1-5
    earnings: int = 3  # 业绩维度 1-5
    valuation: int = 3  # 估值维度 1-5
    fund_flow: int = 3  # 资金维度 1-5
    
    @property
    def total_score(self) -> int:
        """总分（加权）"""
        return int(
            self.policy * 0.30 +
            self.orders * 0.25 +
            self.earnings * 0.25 +
            self.valuation * 0.10 +
            self.fund_flow * 0.10
        )
    
    @property
    def rating(self) -> str:
        """评级"""
        score = self.total_score
        if score >= 4.5:
            return "🟢强烈推荐"
        elif score >= 4.0:
            return "🟢推荐"
        elif score >= 3.0:
            return "🟡中性"
        elif score >= 2.0:
            return "🟠偏空"
        else:
            return "🔴回避"
    
    def to_dict(self) -> Dict:
        return {
            'sector': self.sector,
            'policy': self.policy,
            'orders': self.orders,
            'earnings': self.earnings,
            'valuation': self.valuation,
            'fund_flow': self.fund_flow,
            'total_score': self.total_score,
            'rating': self.rating
        }


class SectorRotationAnalyzer:
    """板块轮动分析器"""
    
    # 板块分级定义
    SECTOR_TIERS = {
        'T0': {  # 核心持仓
            'AI算力': {'weight': (15, 20), 'stocks': ['300308.SZ', '300394.SZ']},
            '算力租赁': {'weight': (8, 10), 'stocks': ['300442.SZ', '300738.SZ']},
            '半导体设备': {'weight': (10, 12), 'stocks': ['002371.SZ', '688012.SH']},
            '储能': {'weight': (8, 10), 'stocks': ['300274.SZ', '300750.SZ']},
            '高股息红利': {'weight': (20, 25), 'stocks': ['600900.SH', '601088.SH']},
        },
        'T1': {  # 进攻持仓
            '人形机器人': {'weight': (5, 8), 'stocks': ['688017.SH', '002050.SZ']},
            '自动驾驶': {'weight': (4, 6), 'stocks': ['002920.SZ', '603596.SH']},
            '低空经济': {'weight': (3, 5), 'stocks': ['002085.SZ', '300411.SZ']},
            '卫星互联网': {'weight': (3, 5), 'stocks': ['600118.SH', '002465.SZ']},
            '创新药': {'weight': (5, 8), 'stocks': ['688235.SH', '1801.HK']},
        },
        'T2': {  # 卫星持仓
            '氢能源': {'weight': (2, 3), 'stocks': []},
            '商业航天': {'weight': (2, 3), 'stocks': []},
            '脑机接口': {'weight': (1, 2), 'stocks': []},
        },
        'T3': {  # 周期/防御
            '白酒': {'weight': (0, 5), 'stocks': ['000858.SZ', '600519.SH']},
            '光伏': {'weight': (0, 5), 'stocks': ['601012.SH', '688599.SH']},
            '锂电材料': {'weight': (0, 5), 'stocks': ['002709.SZ', '300014.SZ']},
        }
    }
    
    def __init__(self):
        self.longbridge = None
        if LONGAPI_AVAILABLE:
            try:
                self._init_environment()
                self.longbridge = get_longbridge_api()
            except Exception as e:
                print(f"⚠️ 长桥API初始化失败: {e}")
    
    def _init_environment(self):
        """初始化环境变量"""
        env_file = '/root/.openclaw/workspace/.longbridge.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"').strip("'")
    
    def analyze_sector(self, sector_name: str) -> Dict:
        """
        分析单个板块
        
        Args:
            sector_name: 板块名称
            
        Returns:
            板块分析报告
        """
        print(f"\n🔍 分析板块: {sector_name}")
        
        # 1. 获取板块分级信息
        tier_info = self._get_tier_info(sector_name)
        
        # 2. 计算五维评分
        score = self._calculate_sector_score(sector_name)
        
        # 3. 获取成分股行情
        quotes = self._get_sector_quotes(sector_name)
        
        # 4. 判断轮动信号
        rotation_signal = self._detect_rotation_signal(score)
        
        # 5. 生成操作建议
        recommendation = self._generate_recommendation(score, rotation_signal)
        
        return {
            'sector': sector_name,
            'tier': tier_info.get('tier', '未知'),
            'weight_range': tier_info.get('weight', (0, 0)),
            'score': score.to_dict(),
            'quotes': quotes,
            'rotation_signal': rotation_signal,
            'recommendation': recommendation,
            'timestamp': datetime.now().isoformat()
        }
    
    def compare_sectors(self, sector_names: List[str]) -> Dict:
        """
        多板块对比分析
        
        Args:
            sector_names: 板块名称列表
            
        Returns:
            对比分析报告
        """
        print(f"\n📊 对比分析 {len(sector_names)} 个板块")
        
        results = []
        for name in sector_names:
            result = self.analyze_sector(name)
            results.append(result)
        
        # 按评分排序
        results.sort(key=lambda x: x['score']['total_score'], reverse=True)
        
        return {
            'sectors': results,
            'top_pick': results[0] if results else None,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_rotation_signals(self) -> List[Dict]:
        """
        获取全市场轮动信号
        
        Returns:
            轮动信号列表（买入/卖出）
        """
        signals = []
        
        # 获取所有板块
        all_sectors = []
        for tier, sectors in self.SECTOR_TIERS.items():
            all_sectors.extend(sectors.keys())
        
        for sector in all_sectors:
            score = self._calculate_sector_score(sector)
            signal = self._detect_rotation_signal(score)
            
            if signal['type'] != 'neutral':
                signals.append({
                    'sector': sector,
                    'signal': signal['type'],
                    'strength': signal['strength'],
                    'score': score.total_score,
                    'reason': signal['reason']
                })
        
        # 按信号强度排序
        signals.sort(key=lambda x: x['strength'], reverse=True)
        return signals
    
    def detect_market_style(self) -> Dict:
        """
        判断市场风格
        
        Returns:
            风格判断结果
        """
        # 分析成长vs价值板块表现
        growth_sectors = ['AI算力', '算力租赁', '半导体设备', '人形机器人', '创新药']
        value_sectors = ['高股息红利', '白酒', '银行', '保险']
        
        growth_score = sum(self._calculate_sector_score(s).total_score for s in growth_sectors) / len(growth_sectors)
        value_score = sum(self._calculate_sector_score(s).total_score for s in value_sectors) / len(value_sectors)
        
        if growth_score > value_score + 0.5:
            style = 'growth'
            style_desc = '成长风格占优'
            suggestion = '增配AI算力/T1进攻板块，减配高股息'
        elif value_score > growth_score + 0.5:
            style = 'value'
            style_desc = '价值风格占优'
            suggestion = '增配高股息/防御板块，减配T1进攻'
        else:
            style = 'balanced'
            style_desc = '风格均衡'
            suggestion = '均衡配置，关注结构性机会'
        
        return {
            'style': style,
            'description': style_desc,
            'growth_score': round(growth_score, 2),
            'value_score': round(value_score, 2),
            'suggestion': suggestion,
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_portfolio_config(self, risk_level: str = 'medium') -> Dict:
        """
        生成板块配置方案
        
        Args:
            risk_level: 风险等级 (low/medium/high)
            
        Returns:
            配置方案
        """
        base_config = {
            'low': {'T0': 70, 'T1': 15, 'T2': 5, 'T3': 10},
            'medium': {'T0': 65, 'T1': 20, 'T2': 10, 'T3': 5},
            'high': {'T0': 55, 'T1': 30, 'T2': 15, 'T3': 0}
        }
        
        config = base_config.get(risk_level, base_config['medium'])
        
        # 根据当前轮动信号调整
        signals = self.get_rotation_signals()
        
        # 生成各板块具体权重
        sector_weights = []
        for tier_name, tier_sectors in self.SECTOR_TIERS.items():
            tier_weight = config.get(tier_name, 0)
            if tier_weight == 0 or not tier_sectors:
                continue
                
            per_sector_weight = tier_weight / len(tier_sectors)
            
            for sector_name, info in tier_sectors.items():
                sector_weight = per_sector_weight
                
                # 根据轮动信号调整
                for signal in signals:
                    if signal['sector'] == sector_name:
                        if signal['signal'] == 'buy':
                            sector_weight *= 1.2
                        elif signal['signal'] == 'sell':
                            sector_weight *= 0.5
                
                sector_weights.append({
                    'sector': sector_name,
                    'tier': tier_name,
                    'weight': round(sector_weight, 1),
                    'stocks': info.get('stocks', [])
                })
        
        # 归一化权重
        total = sum(s['weight'] for s in sector_weights)
        for s in sector_weights:
            s['weight'] = round(s['weight'] / total * 100, 1)
        
        return {
            'risk_level': risk_level,
            'tier_allocation': config,
            'sector_weights': sorted(sector_weights, key=lambda x: x['weight'], reverse=True),
            'signals_considered': len([s for s in signals if s['signal'] in ['buy', 'sell']]),
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_tier_info(self, sector_name: str) -> Dict:
        """获取板块分级信息"""
        for tier, sectors in self.SECTOR_TIERS.items():
            if sector_name in sectors:
                return {
                    'tier': tier,
                    'weight': sectors[sector_name]['weight'],
                    'stocks': sectors[sector_name]['stocks']
                }
        return {'tier': '未知', 'weight': (0, 0), 'stocks': []}
    
    def _calculate_sector_score(self, sector_name: str) -> SectorScore:
        """计算板块五维评分（简化版，实际应从数据库/研报获取）"""
        # 这里使用预设评分，实际应从知识星球/研报/财务数据计算
        preset_scores = {
            'AI算力': {'policy': 5, 'orders': 5, 'earnings': 4, 'valuation': 3, 'fund_flow': 4},
            '算力租赁': {'policy': 5, 'orders': 4, 'earnings': 3, 'valuation': 2, 'fund_flow': 4},
            '半导体设备': {'policy': 5, 'orders': 4, 'earnings': 4, 'valuation': 3, 'fund_flow': 4},
            '储能': {'policy': 4, 'orders': 3, 'earnings': 3, 'valuation': 4, 'fund_flow': 3},
            '高股息红利': {'policy': 3, 'orders': 3, 'earnings': 4, 'valuation': 5, 'fund_flow': 3},
            '人形机器人': {'policy': 5, 'orders': 3, 'earnings': 2, 'valuation': 2, 'fund_flow': 4},
            '自动驾驶': {'policy': 4, 'orders': 3, 'earnings': 2, 'valuation': 3, 'fund_flow': 3},
            '创新药': {'policy': 4, 'orders': 4, 'earnings': 3, 'valuation': 3, 'fund_flow': 3},
        }
        
        preset = preset_scores.get(sector_name, {})
        return SectorScore(
            sector=sector_name,
            policy=preset.get('policy', 3),
            orders=preset.get('orders', 3),
            earnings=preset.get('earnings', 3),
            valuation=preset.get('valuation', 3),
            fund_flow=preset.get('fund_flow', 3)
        )
    
    def _get_sector_quotes(self, sector_name: str) -> List[Dict]:
        """获取板块成分股行情"""
        tier_info = self._get_tier_info(sector_name)
        stocks = tier_info.get('stocks', [])
        
        if not stocks or not self.longbridge:
            return []
        
        try:
            quotes = self.longbridge.get_quotes(stocks)
            # 按涨跌幅排序
            quotes.sort(key=lambda x: x.get('change', 0), reverse=True)
            return quotes[:5]  # 返回前5
        except Exception as e:
            print(f"⚠️ 获取行情失败: {e}")
            return []
    
    def _detect_rotation_signal(self, score: SectorScore) -> Dict:
        """检测轮动信号"""
        positive_dims = sum([
            score.policy >= 4,
            score.orders >= 4,
            score.earnings >= 4,
            score.valuation >= 4,
            score.fund_flow >= 4
        ])
        
        negative_dims = sum([
            score.policy <= 2,
            score.orders <= 2,
            score.earnings <= 2,
            score.valuation <= 2,
            score.fund_flow <= 2
        ])
        
        if positive_dims >= 4:
            return {
                'type': 'buy',
                'strength': score.total_score,
                'reason': f'{positive_dims}个维度向好，五维共振'
            }
        elif negative_dims >= 2:
            return {
                'type': 'sell',
                'strength': 5 - score.total_score,
                'reason': f'{negative_dims}个维度恶化，风险警示'
            }
        else:
            return {
                'type': 'neutral',
                'strength': 0,
                'reason': '信号中性'
            }
    
    def _generate_recommendation(self, score: SectorScore, signal: Dict) -> str:
        """生成操作建议"""
        if signal['type'] == 'buy':
            return f"加仓至目标仓位，{score.rating}"
        elif signal['type'] == 'sell':
            return f"减仓避险，{score.rating}"
        else:
            return f"维持配置，{score.rating}"
    
    def format_report(self, result: Dict) -> str:
        """格式化报告"""
        lines = [
            "="*80,
            f"📊 {result['sector']} 板块分析报告",
            "="*80,
            "",
            f"分析时间: {result['timestamp'][:19]}",
            f"板块分级: {result['tier']}",
            f"建议仓位: {result['weight_range'][0]}-{result['weight_range'][1]}%",
            "",
            "【五维景气度评分】",
        ]
        
        score = result['score']
        lines.extend([
            f"  政策维度: {'⭐' * score['policy']}",
            f"  订单维度: {'⭐' * score['orders']}",
            f"  业绩维度: {'⭐' * score['earnings']}",
            f"  估值维度: {'⭐' * score['valuation']}",
            f"  资金维度: {'⭐' * score['fund_flow']}",
            f"  总分: {score['total_score']}/5 {score['rating']}",
        ])
        
        lines.extend([
            "",
            "【轮动信号】",
            f"  信号类型: {result['rotation_signal']['type']}",
            f"  信号强度: {result['rotation_signal']['strength']}",
            f"  原因: {result['rotation_signal']['reason']}",
            "",
            "【操作建议】",
            f"  {result['recommendation']}",
        ])
        
        if result['quotes']:
            lines.extend([
                "",
                "【成分股行情】",
            ])
            for q in result['quotes']:
                emoji = "🟢" if q.get('change', 0) > 0 else "🔴"
                lines.append(f"  {emoji} {q.get('symbol')}: {q.get('price', 0):.2f} ({q.get('change', 0):+.2f}%)")
        
        lines.extend(["", "="*80])
        return "\n".join(lines)


# 便捷函数
def analyze_sector(sector_name: str) -> Dict:
    """快速分析板块入口"""
    analyzer = SectorRotationAnalyzer()
    return analyzer.analyze_sector(sector_name)

def compare_sectors(sector_names: List[str]) -> Dict:
    """快速对比板块入口"""
    analyzer = SectorRotationAnalyzer()
    return analyzer.compare_sectors(sector_names)

def get_rotation_signals() -> List[Dict]:
    """快速获取轮动信号入口"""
    analyzer = SectorRotationAnalyzer()
    return analyzer.get_rotation_signals()

def detect_market_style() -> Dict:
    """快速判断市场风格入口"""
    analyzer = SectorRotationAnalyzer()
    return analyzer.detect_market_style()

def generate_portfolio(risk_level: str = 'medium') -> Dict:
    """快速生成配置方案入口"""
    analyzer = SectorRotationAnalyzer()
    return analyzer.generate_portfolio_config(risk_level)


if __name__ == "__main__":
    # 测试
    print("\n测试板块分析...")
    analyzer = SectorRotationAnalyzer()
    
    # 测试单个板块
    result = analyzer.analyze_sector("AI算力")
    print(analyzer.format_report(result))
    
    # 测试板块对比
    print("\n\n测试板块对比...")
    compare_result = analyzer.compare_sectors(['AI算力', '半导体设备', '储能'])
    print(f"最强板块: {compare_result['top_pick']['sector']}")
    
    # 测试轮动信号
    print("\n测试轮动信号...")
    signals = analyzer.get_rotation_signals()
    print(f"发现 {len(signals)} 个轮动信号")
    
    print("\n测试完成!")
