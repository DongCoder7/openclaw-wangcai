# 个股深度分析标准化流程 v3.0

## 信息源总览与优先级

| 信息源 | 适用数据 | 获取方式 | 优先级 | 备注 |
|:-------|:---------|:---------|:-------|:-----|
| **Tushare Pro** | 财务数据、日线行情、业绩预告、基本面 | Python API | ⭐⭐⭐⭐⭐ | 需要Token |
| **新浪财经API** | 实时行情、资金流向 | Web API | ⭐⭐⭐⭐⭐ | 免费，实时 |
| **长桥API** | 实时行情、美股港股 | API | ⭐⭐⭐⭐ | 需要Token配置 |
| **eFinance** | 实时行情、财务数据 | Python库 | ⭐⭐⭐⭐ | 同花顺数据 |
| **东方财富** | F10资料、研报、资金流向 | Web/APP | ⭐⭐⭐⭐ | 网页解析 |
| **腾讯财经** | 新闻、公告、快讯 | Web API | ⭐⭐⭐⭐ | 新闻源 |
| **知识星球** | 调研纪要、行业深度、券商交流 | 手动/登录 | ⭐⭐⭐⭐ | 需要订阅 |
| **券商研报** | 盈利预测、行业分析 | 慧博/萝卜/东财 | ⭐⭐⭐⭐⭐ | 投研终端 |
| **公司公告** | 订单、收购、业绩预告 | 巨潮资讯网 | ⭐⭐⭐⭐⭐ | 最权威 |

---

## 核心原则: 多源交叉验证

### 实时行情验证流程
```
┌─────────────────────────────────────────────┐
│  获取实时行情 (至少2个源验证)               │
├─────────────────────────────────────────────┤
│  1. Tushare Pro (daily接口)                 │
│  2. 新浪财经API (hq.sinajs.cn)              │
│  3. 长桥API (如配置)                        │
├─────────────────────────────────────────────┤
│  对比: 收盘价、涨跌幅、成交量                │
│  差异>1%时，以Tushare为准                   │
└─────────────────────────────────────────────┘
```

### 因子计算流程 (不用本地DB)
```
┌─────────────────────────────────────────────┐
│  从Tushare获取原始数据 -> 重新计算因子      │
├─────────────────────────────────────────────┤
│  1. pro.daily() 获取日线数据                │
│  2. 计算 ret_20 (20日收益率)                │
│  3. 计算 vol_20 (20日波动率)                │
│  4. 计算 price_pos (价格位置)               │
└─────────────────────────────────────────────┘
```

---

## 一、各环节信息源详解

### 1. 公司基本画像

**数据需求与信息源**:
| 字段 | 首选信息源 | 备选信息源 | 获取方式 |
|:-----|:-----------|:-----------|:---------|
| 股票代码 | Tushare | 用户输入 | `pro.stock_basic()` |
| 公司名称 | **Tushare** | 新浪财经 | `pro.stock_basic()` |
| 当前股价 | **Tushare** + 新浪财经交叉 | 长桥API | `pro.daily()` + `hq.sinajs.cn` |
| 市值 | 计算 | 东方财富 | `close × total_share` |
| 所属行业 | **Tushare** | 同花顺 | `pro.stock_basic()` |
| 主营业务 | **年报PDF** | 招股说明书 | 巨潮资讯网下载 |
| 控股股东 | Tushare: `stk_holdernumber` | 天眼查 | Python API |
| 上市日期 | **Tushare** | - | `pro.stock_basic()` |

**代码示例 - 多源股价获取**:
```python
import tushare as ts
import requests

def get_price_cross_verify(ts_code):
    """多源交叉验证股价"""
    results = {}
    
    # 1. Tushare Pro
    pro = ts.pro_api()
    df = pro.daily(ts_code=ts_code, limit=1)
    if not df.empty:
        results['tushare'] = {
            'close': df.iloc[0]['close'],
            'pct_chg': df.iloc[0]['pct_chg'],
            'vol': df.iloc[0]['vol']
        }
    
    # 2. 新浪财经
    code = ts_code.lower().replace('.sz', '').replace('.sh', '')
    prefix = 'sz' if ts_code.endswith('.SZ') else 'sh'
    url = f'https://hq.sinajs.cn/list={prefix}{code}'
    r = requests.get(url, headers={'Referer': 'https://finance.sina.com.cn'})
    data = r.text.split('"')[1].split(',')
    results['sina'] = {
        'name': data[0],
        'close': float(data[3]),
        'open': float(data[1]),
        'high': float(data[4]),
        'low': float(data[5]),
        'vol': int(data[8])
    }
    
    # 3. 对比验证
    if abs(results['tushare']['close'] - results['sina']['close']) < 0.01:
        print(f"✅ 价格验证通过: {results['tushare']['close']}")
    else:
        print(f"⚠️ 价格差异: Tushare={results['tushare']['close']}, Sina={results['sina']['close']}")
    
    return results
```

---

### 2. 业务结构分析

**信息源**:
| 数据 | 首选信息源 | 获取方式 | 字段 |
|:-----|:-----------|:---------|:-----|
| 收入结构 | **年报PDF** | 巨潮资讯网下载 | 分产品收入表 |
| 毛利率 | **Tushare**: `fina_indicator` | Python API | `grossprofit_margin` |
| 成本结构 | **年报PDF** | PDF解析 | 成本分析表 |
| 在建工程 | **Tushare**: `balancesheet` | Python API | `const_in_process` |

---

### 3. 产业链定位与竞争优势

**信息源**:
| 数据 | 首选信息源 | 获取方式 |
|:-----|:-----------|:---------|
| 产业链描述 | **招股说明书** | 巨潮资讯网PDF |
| 竞争格局 | **券商研报** | 慧博投研/萝卜投研 |
| 技术壁垒 | **公司公告** + 知识星球 | 调研纪要 |
| 行业规模 | **行业协会** + 券商研报 | 研报数据 |

**券商研报获取渠道**:
1. **慧博投研** (https://www.hibor.com.cn/) - 专业投研平台
2. **萝卜投研** (https://robo.datayes.com/) - 免费研报
3. **东方财富研报中心** (https://data.eastmoney.com/report/) - 免费
4. **知识星球** - 一手调研纪要

---

### 4. 订单与产能分析

**信息源** (多源获取):
| 数据 | 首选源 | 备选源 | 获取方式 |
|:-----|:-------|:-------|:---------|
| 重大合同 | **巨潮资讯网** | 新浪财经 | 公告下载 |
| 在手订单 | **调研纪要** (知识星球) | 券商研报 | 订阅获取 |
| 产能利用率 | **年报** | 调研纪要 | PDF/知识星球 |
| 扩产计划 | **公告**: 定增/可转债 | 新闻 | 巨潮资讯网 |

**公告获取多源尝试**:
```python
import requests
from bs4 import BeautifulSoup

def get_announcements_multi_source(ts_code):
    """多源获取公司公告"""
    anns = []
    
    # 1. 巨潮资讯网 (最权威)
    try:
        url = f'http://www.cninfo.com.cn/new/information/topSearch/query?keyWord={ts_code}'
        # 获取公告列表
        anns.append({'source': 'cninfo', 'data': []})
    except:
        pass
    
    # 2. 新浪财经 (新闻聚合)
    try:
        url = f'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid={ts_code.replace(".SZ", "").replace(".SH", "")}'
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        anns.append({'source': 'sina', 'data': r.text[:500]})
    except:
        pass
    
    # 3. 东方财富 (公告中心)
    try:
        code = ts_code.replace('.SZ', '').replace('.SH', '')
        url = f'https://data.eastmoney.com/notices/detail/{code}.html'
        anns.append({'source': 'eastmoney', 'url': url})
    except:
        pass
    
    return anns
```

---

### 5. 财务深度分析

**信息源 - 全部从Tushare重新获取**:
| 指标 | 信息源 | 获取方式 | 字段 |
|:-----|:-------|:---------|:-----|
| 营业收入 | **Tushare**: `income` | Python API | `total_revenue` |
| 净利润 | **Tushare**: `income` | Python API | `n_income` |
| 毛利率 | **Tushare**: `fina_indicator` | Python API | `grossprofit_margin` |
| ROE | **Tushare**: `fina_indicator` | Python API | `roe` |
| 业绩预告 | **Tushare**: `forecast` | Python API | `type`, `p_change_min/max` |
| 业绩快报 | **Tushare**: `express` | Python API | `revenue`, `profit` |

**代码示例 - 完整财务数据链**:
```python
import tushare as ts

def get_full_financial_data(ts_code):
    """获取完整财务数据 (全从Tushare)"""
    pro = ts.pro_api()
    data = {}
    
    # 1. 利润表 - 营收/净利润/扣非
    df_income = pro.income(ts_code=ts_code, period='20240930')
    if not df_income.empty:
        data['revenue'] = df_income.iloc[0]['total_revenue'] / 1e8  # 亿
        data['net_profit'] = df_income.iloc[0]['n_income'] / 1e8
    
    # 2. 财务指标 - ROE/毛利率/净利率
    df_indicator = pro.fina_indicator(ts_code=ts_code, period='20240930')
    if not df_indicator.empty:
        data['roe'] = df_indicator.iloc[0]['roe']
        data['gross_margin'] = df_indicator.iloc[0]['grossprofit_margin']
        data['net_margin'] = df_indicator.iloc[0]['netprofit_margin']
    
    # 3. 业绩预告 - 全年预测
    df_forecast = pro.forecast(ts_code=ts_code)
    if not df_forecast.empty:
        data['forecast_type'] = df_forecast.iloc[0]['type']  # 预增/预减
        data['forecast_min'] = df_forecast.iloc[0]['p_change_min']  # 增速下限
        data['forecast_max'] = df_forecast.iloc[0]['p_change_max']  # 增速上限
    
    # 4. 每日指标 - PE/PB
    df_basic = pro.daily_basic(ts_code=ts_code)
    if not df_basic.empty:
        data['pe_ttm'] = df_basic.iloc[0]['pe_ttm']
        data['pb'] = df_basic.iloc[0]['pb']
    
    return data

# 使用示例
data = get_full_financial_data('300548.SZ')
print(f"营收: {data.get('revenue', 0):.2f}亿")
print(f"ROE: {data.get('roe', 0):.2f}%")
print(f"PE: {data.get('pe_ttm', 0):.2f}倍")
```

---

### 6. 行业景气度验证

**信息源**:
| 数据 | 首选源 | 获取方式 |
|:-----|:-------|:---------|
| 行业产量 | **行业协会** | 中国光通信行业网 |
| 龙头业绩 | **Tushare** 批量获取 | Python API |
| 价格走势 | **生意社** | 网页/APP |
| 订单排期 | **知识星球** + 券商研报 | 调研纪要 |

**批量获取龙头对比数据**:
```python
def get_industry_comparison(industry_codes):
    """获取同行业公司对比数据"""
    pro = ts.pro_api()
    results = []
    
    for code in industry_codes:
        # 获取财务数据
        df = pro.fina_indicator(ts_code=code, period='20240930')
        if not df.empty:
            results.append({
                'code': code,
                'roe': df.iloc[0]['roe'],
                'netprofit_yoy': df.iloc[0]['netprofit_yoy'],
                'grossprofit_margin': df.iloc[0]['grossprofit_margin']
            })
    
    return pd.DataFrame(results)

# 光模块行业对比
companies = ['300548.SZ', '300502.SZ', '300308.SZ', '300394.SZ']
df = get_industry_comparison(companies)
print(df)
```

---

### 7. 客户与供应商分析

**信息源**:
| 数据 | 首选源 | 获取方式 |
|:-----|:-------|:---------|
| 前五大客户 | **年报**: 销售集中度 | PDF解析 |
| 客户认证 | **公司公告** | 巨潮资讯网 |
| 供应商情况 | **调研纪要** (知识星球) | 订阅获取 |

---

### 8. 业绩预测与估值

**信息源**:
| 数据 | 首选源 | 获取方式 |
|:-----|:-------|:---------|
| 券商盈利预测 | **Wind/同花顺iFinD** | 专业终端 |
| 行业可比PE | **Tushare** 批量计算 | Python API |
| 当前PE/PB | **Tushare**: `daily_basic` | Python API |

---

### 9. 风险提示

基于前面各章节数据综合评估

---

### 10. 投资建议与跟踪指标

**跟踪指标数据源**:
| 指标 | 频率 | 数据源 | 获取方式 |
|:-----|:-----|:-------|:---------|
| 股价/市值 | 日度 | **Tushare** + 新浪财经 | API交叉验证 |
| 订单情况 | 季度 | **公告** + 知识星球 | 巨潮资讯网 |
| 行业数据 | 月度 | **券商研报** | 研报跟踪 |
| 龙头业绩 | 季度 | **Tushare** | Python API |

---

## 二、因子重新计算 (不用本地DB)

### 核心因子计算代码
```python
import tushare as ts
import pandas as pd
import numpy as np

def calculate_factors_from_tushare(ts_code, days=60):
    """
    从Tushare获取日线数据，重新计算因子
    不用本地数据库
    """
    pro = ts.pro_api()
    
    # 获取日线数据
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    
    if df.empty or len(df) < 20:
        return None
    
    df = df.sort_values('trade_date')
    
    # 计算因子
    df['ret_5'] = df['close'].pct_change(5)
    df['ret_20'] = df['close'].pct_change(20)
    df['ret_60'] = df['close'].pct_change(60)
    
    df['vol_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
    df['ma_20'] = df['close'].rolling(20).mean()
    df['ma_60'] = df['close'].rolling(60).mean()
    
    # 价格位置 (20日)
    df['price_pos_20'] = (df['close'] - df['low'].rolling(20).min()) / \
                         (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 0.001)
    
    # 量比
    df['vol_ratio'] = df['vol'] / df['vol'].rolling(20).mean()
    
    # 资金流向 (简化)
    df['money_flow'] = np.where(df['close'] > df['open'], df['vol'], -df['vol'])
    df['money_flow_20'] = df['money_flow'].rolling(20).sum()
    
    return df.iloc[-1]  # 返回最新数据

# 使用示例
factors = calculate_factors_from_tushare('300548.SZ')
print(f"ret_20: {factors['ret_20']:.4f}")
print(f"vol_20: {factors['vol_20']:.4f}")
print(f"price_pos: {factors['price_pos_20']:.4f}")
```

---

## 三、特殊场景数据源

### 场景1: 收购/转型标的

| 数据 | 首选源 | 获取方式 |
|:-----|:-------|:---------|
| 收购标的财务 | **重大资产重组报告书** | 巨潮资讯网PDF |
| 标的估值 | 资产评估报告 | 收购公告附件 |
| 审核进度 | **交易所审核公告** | 深交所/上交所 |
| 行业观点 | **知识星球** | 调研讨论 |

### 场景2: 产品多元化公司

| 数据 | 首选源 | 获取方式 |
|:-----|:-------|:---------|
| 产品拆分收入 | **年报PDF** | 巨潮资讯网 |
| 各产品毛利率 | 年报/知识星球 | PDF/调研纪要 |
| 行业数据 | **券商研报** | 慧博/萝卜 |

### 场景3: 订单驱动型公司

| 数据 | 首选源 | 获取方式 |
|:-----|:-------|:---------|
| 订单公告 | **巨潮资讯网** | 公告下载 |
| 客户产能 | 客户年报/新闻 | 客户公告 |
| 行业排期 | **知识星球** + 券商研报 | 调研纪要 |

---

## 四、数据获取完整代码模板

### 模板1: 完整个股分析数据获取
```python
import tushare as ts
import requests
import pandas as pd
from datetime import datetime, timedelta

class StockDataCollector:
    """个股数据收集器 - 多源获取"""
    
    def __init__(self, tushare_token):
        ts.set_token(tushare_token)
        self.pro = ts.pro_api()
    
    def get_price_cross_verify(self, ts_code):
        """多源交叉验证股价"""
        results = {'sources': []}
        
        # 1. Tushare
        try:
            df = self.pro.daily(ts_code=ts_code, limit=1)
            if not df.empty:
                results['tushare'] = {
                    'close': df.iloc[0]['close'],
                    'pct_chg': df.iloc[0]['pct_chg'],
                    'vol': df.iloc[0]['vol'],
                    'amount': df.iloc[0]['amount']
                }
                results['sources'].append('tushare')
        except Exception as e:
            print(f"Tushare错误: {e}")
        
        # 2. 新浪财经
        try:
            code = ts_code.lower().replace('.sz', '').replace('.sh', '')
            prefix = 'sz' if ts_code.endswith('.SZ') else 'sh'
            url = f'https://hq.sinajs.cn/list={prefix}{code}'
            r = requests.get(url, headers={'Referer': 'https://finance.sina.com.cn'}, timeout=10)
            data = r.text.split('"')[1].split(',')
            results['sina'] = {
                'name': data[0],
                'close': float(data[3]),
                'open': float(data[1]),
                'high': float(data[4]),
                'low': float(data[5]),
                'vol': int(data[8])
            }
            results['sources'].append('sina')
        except Exception as e:
            print(f"新浪财经错误: {e}")
        
        # 3. 交叉验证
        if 'tushare' in results and 'sina' in results:
            diff = abs(results['tushare']['close'] - results['sina']['close'])
            if diff < 0.01:
                results['verified'] = True
                results['final_price'] = results['tushare']['close']
            else:
                results['verified'] = False
                results['final_price'] = results['tushare']['close']  # 以Tushare为准
        
        return results
    
    def get_financial_data(self, ts_code):
        """获取完整财务数据"""
        data = {}
        
        # 利润表
        df_income = self.pro.income(ts_code=ts_code, period='20240930')
        if not df_income.empty:
            data['revenue'] = df_income.iloc[0]['total_revenue'] / 1e8
            data['net_profit'] = df_income.iloc[0]['n_income'] / 1e8
        
        # 财务指标
        df_fina = self.pro.fina_indicator(ts_code=ts_code, period='20240930')
        if not df_fina.empty:
            data['roe'] = df_fina.iloc[0]['roe']
            data['gross_margin'] = df_fina.iloc[0]['grossprofit_margin']
            data['net_margin'] = df_fina.iloc[0]['netprofit_margin']
        
        # 业绩预告
        df_forecast = self.pro.forecast(ts_code=ts_code)
        if not df_forecast.empty:
            data['forecast_type'] = df_forecast.iloc[0]['type']
            data['forecast_range'] = f"{df_forecast.iloc[0]['p_change_min']:.0f}% ~ {df_forecast.iloc[0]['p_change_max']:.0f}%"
        
        # 每日指标
        df_basic = self.pro.daily_basic(ts_code=ts_code)
        if not df_basic.empty:
            data['pe_ttm'] = df_basic.iloc[0]['pe_ttm']
            data['pb'] = df_basic.iloc[0]['pb']
            data['total_mv'] = df_basic.iloc[0]['total_mv'] / 1e8  # 亿
        
        return data
    
    def calculate_factors(self, ts_code):
        """从Tushare日线重新计算因子"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')
        
        df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        
        if df.empty or len(df) < 60:
            return None
        
        df = df.sort_values('trade_date')
        
        # 计算因子
        df['ret_20'] = df['close'].pct_change(20)
        df['ret_60'] = df['close'].pct_change(60)
        df['vol_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
        df['ma_20'] = df['close'].rolling(20).mean()
        df['price_pos_20'] = (df['close'] - df['low'].rolling(20).min()) / \
                             (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 0.001)
        
        latest = df.iloc[-1]
        return {
            'ret_20': latest['ret_20'],
            'ret_60': latest['ret_60'],
            'vol_20': latest['vol_20'],
            'price_pos_20': latest['price_pos_20'],
            'close': latest['close']
        }

# 使用示例
collector = StockDataCollector('your_token')

# 获取多源验证股价
price_data = collector.get_price_cross_verify('300548.SZ')
print(f"验证后股价: {price_data.get('final_price')}")

# 获取财务数据
fina_data = collector.get_financial_data('300548.SZ')
print(f"ROE: {fina_data.get('roe')}%")

# 重新计算因子
factors = collector.calculate_factors('300548.SZ')
print(f"ret_20: {factors.get('ret_20'):.4f}")
```

---

## 五、质量控制Checklist

**发布前检查**:
- [ ] 股价已多源验证 (Tushare + 新浪财经)
- [ ] 财务数据来自Tushare (非本地DB)
- [ ] 因子已重新计算 (从Tushare日线)
- [ ] 业绩预告已获取 (Tushare `forecast`)
- [ ] 公告已多源尝试 (巨潮/新浪/东财)
- [ ] 行业数据有研报支撑 (慧博/萝卜)
- [ ] 估值使用最新PE (Tushare `daily_basic`)
- [ ] 数据源已标注在文档末尾

---

## 六、信息源优先级总结

### 实时行情 (必须交叉验证)
1. **Tushare Pro** - 主要数据源
2. **新浪财经API** - 验证用
3. **长桥API** - 备选 (需配置)

### 财务数据 (全从Tushare)
- 利润表: `pro.income()`
- 财务指标: `pro.fina_indicator()`
- 业绩预告: `pro.forecast()`
- 每日指标: `pro.daily_basic()`

### 因子计算 (不用本地DB)
- 从 `pro.daily()` 获取日线
- 重新计算: ret_20, vol_20, price_pos

### 公司公告 (多源尝试)
1. **巨潮资讯网** - 最权威
2. **新浪财经** - 新闻聚合
3. **东方财富** - 公告中心
4. **Tushare** - 部分可用

### 券商研报
1. **知识星球** - 一手调研
2. **慧博投研** - 专业平台
3. **萝卜投研** - 免费研报
4. **东财研报中心** - 免费

---

*版本: v3.0*  
*更新: 2026-02-26 - 完善多源交叉验证，不用本地DB*  
*适用场景: A股个股深度分析*
