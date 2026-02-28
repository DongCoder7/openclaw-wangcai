#!/usr/bin/env python3
"""
订单与营收预测工具
自动抓取公告、互动易问答，并预测订单增速和营收
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import re
import time


class OrderRevenuePredictor:
    """订单与营收预测器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    # ==================== 巨潮资讯网公告抓取 ====================
    
    def fetch_cninfo_announcements(self, stock_code: str, 
                                    start_date: Optional[str] = None,
                                    end_date: Optional[str] = None) -> List[Dict]:
        """
        抓取巨潮资讯网公告
        
        Args:
            stock_code: 股票代码（如 300548.SZ）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            
        Returns:
            公告列表
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 去除后缀，获取纯数字代码
        code_pure = stock_code.split('.')[0]
        
        announcements = []
        
        try:
            # 巨潮资讯网公告查询API
            # 先搜索公司获取orgId
            search_url = "http://www.cninfo.com.cn/new/information/topSearch/query"
            search_headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest'
            }
            search_data = f'keyWord={code_pure}&maxNum=10'
            
            resp = self.session.post(search_url, data=search_data, 
                                     headers=search_headers, timeout=10)
            
            org_id = None
            if resp.status_code == 200:
                try:
                    result = resp.json()
                    if isinstance(result, dict) and result.get('data') and len(result['data']) > 0:
                        company = result['data'][0]
                        org_id = company.get('orgId')
                except:
                    pass
            
            if not org_id:
                # 使用默认orgId映射
                org_id_map = {
                    '300548': '9900027258',  # 长芯博创
                    '688048': 'gfbj0830841',  # 长光华芯
                    '603306': '9900006256',  # 华懋科技
                    '000969': '9900000003',  # 安泰科技
                }
                org_id = org_id_map.get(code_pure, '')
            
            if org_id:
                # 获取公告列表
                column = 'szse' if '.SZ' in stock_code else 'sse'
                plate = 'sz' if '.SZ' in stock_code else 'sh'
                
                ann_url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
                ann_headers = {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest'
                }
                
                ann_data = {
                    'pageNum': '1',
                    'pageSize': '30',
                    'tabName': 'fulltext',
                    'column': column,
                    'stock': code_pure,
                    'searchkey': '',
                    'secid': '',
                    'plate': plate,
                    'category': 'category_ndbg_szsh,category_bndbg_szsh,category_yjdbg_szsh,category_sjdbg_szsh,category_dqgg_szsh,category_gqbd_szsh,category_gqjl_szsh',
                    'trade': '',
                    'columnTitle': '历年公告',
                    'sortName': '',
                    'sortType': '',
                    'limit': '',
                    'showTitle': '',
                    'seDate': f'{start_date}~{end_date}'
                }
                
                if org_id:
                    ann_data['orgId'] = org_id
                
                ann_resp = self.session.post(ann_url, data=ann_data, 
                                             headers=ann_headers, timeout=15)
                
                if ann_resp.status_code == 200:
                    try:
                        ann_result = ann_resp.json()
                        if isinstance(ann_result, dict) and ann_result.get('data'):
                            data = ann_result['data']
                            if isinstance(data, dict) and data.get('announcements'):
                                for ann in data['announcements']:
                                    announcements.append({
                                        'title': ann.get('announcementTitle', ''),
                                        'time': ann.get('announcementTime', ''),
                                        'type': self._classify_announcement(ann.get('announcementTitle', '')),
                                        'url': f"http://static.cninfo.com.cn/{ann.get('adjunctUrl', '')}"
                                    })
                    except Exception as e:
                        print(f"⚠️ 解析公告数据失败: {e}")
                        
        except Exception as e:
            print(f"⚠️ 获取公告失败: {e}")
        
        return announcements
    
    def _classify_announcement(self, title: str) -> str:
        """分类公告类型"""
        if not title:
            return '其他'
        
        title = title.lower()
        
        if any(k in title for k in ['合同', '订单', '中标', '框架']):
            return '重大合同'
        elif any(k in title for k in ['预告', '快报', '业绩']):
            return '业绩预告'
        elif any(k in title for k in ['减持', '增持', '回购']):
            return '增减持'
        elif any(k in title for k in ['收购', '并购', '重组']):
            return '并购重组'
        elif any(k in title for k in ['定增', '发行', '融资']):
            return '再融资'
        elif any(k in title for k in ['产能', '扩产', '投资']):
            return '产能扩张'
        else:
            return '其他公告'
    
    # ==================== 互动易问答抓取 ====================
    
    def fetch_interactive_questions(self, stock_code: str, 
                                     limit: int = 20) -> List[Dict]:
        """
        抓取深交所互动易问答（仅深交所股票）
        
        Args:
            stock_code: 股票代码（如 300548.SZ）
            limit: 获取条数
            
        Returns:
            问答列表
        """
        # 仅支持深交所股票
        if not stock_code.endswith('.SZ'):
            print(f"⚠️ 互动易仅支持深交所股票，{stock_code} 不支持")
            return []
        
        code_pure = stock_code.split('.')[0]
        questions = []
        
        try:
            url = "http://irm.cninfo.com.cn/ircs/interaction/lastNewIrmInfo"
            params = {
                'condition.type': '1',
                'condition.stockcode': code_pure,
                'pageNo': '1',
                'pageSize': str(limit)
            }
            
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('data') and result['data'].get('rows'):
                    for row in result['data']['rows']:
                        questions.append({
                            'question': row.get('questionContent'),
                            'answer': row.get('answerContent'),
                            'question_time': row.get('questionTime'),
                            'answer_time': row.get('answerTime'),
                            'keywords': self._extract_keywords(row.get('questionContent', ''))
                        })
        except Exception as e:
            print(f"⚠️ 获取互动易失败: {e}")
        
        return questions
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        if not text:
            return []
        
        keywords = []
        key_patterns = {
            '订单': ['订单', '合同', '中标', '客户'],
            '产能': ['产能', '产量', '利用率', '扩产'],
            '产品': ['800g', '400g', '光模块', '芯片', '产品'],
            '客户': ['客户', '华为', '阿里', '腾讯', '字节'],
            '业绩': ['业绩', '营收', '利润', '增长'],
            '竞争': ['竞争', '份额', '行业', '对手']
        }
        
        text_lower = text.lower()
        for category, patterns in key_patterns.items():
            if any(p in text_lower for p in patterns):
                keywords.append(category)
        
        return keywords
    
    # ==================== 订单与营收预测 ====================
    
    def extract_order_info(self, announcements: List[Dict]) -> List[Dict]:
        """
        从公告中提取订单信息
        
        Args:
            announcements: 公告列表
            
        Returns:
            订单信息列表
        """
        orders = []
        
        for ann in announcements:
            if ann['type'] == '重大合同':
                # 尝试提取金额
                amount = self._extract_amount(ann['title'])
                if amount:
                    orders.append({
                        'title': ann['title'],
                        'time': ann['time'],
                        'amount': amount,
                        'amount_str': f"{amount/10000:.2f}亿元" if amount > 10000 else f"{amount:.0f}万元"
                    })
        
        return orders
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """从文本中提取金额（万元）"""
        if not text:
            return None
        
        # 匹配 "X亿元" 或 "X万元"
        patterns = [
            r'(\d+\.?\d*)\s*亿元',
            r'(\d+\.?\d*)\s*亿',
            r'(\d+\.?\d*)\s*万元',
            r'(\d+\.?\d*)\s*万'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                amount = float(match.group(1))
                if '亿' in text:
                    return amount * 10000  # 转为万元
                return amount
        
        return None
    
    def predict_revenue_growth(self, 
                                current_revenue: float,
                                orders: List[Dict],
                                historical_orders: List[Dict],
                                industry_growth: float = 0.2) -> Dict:
        """
        预测营收增速
        
        Args:
            current_revenue: 当前年度营收（亿元）
            orders: 新签订单列表
            historical_orders: 历史订单列表
            industry_growth: 行业增速（默认20%）
            
        Returns:
            预测结果
        """
        # 计算订单金额
        new_order_amount = sum([o['amount'] for o in orders]) / 10000  # 转为亿元
        
        # 订单增速（同比）
        if historical_orders:
            hist_amount = sum([o['amount'] for o in historical_orders]) / 10000
            order_growth = (new_order_amount - hist_amount) / hist_amount if hist_amount > 0 else 0
        else:
            order_growth = industry_growth
        
        # 三情景预测
        scenarios = {
            'conservative': {
                'order_growth': max(order_growth * 0.5, industry_growth * 0.5),
                'delivery_rate': 0.6,  # 订单交付率
                'price_change': 0.95   # 价格下降5%
            },
            'neutral': {
                'order_growth': order_growth,
                'delivery_rate': 0.75,
                'price_change': 1.0
            },
            'optimistic': {
                'order_growth': order_growth * 1.3,
                'delivery_rate': 0.9,
                'price_change': 1.05
            }
        }
        
        results = {}
        for scenario, params in scenarios.items():
            # 营收增速 = 订单增速 × 交付率 × 价格变化
            revenue_growth = (1 + params['order_growth']) * params['delivery_rate'] * params['price_change'] - 1
            predicted_revenue = current_revenue * (1 + revenue_growth)
            
            results[scenario] = {
                'order_growth': f"{params['order_growth']*100:.1f}%",
                'revenue_growth': f"{revenue_growth*100:.1f}%",
                'predicted_revenue': f"{predicted_revenue:.2f}亿元",
                'current_revenue': f"{current_revenue:.2f}亿元"
            }
        
        return {
            'new_orders': f"{new_order_amount:.2f}亿元",
            'scenarios': results
        }
    
    def predict_net_profit(self,
                          predicted_revenue: float,
                          gross_margin: float = 0.35,
                          expense_ratio: float = 0.25) -> Dict:
        """
        预测净利润
        
        Args:
            predicted_revenue: 预测营收（亿元）
            gross_margin: 毛利率（默认35%）
            expense_ratio: 费用率（默认25%）
            
        Returns:
            净利润预测
        """
        gross_profit = predicted_revenue * gross_margin
        expenses = predicted_revenue * expense_ratio
        operating_profit = gross_profit - expenses
        
        # 假设所得税率15%
        tax = operating_profit * 0.15
        net_profit = operating_profit - tax
        
        return {
            'revenue': f"{predicted_revenue:.2f}亿元",
            'gross_profit': f"{gross_profit:.2f}亿元",
            'gross_margin': f"{gross_margin*100:.1f}%",
            'expenses': f"{expenses:.2f}亿元",
            'expense_ratio': f"{expense_ratio*100:.1f}%",
            'operating_profit': f"{operating_profit:.2f}亿元",
            'net_profit': f"{net_profit:.2f}亿元",
            'net_margin': f"{net_profit/predicted_revenue*100:.1f}%"
        }
    
    # ==================== 综合分析 ====================
    
    def analyze_stock(self, stock_code: str, stock_name: str,
                      current_revenue: float) -> Dict:
        """
        综合分析股票订单、营收、净利润
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            current_revenue: 当前营收（亿元）
            
        Returns:
            完整分析结果
        """
        print(f"\n{'='*70}")
        print(f"📊 订单与营收预测分析: {stock_name} ({stock_code})")
        print(f"{'='*70}")
        
        # 1. 抓取公告
        print("\n🔍 抓取巨潮资讯网公告...")
        announcements = self.fetch_cninfo_announcements(stock_code)
        print(f"   ✅ 获取 {len(announcements)} 条公告")
        
        # 2. 抓取互动易
        print("\n🔍 抓取互动易问答...")
        questions = self.fetch_interactive_questions(stock_code)
        print(f"   ✅ 获取 {len(questions)} 条问答")
        
        # 3. 提取订单信息
        print("\n📋 提取订单信息...")
        orders = self.extract_order_info(announcements)
        print(f"   ✅ 识别 {len(orders)} 个订单")
        for o in orders[:5]:  # 只显示前5个
            print(f"      - {o['time'][:10]} {o['title'][:40]}... 金额: {o['amount_str']}")
        
        # 4. 预测营收增速
        print("\n📈 预测营收增速...")
        revenue_pred = self.predict_revenue_growth(
            current_revenue=current_revenue,
            orders=orders,
            historical_orders=[],  # 简化处理
            industry_growth=0.25  # 光模块行业25%
        )
        
        # 5. 预测净利润（中性情景）
        neutral_revenue = float(revenue_pred['scenarios']['neutral']['predicted_revenue'].replace('亿元', ''))
        profit_pred = self.predict_net_profit(neutral_revenue)
        
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'announcements': announcements,
            'questions': questions,
            'orders': orders,
            'revenue_prediction': revenue_pred,
            'profit_prediction': profit_pred
        }


# ==================== 快速测试 ====================

if __name__ == "__main__":
    predictor = OrderRevenuePredictor()
    
    # 测试长芯博创
    result = predictor.analyze_stock(
        stock_code="300548.SZ",
        stock_name="长芯博创",
        current_revenue=35.0  # 假设当前营收35亿
    )
    
    print("\n" + "="*70)
    print("📊 营收预测结果")
    print("="*70)
    for scenario, data in result['revenue_prediction']['scenarios'].items():
        print(f"\n{scenario.upper()}:")
        for k, v in data.items():
            print(f"  {k}: {v}")
    
    print("\n" + "="*70)
    print("📊 净利润预测（中性情景）")
    print("="*70)
    for k, v in result['profit_prediction'].items():
        print(f"  {k}: {v}")
    print("="*70)
