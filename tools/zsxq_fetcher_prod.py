#!/root/.openclaw/workspace/venv/bin/python3
"""
知识星球生产级爬虫 - 线索池数据层 (简化版)
核心机制:
1. end_time逆序回溯 + checkpoint断点续跑
2. seen_ids全局去重
3. 按日期落盘 raw/YYYY-MM-DD.json
4. 防封策略: 低频随机、退避重试
5. 入库口径: 有标题或正文即入库

API: /v2 版本 (无需签名)
"""

import requests
import time
import json
import os
import sys
import random
import logging
import urllib.parse
import re  # 新增：用于文本分析
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# ============ 配置区域 ============

GROUP_ID = os.getenv("ZSXQ_GROUP_ID", "28855458518111")

# Cookie (从现有脚本导入)
ZSXQ_COOKIE = os.environ.get("ZSXQ_COOKIE") or os.environ.get("ZSXQ_COOKIES")

# 数据目录
DATA_DIR = Path(os.getenv("ZSXQ_DATA_DIR", "/root/.openclaw/workspace/data/zsxq"))
RAW_DIR = DATA_DIR / "raw"
CHECKPOINT_FILE = DATA_DIR / "checkpoint.json"
SEEN_IDS_FILE = DATA_DIR / "seen_ids.txt"

# API配置
BASE_URL = "https://api.zsxq.com/v2"

# 防封策略配置 - 超保守策略（降低限流风险）
REQUEST_MIN_DELAY = 8.0   # 最小请求间隔(秒) - 降低频率
REQUEST_MAX_DELAY = 15.0  # 最大请求间隔(秒)
PASS_COOLDOWN = 60        # 轮次冷却(秒) - 每轮后休息更久
MAX_RETRIES = 3           # 最大重试次数
BACKOFF_BASE = 10         # 退避基数(秒) - 增加退避时间
CONTINUOUS_ERROR_THRESHOLD = 3  # 连续异常保护退出阈值
RATE_LIMIT_WAIT = 60      # 限流后等待(秒)

# 分页配置
DEFAULT_PAGE_SIZE = 30  # API最大支持30条

# 回补窗口(天)
LOOKBACK_DAYS = int(os.getenv("ZSXQ_LOOKBACK_DAYS", "7"))

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(DATA_DIR / "fetcher.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class ZsxqFetcher:
    """知识星球生产级抓取器"""
    
    def __init__(self, cookie: str, group_id: str):
        if not cookie:
            raise ValueError("Cookie不能为空")
        
        self.cookie = cookie
        self.group_id = group_id
        self.base_url = BASE_URL
        
        # 统计
        self.stats = {
            "fetched": 0,
            "duplicated": 0,
            "saved": 0,
            "errors": 0,
            "retries": 0
        }
        
        # 连续异常计数
        self.continuous_errors = 0
        
        # 初始化目录
        self._init_dirs()
        
        # 加载已抓取ID
        self.seen_ids = self._load_seen_ids()
        
        # 请求头 (简化版)
        self.headers = {
            "Cookie": self.cookie,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
    
    def _init_dirs(self):
        """初始化目录结构"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        RAW_DIR.mkdir(exist_ok=True)
        logger.info(f"数据目录: {DATA_DIR}")
    
    def _load_seen_ids(self) -> set:
        """加载已抓取的topic_id"""
        if SEEN_IDS_FILE.exists():
            with open(SEEN_IDS_FILE, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    
    def _save_seen_id(self, topic_id: str):
        """保存已抓取的topic_id"""
        with open(SEEN_IDS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{topic_id}\n")
        self.seen_ids.add(topic_id)
    
    def _load_checkpoint(self) -> Dict:
        """加载断点"""
        if CHECKPOINT_FILE.exists():
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "last_end_time": None,
            "last_fetch_time": None,
            "fetched_count": 0
        }
    
    def _save_checkpoint(self, end_time: str = None, fetched: int = 0):
        """保存断点"""
        checkpoint = {
            "last_end_time": end_time,
            "last_fetch_time": datetime.now().isoformat(),
            "fetched_count": fetched,
            "group_id": self.group_id
        }
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    
    def _random_delay(self):
        """随机延迟，防封策略"""
        delay = random.uniform(REQUEST_MIN_DELAY, REQUEST_MAX_DELAY)
        time.sleep(delay)
    
    def _exponential_backoff(self, attempt: int):
        """指数退避"""
        delay = BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 1)
        logger.info(f"退避等待: {delay:.1f}s (尝试 {attempt+1}/{MAX_RETRIES})")
        time.sleep(delay)
    
    def send_request(self, path: str, params: dict = None, retry_count: int = 0) -> Optional[dict]:
        """发送请求，带退避重试"""
        url = f"{self.base_url}{path}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # 检查业务错误
            if not data.get("succeeded"):
                code = data.get("code", 0)
                logger.warning(f"API返回错误: code={code}, msg={data.get('resp_err', '未知')}")
                self.stats["errors"] += 1
                self.continuous_errors += 1
                return None
            
            # 成功，重置连续错误计数
            self.continuous_errors = 0
            return data
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求失败: {e}")
            self.stats["errors"] += 1
            self.continuous_errors += 1
            
            # 退避重试
            if retry_count < MAX_RETRIES:
                self._exponential_backoff(retry_count)
                self.stats["retries"] += 1
                return self.send_request(path, params, retry_count + 1)
            
            return None
    
    def get_topics(self, count: int = DEFAULT_PAGE_SIZE, end_time: str = None, retry_count: int = 0) -> Tuple[List[dict], Optional[str]]:
        """获取主题列表 - 使用URL编码的end_time分页，带限流处理"""
        # 使用 v2 API 直接 URL 构造
        url = f"{self.base_url}/groups/{self.group_id}/topics?count={count}"
        if end_time:
            # end_time 需要 URL 编码
            end_time_encoded = urllib.parse.quote(end_time)
            url += f"&end_time={end_time_encoded}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # 检查业务错误
            if not data.get("succeeded"):
                code = data.get("code", 0)
                error_msg = data.get('resp_err', '未知')
                
                # code 1059 是限流，需要等待后重试
                if code == 1059:
                    if retry_count < MAX_RETRIES:
                        wait_time = RATE_LIMIT_WAIT * (retry_count + 1)  # 60s, 120s, 180s
                        logger.warning(f"触发限流(code=1059)，等待{wait_time}s后重试({retry_count+1}/{MAX_RETRIES})...")
                        time.sleep(wait_time)
                        return self.get_topics(count, end_time, retry_count + 1)
                    else:
                        logger.error(f"限流重试次数耗尽，停止")
                        return [], None
                
                logger.warning(f"API返回错误: code={code}, msg={error_msg}")
                self.stats["errors"] += 1
                self.continuous_errors += 1
                return [], None
            
            # 成功，重置连续错误计数
            self.continuous_errors = 0
            
            resp_data = data.get("resp_data", {})
            topics = resp_data.get("topics", [])
            
            # 下一页的 end_time 是最后一条的 create_time
            next_end_time = None
            if topics:
                next_end_time = topics[-1].get("create_time")
            
            return topics, next_end_time
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求失败: {e}")
            self.stats["errors"] += 1
            self.continuous_errors += 1
            
            # 网络错误重试
            if retry_count < MAX_RETRIES:
                self._exponential_backoff(retry_count)
                return self.get_topics(count, end_time, retry_count + 1)
            
            return [], None
    
    def extract_topic(self, topic: dict) -> Optional[dict]:
        """提取主题信息 (入库口径: 有标题或正文即入库)
        
        修复v2.1: 完整提取所有相关字段
        - talk.files (帖子内的附件)
        - topic.files (顶层的附件)
        - quoted (引用的原帖)
        - comments (评论列表)
        - likes_count/readers_count (互动数据)
        """
        topic_id = topic.get("topic_id", "")
        
        # 去重检查
        if topic_id in self.seen_ids:
            self.stats["duplicated"] += 1
            return None
        
        create_time = topic.get("create_time", "")
        
        # 解析日期
        try:
            dt = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
            date_str = dt.strftime("%Y-%m-%d")
        except:
            date_str = "unknown"
        
        # 获取作者
        talk = topic.get("talk", {})
        owner = talk.get("owner", {}) if talk else {}
        author = owner.get("name", "") if owner else ""
        author_id = owner.get("user_id", "") if owner else ""
        
        # 获取频道/标签
        tags = topic.get("tags", [])
        channels = [t.get("name", "") for t in tags]
        
        # 提取标题和正文
        title = ""
        content = ""
        
        if talk:
            title = talk.get("title", "")
            content = talk.get("text", "")
        
        # 问答
        question = topic.get("question", {})
        if question:
            title = question.get("title", "")
            content = question.get("text", "")
        
        # ========== 文件提取 (修复bug: 检查多个位置) ==========
        all_files = []
        
        # 1. topic顶层files
        topic_files = topic.get("files", [])
        if topic_files:
            all_files.extend(topic_files)
        
        # 2. talk内部files (这是之前的bug位置!)
        talk_files = talk.get("files", []) if talk else []
        if talk_files:
            all_files.extend(talk_files)
        
        # 3. question内部files
        if question:
            question_files = question.get("files", [])
            if question_files:
                all_files.extend(question_files)
        
        # 去重(按file_id)
        seen_file_ids = set()
        unique_files = []
        for f in all_files:
            fid = f.get("file_id")
            if fid and fid not in seen_file_ids:
                seen_file_ids.add(fid)
                unique_files.append({
                    "file_id": f.get("file_id"),
                    "name": f.get("name", ""),
                    "size": f.get("size", 0),
                    "download_count": f.get("download_count", 0),
                    "create_time": f.get("create_time", "")
                })
        
        if unique_files and not content:
            file_names = [f.get("name", "") for f in unique_files]
            title = file_names[0] if file_names else ""
            content = f"[文件] {', '.join(file_names)}"
        
        # 图片 (同样检查多个位置)
        all_images = []
        topic_images = topic.get("images", [])
        if topic_images:
            all_images.extend(topic_images)
        talk_images = talk.get("images", []) if talk else []
        if talk_images:
            all_images.extend(talk_images)
        
        if all_images and not content:
            content = f"[图片] {len(all_images)}张"
        
        # 入库口径: 有标题或正文即入库
        if not title and not content:
            return None
        
        # ========== 提取引用内容 (quoted) ==========
        quoted_data = None
        quoted = topic.get("quoted")
        if quoted:
            quoted_talk = quoted.get("talk", {})
            quoted_question = quoted.get("question", {})
            
            quoted_author = ""
            quoted_content = ""
            quoted_files = []
            
            if quoted_talk:
                quoted_author = quoted_talk.get("owner", {}).get("name", "")
                quoted_content = quoted_talk.get("text", "")
                # 引用的文件
                qf = quoted_talk.get("files", [])
                if qf:
                    quoted_files = [{"name": f.get("name"), "file_id": f.get("file_id")} for f in qf]
            elif quoted_question:
                quoted_author = quoted_question.get("owner", {}).get("name", "")
                quoted_content = quoted_question.get("text", "")
            
            quoted_data = {
                "topic_id": quoted.get("topic_id"),
                "author": quoted_author,
                "content": quoted_content[:500] if quoted_content else "",
                "files": quoted_files,
                "create_time": quoted.get("create_time")
            }
        
        # ========== 提取评论 (comments) ==========
        comments_data = []
        comments = topic.get("comments", [])
        if comments:
            for c in comments:
                comment_talk = c.get("talk", {})
                comments_data.append({
                    "comment_id": c.get("comment_id"),
                    "author": comment_talk.get("owner", {}).get("name", ""),
                    "content": comment_talk.get("text", "")[:300],
                    "create_time": c.get("create_time"),
                    "likes_count": c.get("likes_count", 0)
                })
        
        # ========== 互动数据 ==========
        likes_count = topic.get("likes_count", 0)
        readers_count = topic.get("readers_count", 0)
        comments_count = topic.get("comments_count", 0) or len(comments_data)
        rewards_count = topic.get("rewards_count", 0)
        
        # 保存seen_id
        self._save_seen_id(topic_id)
        
        return {
            "topic_id": topic_id,
            "date": date_str,
            "create_time": create_time,
            "author": author,
            "author_id": author_id,
            "channels": channels,
            "title": title[:200] if title else "",
            "content": content[:1000] if content else "",  # 增加长度限制
            "type": topic.get("type", ""),
            "files": unique_files,  # 完整的文件列表
            "has_attachment": bool(unique_files),
            "images": [{"url": img.get("large", {}).get("url")} for img in all_images[:5]],  # 前5张图
            "image_count": len(all_images),
            "quoted": quoted_data,  # 引用的原帖
            "comments": comments_data,  # 评论列表
            "comments_count": comments_count,
            "likes_count": likes_count,
            "readers_count": readers_count,
            "rewards_count": rewards_count
        }
    
    def save_to_daily_file(self, topics: List[dict], date: str):
        """按日期落盘，同时按Group ID保存"""
        if not topics:
            return
        
        # 1. 按日期保存（原有逻辑）
        file_path = RAW_DIR / f"{date}.json"
        
        # 2. 按Group ID保存（新增，用于分Group发送）
        group_file_path = RAW_DIR / f"{date}_{self.group_id}.json"
        
        # 读取已有数据
        existing = []
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        
        # 合并并去重
        existing_ids = {t["topic_id"] for t in existing}
        new_topics = [t for t in topics if t["topic_id"] not in existing_ids]
        
        if not new_topics:
            return
        
        all_topics = existing + new_topics
        
        # 按时间排序
        all_topics.sort(key=lambda x: x.get("create_time", ""), reverse=True)
        
        # 写入日期文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(all_topics, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 保存 {len(new_topics)} 条到 {file_path.name} (共 {len(all_topics)} 条)")
        self.stats["saved"] += len(new_topics)
        
        # 3. 按Group ID保存（新增）
        group_existing = []
        if group_file_path.exists():
            with open(group_file_path, 'r', encoding='utf-8') as f:
                group_existing = json.load(f)
        
        # 合并并去重
        group_existing_ids = {t["topic_id"] for t in group_existing}
        group_new_topics = [t for t in topics if t["topic_id"] not in group_existing_ids]
        
        if group_new_topics:
            group_all_topics = group_existing + group_new_topics
            group_all_topics.sort(key=lambda x: x.get("create_time", ""), reverse=True)
            
            with open(group_file_path, 'w', encoding='utf-8') as f:
                json.dump(group_all_topics, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 保存 {len(group_new_topics)} 条到 {group_file_path.name} (共 {len(group_all_topics)} 条) [Group]")
    
    def fetch_with_pagination(self, target_date: str = None, max_pages: int = 100) -> Dict[str, List[dict]]:
        """分页抓取，支持断点续跑"""
        logger.info("=" * 60)
        logger.info(f"🚀 开始抓取星球: {self.group_id}")
        if target_date:
            logger.info(f"🎯 目标日期: {target_date}")
        logger.info("=" * 60)
        
        daily_topics: Dict[str, List[dict]] = {}
        page_count = 0
        stop_reason = "正常结束"
        
        # 第一页不使用end_time
        end_time = None
        seen_topic_ids = set()  # 本运行内去重
        
        while page_count < max_pages:
            # 连续异常保护退出
            if self.continuous_errors >= CONTINUOUS_ERROR_THRESHOLD:
                stop_reason = f"连续异常达到阈值({CONTINUOUS_ERROR_THRESHOLD})"
                logger.error(f"❌ {stop_reason}，保护退出")
                break
            
            page_count += 1
            logger.info(f"📄 第 {page_count} 页 (end_time={'有' if end_time else '无'})")
            
            # 获取数据
            topics, next_end_time = self.get_topics(count=DEFAULT_PAGE_SIZE, end_time=end_time)
            
            if not topics:
                stop_reason = "没有更多主题"
                logger.info(f"✅ {stop_reason}")
                break
            
            # 处理每个主题 - 添加本运行去重
            page_new_count = 0
            for topic in topics:
                topic_id = topic.get("topic_id", "")
                
                # 跳过本运行已处理的
                if topic_id in seen_topic_ids:
                    continue
                seen_topic_ids.add(topic_id)
                
                extracted = self.extract_topic(topic)
                if extracted:
                    date = extracted["date"]
                    
                    # 日期筛选
                    if target_date and date != target_date:
                        continue
                    
                    if date not in daily_topics:
                        daily_topics[date] = []
                    
                    daily_topics[date].append(extracted)
                    self._save_seen_id(extracted["topic_id"])
                    page_new_count += 1
                    self.stats["fetched"] += 1
            
            duplicate_count = len(topics) - page_new_count
            logger.info(f"  本页新数据: {page_new_count} 条, 去重: {duplicate_count} 条")
            
            # 如果整页都是重复的，停止
            if page_new_count == 0 and len(topics) > 0:
                stop_reason = "本页全部重复，停止"
                logger.info(f"⏹️ {stop_reason}")
                break
            
            # 按日期落盘
            for date, topics_list in list(daily_topics.items()):
                if topics_list:
                    self.save_to_daily_file(topics_list, date)
                    daily_topics[date] = []
            
            # 保存断点
            self._save_checkpoint(next_end_time, self.stats["fetched"])
            
            # 检查是否需要停止
            if not next_end_time:
                stop_reason = "无下一页"
                logger.info(f"✅ {stop_reason}")
                break
            
            # 检查日期边界
            if target_date:
                earliest_in_page = min(
                    (t.get("create_time", "") for t in topics if t.get("create_time")),
                    default=""
                )
                if earliest_in_page:
                    try:
                        dt = datetime.fromisoformat(earliest_in_page.replace('Z', '+00:00'))
                        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                        if dt.date() < target_dt.date():
                            stop_reason = "已到达目标日期之前"
                            logger.info(f"✅ {stop_reason}")
                            break
                    except:
                        pass
            
            # 更新游标 - 关键：使用next_end_time
            end_time = next_end_time
            
            # 随机延迟
            self._random_delay()
        
        if page_count >= max_pages:
            stop_reason = f"达到最大页数限制({max_pages})"
            logger.info(f"⏹️ {stop_reason}")
        
        # 轮次冷却
        logger.info(f"⏸️ 轮次冷却: {PASS_COOLDOWN}s")
        time.sleep(PASS_COOLDOWN)
        
        logger.info(f"🏁 抓取结束: {stop_reason}")
        return daily_topics
    
    def generate_summary_report(self, target_date: str = None) -> str:
        """生成结构化汇总报告（归纳总结版）"""
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        file_path = RAW_DIR / f"{target_date}.json"
        if not file_path.exists():
            return f"❌ 未找到 {target_date} 的数据文件"
        
        # 读取数据
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                topics = json.load(f)
        except Exception as e:
            return f"❌ 读取数据失败: {e}"
        
        if not topics:
            return f"📭 {target_date} 无数据"
        
        # 合并所有文本
        all_text = []
        for t in topics:
            text = f"{t.get('title', '')} {t.get('content', '')}"
            if text.strip():
                all_text.append(text)
        
        full_text = '\n'.join(all_text)
        
        # 行业关键词统计
        industry_keywords = {
            '人工智能/AI': ['人工智能', 'AI', '算力', '大模型', 'AIGC', 'ChatGPT'],
            '半导体/芯片': ['半导体', '芯片', '集成电路', '晶圆', '光刻'],
            '新能源': ['新能源', '光伏', '储能', '锂电池', '电动车', '风电'],
            '军工': ['军工', '国防', '航空航天', '导弹', '军舰', '低空经济'],
            '医药': ['医药', '医疗', '创新药', 'CXO', '医疗器械', '生物'],
            '金融': ['金融', '银行', '保险', '证券', '券商', '基金'],
            '消费': ['消费', '白酒', '食品饮料', '家电', '零售'],
            '通信': ['通信', '5G', '光模块', '光通讯', '基站', '运营商'],
            '计算机': ['计算机', '软件', 'IT', '云计算', '大数据'],
            '机器人': ['机器人', '人形机器人', '具身智能', '自动化'],
        }
        
        industry_stats = {}
        for industry, keywords in industry_keywords.items():
            count = 0
            for kw in keywords:
                count += len(re.findall(kw, full_text, re.IGNORECASE))
            if count > 0:
                industry_stats[industry] = count
        
        # 情绪统计
        bullish_words = ['买入', '增持', '看好', '推荐', '上行', '反弹', '上涨', '机会', '利好', '强势', '突破', '加仓']
        bearish_words = ['卖出', '减持', '看空', '回避', '下行', '调整', '下跌', '风险', '利空', '弱势', '回调', '减仓']
        
        bullish_count = sum(len(re.findall(w, full_text)) for w in bullish_words)
        bearish_count = sum(len(re.findall(w, full_text)) for w in bearish_words)
        total_sentiment = bullish_count + bearish_count
        
        # 政策/事件关键词
        policy_keywords = ['政府工作报告', '两会', '政策', '补贴', '规划', '十四五', '十五五']
        policy_count = sum(len(re.findall(kw, full_text)) for kw in policy_keywords)
        
        # 生成报告
        lines = []
        lines.append("=" * 60)
        lines.append(f"📊 知识星球日终汇总报告 ({target_date})")
        lines.append("=" * 60)
        
        lines.append(f"\n【一、数据概览】")
        lines.append(f"  • 抓取帖子数: {len(topics)} 条")
        lines.append(f"  • 总字数: {len(full_text):,} 字")
        lines.append(f"  • 平均单帖长度: {len(full_text)//len(topics):,} 字")
        
        lines.append(f"\n【二、热点行业分布】")
        sorted_industries = sorted(industry_stats.items(), key=lambda x: -x[1])
        for i, (industry, count) in enumerate(sorted_industries[:8], 1):
            bar = "█" * min(count // 3, 25)
            lines.append(f"  {i}. {industry:12s}: {count:3d}次 {bar}")
        
        if total_sentiment > 0:
            lines.append(f"\n【三、市场情绪统计】")
            bullish_pct = bullish_count * 100 // total_sentiment
            bearish_pct = bearish_count * 100 // total_sentiment
            lines.append(f"  • 🟢 看多情绪: {bullish_count}次 ({bullish_pct}%)")
            lines.append(f"  • 🔴 看空情绪: {bearish_count}次 ({bearish_pct}%)")
            sentiment_score = (bullish_count - bearish_count) / total_sentiment * 100
            sentiment_emoji = "📈" if sentiment_score > 20 else "📉" if sentiment_score < -20 else "➡️"
            lines.append(f"  • {sentiment_emoji} 情绪指数: {sentiment_score:+.1f} (正值看多)")
        
        lines.append(f"\n【四、政策/事件关注度】")
        lines.append(f"  • 政策相关提及: {policy_count}次")
        if policy_count > 10:
            lines.append(f"  • 🔥 今日政策热点密集")
        
        lines.append(f"\n【五、核心观点归纳】")
        
        # 基于高频行业生成观点
        top_industries = [k for k, v in sorted_industries[:3]]
        if '人工智能/AI' in top_industries:
            lines.append(f"  1️⃣ AI产业: 算力、大模型、应用持续高关注度")
        if '军工' in top_industries:
            lines.append(f"  2️⃣ 军工板块: 国防预算、航空航天、低空经济受关注")
        if '新能源' in top_industries:
            lines.append(f"  3️⃣ 新能源: 储能、光伏、电动车产业链")
        if policy_count > 10:
            lines.append(f"  4️⃣ 政策面: 政府工作报告/两会政策解读密集")
        
        if sentiment_score > 20:
            lines.append(f"  5️⃣ 市场情绪: 整体偏多，积极信号较多")
        elif sentiment_score < -20:
            lines.append(f"  5️⃣ 市场情绪: 整体偏空，谨慎情绪较浓")
        else:
            lines.append(f"  5️⃣ 市场情绪: 中性震荡，结构性机会为主")
        
        lines.append(f"\n【六、明日关注方向】")
        for i, industry in enumerate(top_industries[:3], 1):
            lines.append(f"  {i}. {industry}")
        
        lines.append(f"\n【七、数据质量】")
        lines.append(f"  • 抓取状态: {'✅ 完整' if len(topics) > 200 else '⚠️ 部分(可能限流)'}")
        lines.append(f"  • 文件路径: {file_path}")
        lines.append(f"  • 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)

    def generate_daily_report(self) -> str:
        """生成每日统计报告"""
        report_lines = ["📊 知识星球抓取统计", "=" * 40]
        
        # 读取所有日期文件
        daily_counts = {}
        for json_file in sorted(RAW_DIR.glob("*.json")):
            date = json_file.stem
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    daily_counts[date] = len(data)
            except:
                continue
        
        # 按日期排序
        for date in sorted(daily_counts.keys(), reverse=True)[:7]:
            count = daily_counts[date]
            bar = "█" * min(count // 2, 20)
            report_lines.append(f"{date}: {count:3d} 条 {bar}")
        
        total = sum(daily_counts.values())
        report_lines.append("-" * 40)
        report_lines.append(f"总计: {total} 条")
        report_lines.append("")
        report_lines.append(f"本次运行:")
        report_lines.append(f"  抓取: {self.stats['fetched']}")
        report_lines.append(f"  去重: {self.stats['duplicated']}")
        report_lines.append(f"  保存: {self.stats['saved']}")
        report_lines.append(f"  错误: {self.stats['errors']}")
        report_lines.append(f"  重试: {self.stats['retries']}")
        
        return "\n".join(report_lines)


def main():
    """主函数 - 抓取并生成汇总报告"""
    # 初始化
    try:
        fetcher = ZsxqFetcher(ZSXQ_COOKIE, GROUP_ID)
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        sys.exit(1)
    
    # 抓取
    target_date = datetime.now().strftime("%Y-%m-%d")
    try:
        fetcher.fetch_with_pagination()
    except KeyboardInterrupt:
        logger.info("⛔ 用户中断")
    except Exception as e:
        logger.error(f"抓取异常: {e}")
    
    # 输出简要统计
    report = fetcher.generate_daily_report()
    print("\n" + report)
    
    # 生成结构化汇总报告
    print("\n" + "="*60)
    print("📊 正在生成结构化汇总报告...")
    summary = fetcher.generate_summary_report(target_date)
    print(summary)
    
    # 保存汇总报告
    summary_file = DATA_DIR / f"summary_{target_date}.md"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary)
    logger.info(f"📄 汇总报告已保存: {summary_file}")
    
    # 同时保存简要报告
    report_file = DATA_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"📄 统计报告已保存: {report_file}")


if __name__ == "__main__":
    main()
