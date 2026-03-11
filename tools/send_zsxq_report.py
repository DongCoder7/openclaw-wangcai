#!/root/.openclaw/workspace/venv/bin/python3
"""发送知识星球抓取报告到Feishu - 增量版，只发送新内容

用法:
  ./venv_runner.sh tools/send_zsxq_report.py [all|group2|group3]

特性:
  - 只发送当天的新内容
  - 记录上次发送的topic_id，避免重复推送
  - 如果没有新内容，发送"无新内容"提示

环境变量:
  ZSXQ_TARGET_USER - 指定接收消息的Feishu user_id
"""
import json
from datetime import datetime
from pathlib import Path
import sys
import os
import subprocess

sys.path.insert(0, '/root/.openclaw/workspace')

# 配置
DEFAULT_USER_ID = "ou_efbad805767f4572e8f93ebafa8d5402"
TARGET_USER_ID = os.getenv("ZSXQ_TARGET_USER", DEFAULT_USER_ID)
MAX_MSG_LENGTH = 3500

GROUP_CONFIG = {
    "group1": {"id": "51122188845424", "name": "调研纪要"},
    "group2": {"id": "51111818455824", "name": "投资交流"},
    "group3": {"id": "88512145458842", "name": "行业研究"},
}

DATA_DIR = Path("/root/.openclaw/workspace/data/zsxq/raw")
STATE_DIR = Path("/root/.openclaw/workspace/data/zsxq/state")
STATE_DIR.mkdir(parents=True, exist_ok=True)


def get_state_file(group_id: str) -> Path:
    """获取状态文件路径"""
    return STATE_DIR / f"last_sent_{group_id}.json"


def load_last_sent(group_id: str) -> set:
    """加载上次已发送的topic_id"""
    state_file = get_state_file(group_id)
    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get("sent_ids", []))
    return set()


def save_sent_ids(group_id: str, sent_ids: set):
    """保存已发送的topic_id"""
    state_file = get_state_file(group_id)
    data = {
        "last_sent_time": datetime.now().isoformat(),
        "sent_ids": list(sent_ids)
    }
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_feishu_message(message: str, user_id: str = None) -> bool:
    """通过OpenClaw CLI发送Feishu消息"""
    if not user_id:
        user_id = TARGET_USER_ID
    
    cmd = [
        "openclaw", "message", "send",
        "--channel", "feishu",
        "--target", f"user:{user_id}",
        "--message", message
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False


def split_message(content: str, max_length: int = MAX_MSG_LENGTH) -> list:
    """将长消息分割"""
    if len(content) <= max_length:
        return [content]
    
    parts = []
    lines = content.split('\n')
    current_part = ""
    
    for line in lines:
        if len(line) > max_length:
            if current_part:
                parts.append(current_part.rstrip())
                current_part = ""
            for i in range(0, len(line), max_length):
                parts.append(line[i:i+max_length])
            continue
        
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part.rstrip())
            current_part = line + '\n'
        else:
            current_part += line + '\n'
    
    if current_part:
        parts.append(current_part.rstrip())
    
    return parts


def format_topic(topic: dict, index: int) -> str:
    """格式化单个帖子"""
    lines = []
    
    title = topic.get('title', '')
    content = topic.get('content', '')
    author = topic.get('author', 'Unknown')
    create_time = topic.get('create_time', '')
    
    try:
        dt = datetime.fromisoformat(create_time.replace('Z', '+00:00').replace('+0800', '+08:00'))
        time_str = dt.strftime("%H:%M")
    except:
        time_str = create_time[:16] if create_time else "未知时间"
    
    lines.append(f"【{index}】{title[:80] if title else '(无标题)'}")
    lines.append(f"👤 {author}  |  🕐 {time_str}")
    lines.append("-" * 40)
    
    if content:
        content_clean = content.replace('\r\n', '\n').replace('\r', '\n')
        lines.append(content_clean[:1500])  # 限制单帖长度
    else:
        lines.append("[无正文内容]")
    
    if topic.get('has_attachment'):
        lines.append("\n📎 [包含附件]")
    if topic.get('image_count', 0) > 0:
        lines.append(f"\n🖼️ [包含 {topic['image_count']} 张图片]")
    
    lines.append("")
    return '\n'.join(lines)


def send_group_report(group_key: str, target_date: str = None) -> bool:
    """发送Group报告，只发送新内容"""
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    group_info = GROUP_CONFIG.get(group_key)
    if not group_info:
        print(f"❌ 未知Group: {group_key}")
        return False
    
    group_id = group_info["id"]
    group_name = group_info["name"]
    
    # 读取数据文件
    file_path = DATA_DIR / f"{target_date}_{group_id}.json"
    
    if not file_path.exists():
        print(f"⚠️ {group_name}: 无数据文件")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            topics = json.load(f)
    except Exception as e:
        print(f"❌ {group_name}: 读取失败 - {e}")
        return False
    
    # 加载上次已发送的
    last_sent_ids = load_last_sent(group_id)
    
    # 过滤新内容
    new_topics = []
    new_ids = []
    
    for topic in topics:
        topic_id = str(topic.get("topic_id", ""))
        if topic_id and topic_id not in last_sent_ids:
            new_topics.append(topic)
            new_ids.append(topic_id)
    
    print(f"📊 {group_name}: 共 {len(topics)} 条，新内容 {len(new_topics)} 条")
    
    if not new_topics:
        # 没有新内容，发送提示
        msg = f"📭 知识星球 - {group_name}\n时间: {datetime.now().strftime('%H:%M')}\n\n暂无新内容更新"
        print(f"📤 发送: 无新内容")
        send_feishu_message(msg, TARGET_USER_ID)
        return True
    
    # 生成报告头
    header = f"📊 知识星球 - {group_name}\n时间: {datetime.now().strftime('%H:%M')}\n新内容: {len(new_topics)} 条\n{'='*50}\n\n"
    
    # 生成内容
    content_parts = []
    for i, topic in enumerate(new_topics, 1):
        content_parts.append(format_topic(topic, i))
    
    full_content = '\n'.join(content_parts)
    
    # 分割消息
    messages = split_message(header + full_content)
    
    # 添加批次标记
    if len(messages) > 1:
        for i in range(len(messages)):
            messages[i] = f"【{i+1}/{len(messages)}】\n{messages[i]}"
    
    # 发送
    print(f"📤 准备发送 {len(messages)} 条消息...")
    all_sent = True
    for i, msg in enumerate(messages, 1):
        print(f"  发送第 {i}/{len(messages)} 条...")
        if not send_feishu_message(msg, TARGET_USER_ID):
            all_sent = False
        if i < len(messages):
            time.sleep(1)
    
    # 更新已发送记录
    if all_sent:
        last_sent_ids.update(new_ids)
        save_sent_ids(group_id, last_sent_ids)
        print(f"✅ 已更新发送记录: {len(new_ids)} 条")
    
    return all_sent


def main():
    """主函数"""
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    print(f"🚀 发送知识星球报告 (增量)")
    print(f"目标用户: {TARGET_USER_ID}")
    print("-" * 60)
    
    if mode == "group2":
        send_group_report("group2")
    elif mode == "group3":
        send_group_report("group3")
    elif mode == "all":
        send_group_report("group2")
        time.sleep(2)
        send_group_report("group3")
    else:
        print(f"❌ 未知模式: {mode}")
        sys.exit(1)
    
    print("\n✅ 完成")


if __name__ == "__main__":
    import time
    main()
