#!/root/.openclaw/workspace/venv/bin/python3
"""
知识星球增量抓取脚本 V2 - 带重试机制

更新:
- 添加 API 错误 1059 限流重试
- 最多重试 3 次，间隔递增

用法:
  ZSXQ_GROUP_ID=xxx ZSXQ_COOKIE=xxx ./venv_runner.sh tools/zsxq_fetcher_incremental_v2.py
"""

import requests
import time
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 配置
GROUP_ID = os.getenv("ZSXQ_GROUP_ID", "")
ZSXQ_COOKIE = os.getenv("ZSXQ_COOKIE", "")
BASE_URL = "https://api.zsxq.com/v2"

# 重试配置
MAX_RETRIES = 3
BASE_WAIT = 10  # 基础等待时间(秒)

# 数据目录
DATA_DIR = Path("/root/.openclaw/workspace/data/zsxq")
RAW_DIR = DATA_DIR / "raw"
SEEN_IDS_FILE = DATA_DIR / f"seen_ids_{GROUP_ID}.txt"


def init_dirs():
    """初始化目录"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_seen_ids() -> set:
    """加载已抓取的topic_id"""
    if SEEN_IDS_FILE.exists():
        with open(SEEN_IDS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_seen_id(topic_id: str):
    """保存已抓取的topic_id"""
    with open(SEEN_IDS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{topic_id}\n")


def fetch_latest_with_retry(group_id: str, cookie: str) -> tuple:
    """
    抓取最新一页（带重试机制）
    处理 API 错误 1059 (限流)
    """
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    url = f"{BASE_URL}/groups/{group_id}/topics?count=10"
    
    for retry_count in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("succeeded"):
                code = data.get("code", 0)
                
                # 处理限流错误 1059
                if code == 1059:
                    wait_time = BASE_WAIT * (retry_count + 1)  # 递增等待
                    if retry_count < MAX_RETRIES - 1:
                        print(f"⚠️ 触发限流(code=1059)，等待{wait_time}s后重试({retry_count+1}/{MAX_RETRIES})...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ API限流，已重试{MAX_RETRIES}次，放弃")
                        return [], 0
                else:
                    print(f"❌ API错误: code={code}")
                    return [], 0
            
            # 成功
            resp_data = data.get("resp_data", {})
            topics = resp_data.get("topics", [])
            return topics, len(topics)
            
        except requests.exceptions.RequestException as e:
            if retry_count < MAX_RETRIES - 1:
                wait_time = BASE_WAIT * (retry_count + 1)
                print(f"⚠️ 请求失败: {e}，等待{wait_time}s后重试({retry_count+1}/{MAX_RETRIES})...")
                time.sleep(wait_time)
            else:
                print(f"❌ 请求失败，已重试{MAX_RETRIES}次: {e}")
                return [], 0
        except Exception as e:
            print(f"❌ 异常: {e}")
            return [], 0
    
    return [], 0


def extract_topic(topic: dict) -> dict:
    """提取主题信息"""
    topic_id = str(topic.get("topic_id", ""))
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
    
    # 提取标题和正文
    title = talk.get("title", "") if talk else ""
    content = talk.get("text", "") if talk else ""
    
    # 问答
    question = topic.get("question", {})
    if question:
        title = question.get("title", "")
        content = question.get("text", "")
    
    # 文件
    files = topic.get("files", [])
    if files and not content:
        file_names = [f.get("name", "") for f in files]
        content = f"[文件] {', '.join(file_names)}"
    
    # 图片
    images = topic.get("images", [])
    if images and not content:
        content = f"[图片] {len(images)}张"
    
    if not title and not content:
        return None
    
    return {
        "topic_id": topic_id,
        "date": date_str,
        "create_time": create_time,
        "author": author,
        "title": title[:200] if title else "",
        "content": content[:2000] if content else "",
        "type": topic.get("type", ""),
        "has_attachment": bool(files),
        "image_count": len(images)
    }


def save_to_file(topics: list, group_id: str):
    """保存到按Group ID命名的文件"""
    if not topics:
        return 0
    
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = RAW_DIR / f"{today}_{group_id}.json"
    
    # 读取已有数据
    existing = []
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    
    # 合并（新数据在前）
    all_topics = topics + existing
    
    # 按topic_id去重
    seen = set()
    unique_topics = []
    for t in all_topics:
        tid = t.get("topic_id")
        if tid and tid not in seen:
            seen.add(tid)
            unique_topics.append(t)
    
    # 按时间排序
    unique_topics.sort(key=lambda x: x.get("create_time", ""), reverse=True)
    
    # 写入
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(unique_topics, f, ensure_ascii=False, indent=2)
    
    return len(topics)


def main():
    """主函数"""
    if not GROUP_ID or not ZSXQ_COOKIE:
        print("❌ 缺少环境变量 ZSXQ_GROUP_ID 或 ZSXQ_COOKIE")
        sys.exit(1)
    
    init_dirs()
    seen_ids = load_seen_ids()
    
    print(f"🚀 增量抓取 Group: {GROUP_ID}")
    print(f"   已有记录: {len(seen_ids)} 条")
    print(f"   重试配置: 最多{MAX_RETRIES}次，基础等待{BASE_WAIT}s")
    
    # 抓取最新一页（带重试）
    raw_topics, total = fetch_latest_with_retry(GROUP_ID, ZSXQ_COOKIE)
    
    if not raw_topics:
        print("❌ 未获取到数据")
        sys.exit(1)
    
    print(f"📄 API返回: {total} 条 (抓取最新10条)")
    
    # 过滤新内容
    new_topics = []
    for topic in raw_topics:
        topic_id = str(topic.get("topic_id", ""))
        if topic_id and topic_id not in seen_ids:
            extracted = extract_topic(topic)
            if extracted:
                new_topics.append(extracted)
                save_seen_id(topic_id)
    
    # 保存
    saved_count = save_to_file(new_topics, GROUP_ID)
    
    # 输出结果
    print(f"✅ 新内容: {len(new_topics)} 条")
    print(f"💾 已保存到: {datetime.now().strftime('%Y-%m-%d')}_{GROUP_ID}.json")
    
    # 统计
    stats = {
        "timestamp": datetime.now().isoformat(),
        "group_id": GROUP_ID,
        "fetched": total,
        "new": len(new_topics),
        "saved": saved_count
    }
    print(f"📊 统计: {json.dumps(stats, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
