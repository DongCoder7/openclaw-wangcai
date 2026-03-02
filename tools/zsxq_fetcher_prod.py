#!/usr/bin/env python3
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

# 防封策略配置 - 保守策略
REQUEST_MIN_DELAY = 5.0   # 最小请求间隔(秒) - 保守设置
REQUEST_MAX_DELAY = 10.0  # 最大请求间隔(秒)
PASS_COOLDOWN = 30        # 轮次冷却(秒)
MAX_RETRIES = 3           # 最大重试次数
BACKOFF_BASE = 5          # 退避基数(秒)
CONTINUOUS_ERROR_THRESHOLD = 3  # 连续异常保护退出阈值

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
                        wait_time = 30 * (retry_count + 1)  # 30s, 60s, 90s
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
        """提取主题信息 (入库口径: 有标题或正文即入库)"""
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
        
        # 文件
        files = topic.get("files", [])
        if files and not content:
            file_names = [f.get("name", "") for f in files]
            title = file_names[0] if file_names else ""
            content = f"[文件] {', '.join(file_names)}"
        
        # 图片
        images = topic.get("images", [])
        if images and not content:
            content = f"[图片] {len(images)}张"
        
        # 入库口径: 有标题或正文即入库
        if not title and not content:
            return None
        
        return {
            "topic_id": topic_id,
            "date": date_str,
            "create_time": create_time,
            "author": author,
            "author_id": author_id,
            "channels": channels,
            "title": title[:200] if title else "",
            "content": content[:500] if content else "",  # 限制长度
            "type": topic.get("type", ""),
            "has_attachment": bool(files),
            "image_count": len(images)
        }
    
    def save_to_daily_file(self, topics: List[dict], date: str):
        """按日期落盘"""
        if not topics:
            return
        
        file_path = RAW_DIR / f"{date}.json"
        
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
        
        # 写入
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(all_topics, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 保存 {len(new_topics)} 条到 {file_path.name} (共 {len(all_topics)} 条)")
        self.stats["saved"] += len(new_topics)
    
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
    """主函数"""
    # 初始化
    try:
        fetcher = ZsxqFetcher(ZSXQ_COOKIE, GROUP_ID)
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        sys.exit(1)
    
    # 抓取
    try:
        fetcher.fetch_with_pagination()
    except KeyboardInterrupt:
        logger.info("⛔ 用户中断")
    except Exception as e:
        logger.error(f"抓取异常: {e}")
    
    # 输出报告
    report = fetcher.generate_daily_report()
    print("\n" + report)
    
    # 保存报告
    report_file = DATA_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"📄 报告已保存: {report_file}")


if __name__ == "__main__":
    main()
