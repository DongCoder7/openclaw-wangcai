#!/usr/bin/env python3
"""
知识星球API爬虫 - 调研纪要频道最近一周信息抓取
参考: https://cloud.tencent.com/developer/article/2627228

功能:
1. 抓取指定星球最近一周的主题
2. 只抓取"调研纪要"频道的内容
3. 按天统计信息量
4. 输出JSON和Markdown报告
"""

import requests
import hashlib
import time
import json
import os
import sys
from urllib.parse import urlencode
from datetime import datetime, timedelta
from collections import defaultdict

# ============ 配置区域 ============

# 星球ID (从URL中获取，如 https://wx.zsxq.com/group/28855458518111)
GROUP_ID = "28855458518111"  # 请替换为你的星球ID

# 目标频道名称 (只抓取这个频道的内容)
TARGET_CHANNEL = "调研纪要"

# Cookie配置 - 必须手动从浏览器获取
# 获取方法:
# 1. 登录 https://wx.zsxq.com
# 2. F12打开开发者工具 -> Network
# 3. 刷新页面，找到 api.zsxq.com 的请求
# 4. 复制 Cookie 字段中的 zsxq_access_token
ZSXQ_COOKIE = os.getenv("ZSXQ_COOKIE", "")

# API基础配置
BASE_URL = "https://api.zsxq.com"
APP_VERSION = "3.11.0"
PLATFORM = "ios"
SECRET = "zsxqapi2020"  # 知识星球内置密钥

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "zsxq")


class ZsxqApiSpider:
    """知识星球API爬虫"""
    
    def __init__(self, cookie: str):
        if not cookie:
            raise ValueError("Cookie不能为空，请设置 ZSXQ_COOKIE 环境变量或直接修改脚本")
        
        self.cookie = cookie
        self.base_url = BASE_URL
        self.app_version = APP_VERSION
        self.platform = PLATFORM
        self.secret = SECRET
        
        # 基础请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Cookie": self.cookie,
            "Origin": "https://wx.zsxq.com",
            "Referer": "https://wx.zsxq.com/"
        }
    
    def generate_signature(self, path: str, params: dict = None) -> tuple:
        """
        生成知识星球API签名
        
        签名规则:
        1. 公共参数: app_version, platform, timestamp(毫秒)
        2. 合并业务参数，按键名升序排序
        3. 拼接: path&key1=value1&key2=value2&secret
        4. MD5加密，32位小写
        """
        # 1. 初始化公共参数
        common_params = {
            "app_version": self.app_version,
            "platform": self.platform,
            "timestamp": str(int(time.time() * 1000))  # 毫秒级时间戳
        }
        
        # 2. 合并并排序参数
        all_params = common_params.copy()
        if params and isinstance(params, dict):
            all_params.update(params)
        
        sorted_params = sorted(all_params.items(), key=lambda x: x[0])
        params_str = urlencode(sorted_params)
        
        # 3. 拼接待签名字符串
        sign_str = f"{path}&{params_str}&{self.secret}"
        
        # 4. MD5加密
        md5 = hashlib.md5()
        md5.update(sign_str.encode("utf-8"))
        signature = md5.hexdigest()
        
        return signature, common_params["timestamp"]
    
    def send_get_request(self, path: str, params: dict = None) -> dict:
        """发送GET请求"""
        signature, timestamp = self.generate_signature(path, params)
        
        # 更新请求头
        self.headers["X-Signature"] = signature
        self.headers["X-Timestamp"] = timestamp
        
        url = f"{self.base_url}{path}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ GET请求失败: {path}, 错误: {e}")
            return None
    
    def get_group_info(self, group_id: str) -> dict:
        """获取星球基本信息"""
        path = f"/v1/groups/{group_id}"
        response = self.send_get_request(path)
        
        if response and response.get("succeeded"):
            return response.get("resp_data", {}).get("group", {})
        else:
            error = response.get("resp_err", "未知错误") if response else "请求失败"
            print(f"❌ 获取星球信息失败: {error}")
            return {}
    
    def get_group_topics(self, group_id: str, count: int = 20, end_time: str = None, scope: str = None) -> tuple:
        """
        获取星球主题列表
        
        Args:
            group_id: 星球ID
            count: 每页数量
            end_time: 分页时间戳
            scope: 频道筛选 (all/combined/file/questions/essence)
        
        Returns:
            (主题列表, 下一页end_time)
        """
        path = f"/v1/groups/{group_id}/topics"
        params = {"count": count}
        
        if end_time:
            params["end_time"] = end_time
        if scope:
            params["scope"] = scope
        
        response = self.send_get_request(path, params)
        
        if response and response.get("succeeded"):
            data = response.get("resp_data", {})
            topics = data.get("topics", [])
            next_end_time = data.get("end_time")
            return topics, next_end_time
        else:
            error = response.get("resp_err", "未知错误") if response else "请求失败"
            print(f"❌ 获取主题列表失败: {error}")
            return [], None
    
    def get_topic_detail(self, topic_id: str) -> dict:
        """获取主题详情"""
        path = f"/v1/topics/{topic_id}"
        response = self.send_get_request(path)
        
        if response and response.get("succeeded"):
            return response.get("resp_data", {}).get("topic", {})
        else:
            return {}
    
    def get_channels(self, group_id: str) -> list:
        """获取星球频道列表"""
        path = f"/v1/groups/{group_id}/tags"
        response = self.send_get_request(path)
        
        if response and response.get("succeeded"):
            return response.get("resp_data", {}).get("tags", [])
        return []


def parse_topic_time(create_time: str) -> datetime:
    """解析主题创建时间"""
    # 格式: 2024-03-01T10:30:00.000+0800
    try:
        # 去掉时区信息，处理微秒
        dt_str = create_time[:19]  # 取前19个字符: 2024-03-01T10:30:00
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
    except:
        return None


def extract_topic_summary(topic: dict) -> dict:
    """提取主题摘要信息"""
    topic_id = topic.get("topic_id", "")
    create_time = topic.get("create_time", "")
    title = ""
    content = ""
    author = ""
    channel = ""
    
    # 解析时间
    dt = parse_topic_time(create_time)
    date_str = dt.strftime("%Y-%m-%d") if dt else ""
    
    # 获取作者
    author_info = topic.get("owner", {})
    author = author_info.get("name", "")
    
    # 获取频道/标签
    tags = topic.get("tags", [])
    if tags:
        channel = tags[0].get("name", "")
    
    # 获取内容
    talk = topic.get("talk", {})
    if talk:
        title = talk.get("title", "")
        content = talk.get("text", "")
    
    # 问答类型
    question = topic.get("question", {})
    if question:
        title = question.get("title", "")
        content = question.get("text", "")
    
    # 文件类型
    file_info = topic.get("files", [{}])[0]
    if file_info and not content:
        title = file_info.get("name", "")
        content = f"[文件] {file_info.get('name', '')}"
    
    return {
        "topic_id": topic_id,
        "date": date_str,
        "create_time": create_time,
        "author": author,
        "channel": channel,
        "title": title[:100] + "..." if len(title) > 100 else title,
        "content": content[:200] + "..." if len(content) > 200 else content,
        "type": topic.get("type", "")
    }


def fetch_recent_topics(spider: ZsxqApiSpider, group_id: str, target_channel: str = None, days: int = 7) -> list:
    """
    抓取最近N天的主题
    
    Args:
        spider: API爬虫实例
        group_id: 星球ID
        target_channel: 目标频道名称 (None表示全部)
        days: 抓取最近多少天
    
    Returns:
        主题列表
    """
    print(f"🚀 开始抓取最近 {days} 天的主题...")
    if target_channel:
        print(f"🎯 只抓取频道: {target_channel}")
    
    # 计算截止日期
    cutoff_date = datetime.now() - timedelta(days=days)
    print(f"📅 截止日期: {cutoff_date.strftime('%Y-%m-%d')}")
    
    all_topics = []
    end_time = None
    page = 1
    reached_cutoff = False
    
    while True:
        print(f"📄 正在抓取第 {page} 页...")
        topics, next_end_time = spider.get_group_topics(group_id, count=20, end_time=end_time)
        
        if not topics:
            print("✅ 没有更多主题")
            break
        
        for topic in topics:
            create_time = topic.get("create_time", "")
            dt = parse_topic_time(create_time)
            
            # 检查是否超过截止日期
            if dt and dt < cutoff_date:
                print(f"📅 已到达截止日期 ({dt.strftime('%Y-%m-%d')})")
                reached_cutoff = True
                break
            
            # 提取主题信息
            summary = extract_topic_summary(topic)
            
            # 频道筛选
            if target_channel:
                if summary["channel"] != target_channel:
                    continue
            
            all_topics.append(summary)
        
        if reached_cutoff:
            break
        
        if not next_end_time:
            break
        
        end_time = next_end_time
        page += 1        
        time.sleep(0.5)  # 避免请求过快
    
    print(f"✅ 共抓取 {len(all_topics)} 条主题")
    return all_topics


def generate_daily_stats(topics: list) -> dict:
    """生成每天的信息量统计"""
    stats = defaultdict(lambda: {"count": 0, "topics": []})
    
    for topic in topics:
        date = topic.get("date")
        if date:
            stats[date]["count"] += 1
            stats[date]["topics"].append(topic)
    
    # 按日期排序
    return dict(sorted(stats.items(), key=lambda x: x[0], reverse=True))


def save_json(data: dict, filename: str):
    """保存JSON文件"""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 JSON已保存: {filename}")


def generate_markdown_report(stats: dict, group_name: str, days: int, output_file: str):
    """生成Markdown报告"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# 📊 知识星球信息统计报告\n\n")
        f.write(f"**星球**: {group_name}\n\n")
        f.write(f"**统计周期**: 最近 {days} 天\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"---\n\n")
        
        # 总体统计
        total = sum(s["count"] for s in stats.values())
        f.write(f"## 📈 总体统计\n\n")
        f.write(f"- **总信息量**: {total} 条\n")
        f.write(f"- **统计天数**: {len(stats)} 天\n")
        f.write(f"- **日均信息量**: {total / len(stats) if stats else 0:.1f} 条\n\n")
        
        # 每天统计
        f.write(f"## 📅 每日信息量\n\n")
        f.write(f"| 日期 | 信息量 | 占比 |\n")
        f.write(f"|------|--------|------|\n")
        
        for date, data in stats.items():
            count = data["count"]
            percentage = (count / total * 100) if total > 0 else 0
            bar = "█" * int(percentage / 5)  # 每5%一个方块
            f.write(f"| {date} | {count} 条 | {bar} {percentage:.1f}% |\n")
        
        f.write(f"\n")
        
        # 详细列表
        f.write(f"## 📝 详细内容\n\n")
        
        for date, data in stats.items():
            f.write(f"### {date} ({data['count']} 条)\n\n")
            
            for i, topic in enumerate(data["topics"][:10], 1):  # 每天最多显示10条
                f.write(f"**{i}. {topic['title'] or '无标题'}**\n\n")
                f.write(f"- 作者: {topic['author']}\n")
                f.write(f"- 时间: {topic['create_time']}\n")
                if topic['channel']:
                    f.write(f"- 频道: {topic['channel']}\n")
                f.write(f"- 内容: {topic['content'][:150]}...\n\n")
            
            if len(data["topics"]) > 10:
                f.write(f"*... 还有 {len(data['topics']) - 10} 条内容 ...*\n\n")
        
        f.write(f"---\n\n")
        f.write(f"*报告由自动脚本生成*\n")
    
    print(f"📝 Markdown报告已保存: {output_file}")


def main():
    """主函数"""
    print("=" * 60)
    print("🌟 知识星球信息抓取工具")
    print("=" * 60)
    
    # 检查Cookie
    cookie = ZSXQ_COOKIE
    if not cookie:
        print("""
❌ 错误: 未设置Cookie

请通过以下方式之一设置Cookie:

方法1 - 环境变量 (推荐):
  export ZSXQ_COOKIE="zsxq_access_token=你的token值"

方法2 - 修改脚本:
  编辑本脚本，修改 ZSXQ_COOKIE 变量

获取Cookie方法:
  1. 登录 https://wx.zsxq.com
  2. F12打开开发者工具 -> Network
  3. 刷新页面，找到 api.zsxq.com 的请求
  4. 复制 Cookie 字段的完整内容
        """)
        sys.exit(1)
    
    # 初始化爬虫
    try:
        spider = ZsxqApiSpider(cookie)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # 获取星球信息
    print(f"\n🔍 获取星球信息 (ID: {GROUP_ID})...")
    group_info = spider.get_group_info(GROUP_ID)
    group_name = group_info.get("name", "未知星球")
    print(f"✅ 星球名称: {group_name}")
    
    # 显示频道列表
    print(f"\n📋 频道列表:")
    channels = spider.get_channels(GROUP_ID)
    if channels:
        for ch in channels:
            print(f"  - {ch.get('name', '未命名')} (ID: {ch.get('id', 'N/A')})")
    else:
        print("  (未获取到频道列表，API可能不支持)")
    
    # 抓取最近7天数据
    print(f"\n" + "=" * 60)
    topics = fetch_recent_topics(spider, GROUP_ID, TARGET_CHANNEL, days=7)
    
    if not topics:
        print("⚠️ 未抓取到任何主题，请检查:")
        print("  1. Cookie是否有效")
        print("  2. 是否有权限访问该星球")
        print("  3. 频道名称是否正确")
        sys.exit(1)
    
    # 生成统计
    stats = generate_daily_stats(topics)
    
    # 输出统计结果
    print(f"\n" + "=" * 60)
    print("📊 每日信息量统计")
    print("=" * 60)
    total = sum(s["count"] for s in stats.values())
    print(f"总计: {total} 条\n")
    
    for date, data in stats.items():
        count = data["count"]
        bar = "█" * (count * 2)  # 简单的可视化
        print(f"{date}: {count:3d} 条 {bar}")
    
    # 准备输出
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_prefix = f"zsxq_{TARGET_CHANNEL}_{timestamp}" if TARGET_CHANNEL else f"zsxq_all_{timestamp}"
    
    # 保存JSON
    json_file = os.path.join(OUTPUT_DIR, f"{output_prefix}.json")
    save_json({
        "meta": {
            "group_id": GROUP_ID,
            "group_name": group_name,
            "target_channel": TARGET_CHANNEL,
            "fetch_time": datetime.now().isoformat(),
            "total_topics": len(topics)
        },
        "stats": stats,
        "topics": topics
    }, json_file)
    
    # 生成Markdown报告
    md_file = os.path.join(OUTPUT_DIR, f"{output_prefix}.md")
    generate_markdown_report(stats, group_name, 7, md_file)
    
    print(f"\n✅ 完成! 输出文件:")
    print(f"  - JSON: {json_file}")
    print(f"  - 报告: {md_file}")


if __name__ == "__main__":
    main()
