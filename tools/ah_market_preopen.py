#!/root/.openclaw/workspace/venv/bin/python3
"""
A+H股开盘前瞻报告 - 长桥API版本
每日9:15前执行，生成开盘策略报告

环境变量:
    LONGBRIDGE_APP_KEY: 长桥App Key
    LONGBRIDGE_APP_SECRET: 长桥App Secret
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from longbridge_provider import LongbridgeDataProvider
from data_utils import StockDataProvider


# A股重点板块监控
A_STOCK_SECTORS = {
    '科技/半导体': ['688981', '688012', '603893', '300760'],  # 中芯国际、中微公司、瑞芯微、迈瑞医疗
    'AI算力': ['300308', '300502', '002230', '603019'],       # 中际旭创、新易盛、科大讯飞、中科曙光
    '金融': ['600036', '000001', '601318', '601166'],         # 招商银行、平安银行、中国平安、兴业银行
    '消费医药': ['600519', '000858', '600887', '603259'],     # 茅台、五粮液、伊利、药明康德
    '新能源/资源': ['300750', '601012', '601899', '600900'],  # 宁德时代、隆基绿能、紫金矿业、长江电力
}

# 港股重点板块监控
H_STOCK_SECTORS = {
    '科技': ['00700', '09988', '03690', '01810'],  # 腾讯、阿里、美团、小米
    '金融地产': ['02318', '03988', '01109', '00688'],  # 中国平安、中国银行、华润置地、中国海外发展
    '能源资源': ['00883', '00857', '01088', '00998'],  # 中海油、中石油、中国神华、中信银行
    '消费医药': ['02331', '06690', '09618', '09999'],  # 李宁、百济神州、京东健康、网易
}


class MarketDataCollector:
    """市场数据收集器"""
    
    def __init__(self):
        self.longbridge = None
        self.tencent = StockDataProvider()
        self._init_longbridge()
    
    def _init_longbridge(self):
        """初始化长桥API"""
        try:
            self.longbridge = LongbridgeDataProvider()
            test = self.longbridge.get_realtime_quote('00700', market='HK')
            if test:
                print('✅ 长桥API连接成功（支持港股）')
            else:
                print('⚠️ 长桥API测试失败')
        except Exception as e:
            print(f'⚠️ 长桥API初始化失败: {e}')
    
    def get_a_stock_quotes(self) -> Dict[str, Dict]:
        """获取A股板块行情"""
        print('\n📊 获取A股板块行情...')
        
        all_codes = []
        for sector, codes in A_STOCK_SECTORS.items():
            all_codes.extend(codes)
        
        # 去重
        all_codes = list(set(all_codes))
        
        results = {}
        
        # 优先使用长桥A股
        if self.longbridge:
            try:
                quotes = self.longbridge.get_realtime_quotes(all_codes, market='CN')
                for q in quotes:
                    results[q['code']] = {
                        'name': q['name'],
                        'price': q['price'],
                        'change_pct': q['change_pct'],
                        'sector': self._get_sector(q['code'], 'A')
                    }
                print(f'   ✅ 长桥A股: {len(results)}/{len(all_codes)}')
            except Exception as e:
                print(f'   ⚠️ 长桥A股失败: {e}')
        
        # 补缺失的
        missing = [c for c in all_codes if c not in results]
        if missing:
            print(f'   🔄 腾讯API补缺失: {len(missing)}只')
            for code in missing:
                try:
                    quote = self.tencent.get_realtime_quote(code)
                    if quote:
                        results[code] = {
                            'name': quote['name'],
                            'price': quote['price'],
                            'change_pct': quote['change_pct'],
                            'sector': self._get_sector(code, 'A')
                        }
                except:
                    pass
        
        return results
    
    def get_h_stock_quotes(self) -> Dict[str, Dict]:
        """获取港股板块行情"""
        print('\n📊 获取港股板块行情...')
        
        all_codes = []
        for sector, codes in H_STOCK_SECTORS.items():
            all_codes.extend(codes)
        
        all_codes = list(set(all_codes))
        results = {}
        
        # 使用长桥港股
        if self.longbridge:
            try:
                for code in all_codes:
                    quote = self.longbridge.get_realtime_quote(code, market='HK')
                    if quote:
                        results[code] = {
                            'name': quote['name'],
                            'price': quote['price'],
                            'change_pct': quote['change_pct'],
                            'sector': self._get_sector(code, 'HK')
                        }
                    import time
                    time.sleep(0.05)  # 限速
                
                print(f'   ✅ 长桥港股: {len(results)}/{len(all_codes)}')
            except Exception as e:
                print(f'   ⚠️ 长桥港股失败: {e}')
        
        return results
    
    def _get_sector(self, code: str, market: str) -> str:
        """获取股票所属板块"""
        sectors = A_STOCK_SECTORS if market == 'A' else H_STOCK_SECTORS
        for sector, codes in sectors.items():
            if code in codes:
                return sector
        return '其他'


def analyze_sectors(quotes: Dict[str, Dict], market: str) -> Dict:
    """分析板块强弱"""
    sectors = A_STOCK_SECTORS if market == 'A' else H_STOCK_SECTORS
    
    sector_stats = {}
    for sector_name in sectors.keys():
        sector_quotes = [q for q in quotes.values() if q.get('sector') == sector_name]
        if sector_quotes:
            avg_change = sum(q['change_pct'] for q in sector_quotes) / len(sector_quotes)
            up_count = sum(1 for q in sector_quotes if q['change_pct'] > 0)
            sector_stats[sector_name] = {
                'avg_change': avg_change,
                'up_count': up_count,
                'total': len(sector_quotes),
                'stocks': sector_quotes
            }
    
    # 按涨幅排序
    sorted_sectors = sorted(sector_stats.items(), key=lambda x: x[1]['avg_change'], reverse=True)
    return dict(sorted_sectors)


def generate_report(a_quotes: Dict, h_quotes: Dict) -> str:
    """生成开盘前瞻报告"""
    today = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M')
    
    report = f"""# A+H股开盘前瞻报告

**生成时间**: {today} {time_str}  
**数据来源**: 长桥API / 腾讯API

---

## 一、隔夜美股回顾

*(需手动补充美股收盘情况)*

---

## 二、A股开盘前瞻

### 板块强弱排序

"""
    
    # A股板块分析
    a_sectors = analyze_sectors(a_quotes, 'A')
    for i, (sector, stats) in enumerate(a_sectors.items(), 1):
        emoji = '🟢' if stats['avg_change'] > 0 else '🔴'
        report += f"{i}. {emoji} **{sector}**: 平均 {stats['avg_change']:+.2f}% ({stats['up_count']}/{stats['total']} 上涨)\n"
        for stock in stats['stocks'][:2]:  # 只显示前2只
            report += f"   - {stock['name']}: {stock['change_pct']:+.2f}%\n"
    
    report += "\n### 重点个股监控\n\n"
    
    # 涨幅榜
    top_gainers = sorted(a_quotes.values(), key=lambda x: x['change_pct'], reverse=True)[:5]
    report += "**涨幅前五**:\n"
    for i, stock in enumerate(top_gainers, 1):
        report += f"{i}. {stock['name']}: {stock['change_pct']:+.2f}%\n"
    
    report += "\n"
    
    # 跌幅榜
    top_losers = sorted(a_quotes.values(), key=lambda x: x['change_pct'])[:5]
    report += "**跌幅前五**:\n"
    for i, stock in enumerate(top_losers, 1):
        report += f"{i}. {stock['name']}: {stock['change_pct']:+.2f}%\n"
    
    report += """
---

## 三、港股开盘前瞻

### 板块强弱排序

"""
    
    # 港股板块分析
    h_sectors = analyze_sectors(h_quotes, 'HK')
    for i, (sector, stats) in enumerate(h_sectors.items(), 1):
        emoji = '🟢' if stats['avg_change'] > 0 else '🔴'
        report += f"{i}. {emoji} **{sector}**: 平均 {stats['avg_change']:+.2f}% ({stats['up_count']}/{stats['total']} 上涨)\n"
        for stock in stats['stocks'][:2]:
            report += f"   - {stock['name']}: {stock['change_pct']:+.2f}%\n"
    
    report += "\n### 重点个股监控\n\n"
    
    # 港股涨幅榜
    if h_quotes:
        h_gainers = sorted(h_quotes.values(), key=lambda x: x['change_pct'], reverse=True)[:5]
        report += "**涨幅前五**:\n"
        for i, stock in enumerate(h_gainers, 1):
            report += f"{i}. {stock['name']}: {stock['change_pct']:+.2f}%\n"
    
    report += """
---

## 四、开盘策略建议

### A股策略

| 情景 | 操作建议 |
|:-----|:---------|
| 高开 > 1% | 减仓观望，等待回踩 |
| 高开 0-1% | 持股观察，不追高 |
| 平开 | 关注板块轮动，择机调仓 |
| 低开 | 关注错杀机会，逢低吸纳 |

### 港股策略

| 情景 | 操作建议 |
|:-----|:---------|
| 科技股高开 | 腾讯/阿里减仓 |
| 科技股低开 | 关注抄底机会 |
| 高股息强势 | 增配中海油/神华 |

---

## 五、重点关注

1. **北向资金流向** - 开盘后30分钟观察
2. **成交量变化** - 对比昨日同期
3. **板块轮动** - 关注领涨板块持续性
4. **美股映射** - AI算力/新能源联动

---

*报告由VQM策略系统自动生成*
"""
    
    return report


def save_report(report: str):
    """保存报告到文件"""
    today = datetime.now().strftime('%Y-%m-%d')
    output_dir = os.path.expanduser('~/.openclaw/workshop/data')
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f'{output_dir}/market_preopen_{today}.md'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f'\n✅ 报告已保存: {filename}')
    return filename


def send_report_feishu(report: str):
    """发送报告到Feishu"""
    import subprocess
    USER_ID = 'ou_efbad805767f4572e8f93ebafa8d5402'
    try:
        result = subprocess.run(
            ['openclaw', 'message', 'send', '--target', USER_ID, '--message', report],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print('✅ 报告已发送到Feishu')
            return True
        else:
            print(f'❌ 发送失败: {result.stderr}')
            return False
    except Exception as e:
        print(f'❌ 发送异常: {e}')
        return False


def main():
    """主函数"""
    print('=' * 60)
    print('  A+H股开盘前瞻报告 - 长桥API版本')
    print('=' * 60)
    
    # 收集数据
    collector = MarketDataCollector()
    
    a_quotes = collector.get_a_stock_quotes()
    h_quotes = collector.get_h_stock_quotes()
    
    print(f'\n📈 数据汇总:')
    print(f'   A股: {len(a_quotes)} 只')
    print(f'   港股: {len(h_quotes)} 只')
    
    # 生成报告
    print('\n📝 生成报告中...')
    report = generate_report(a_quotes, h_quotes)
    
    # 保存
    filename = save_report(report)
    
    # 发送到Feishu
    print('\n📤 发送报告中...')
    send_report_feishu(report)
    
    # 同时打印报告
    print('\n' + '=' * 60)
    print(report)
    
    return filename


if __name__ == '__main__':
    main()
