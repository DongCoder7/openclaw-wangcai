#!/root/.openclaw/workspace/venv/bin/python3
"""发送知识星球抓取报告到Feishu - 完整版，支持分批发送

用法:
  ./venv_runner.sh tools/send_zsxq_report.py [all|group2|group3]

参数:
  all     - 发送所有Group的汇总报告
  group2  - 只发送Group 2 (51111818455824) 的报告
  group3  - 只发送Group 3 (88512145458842) 的报告

环境变量:
  ZSXQ_TARGET_USER - 指定接收消息的Feishu user_id
  MAX_MSG_LENGTH   - 单条消息最大长度 (默认 3500)
"""
import json
from datetime import datetime
from pathlib import Path
import sys
import os
import subprocess

sys.path.insert(0, '/root/.openclaw/workspace')

# Feishu 配置
DEFAULT_USER_ID = "ou_efbad805767f4572e8f93ebafa8d5402"
TARGET_USER_ID = os.getenv("ZSXQ_TARGET_USER", DEFAULT_USER_ID)
MAX_MSG_LENGTH = int(os.getenv("MAX_MSG_LENGTH", "3500"))  # Feishu限制约4096，留些余量

# Group 配置
GROUP_CONFIG = {
    "group1": {"id": "51122188845424", "name": "调研纪要"},
    "group2": {"id": "51111818455824", "name": "投资交流"},
    "group3": {"id": "88512145458842", "name": "行业研究"},
}

# 数据目录
DATA_DIR = Path("/root/.openclaw/workspace/data/zsxq/raw")


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
        if result.returncode == 0:
            print(f"✅ 消息已发送 (长度: {len(message)} 字符)")
            return True
        else:
            print(f"❌ 发送失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False


def split_message(content: str, max_length: int = MAX_MSG_LENGTH) -> list:
    """将长消息分割成多个部分"""
    if len(content) <= max_length:
        return [content]
    
    parts = []
    lines = content.split('\n')
    current_part = ""
    
    for line in lines:
        # 如果单行就超过限制，需要截断
        if len(line) > max_length:
            if current_part:
                parts.append(current_part.rstrip())
                current_part = ""
            # 截断长行
            for i in range(0, len(line), max_length):
                parts.append(line[i:i+max_length])
            continue
        
        # 检查添加这一行后是否超过限制
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
    
    # 标题行
    title = topic.get('title', '')
    content = topic.get('content', '')
    author = topic.get('author', 'Unknown')
    create_time = topic.get('create_time', '')
    
    # 解析时间
    try:
        dt = datetime.fromisoformat(create_time.replace('Z', '+00:00').replace('+0800', '+08:00'))
        time_str = dt.strftime("%H:%M")
    except:
        time_str = create_time[:16] if create_time else "未知时间"
    
    # 帖子标题
    lines.append(f"【{index}】{title[:100] if title else '(无标题)'}")
    lines.append(f"👤 {author}  |  🕐 {time_str}")
    
    # 分隔线
    lines.append("-" * 40)
    
    # 正文内容
    if content:
        # 清理内容，保留换行
        content_clean = content.replace('\r\n', '\n').replace('\r', '\n')
        lines.append(content_clean)
    else:
        lines.append("[无正文内容]")
    
    # 图片/附件信息
    if topic.get('has_attachment'):
        lines.append("\n📎 [包含附件]")
    if topic.get('image_count', 0) > 0:
        lines.append(f"\n🖼️ [包含 {topic['image_count']} 张图片]")
    
    # 频道标签
    channels = topic.get('channels', [])
    if channels:
        lines.append(f"\n🏷️ {' | '.join(channels)}")
    
    lines.append("")  # 空行分隔
    return '\n'.join(lines)


def generate_full_group_report(group_key: str, target_date: str = None) -> list:
    """生成单个Group的完整报告，返回消息列表（已分批）"""
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    group_info = GROUP_CONFIG.get(group_key)
    if not group_info:
        return [f"❌ 未知Group: {group_key}"]
    
    group_id = group_info["id"]
    group_name = group_info["name"]
    
    # 读取数据文件 - 只读当天
    file_path = DATA_DIR / f"{target_date}_{group_id}.json"
    
    if not file_path.exists():
        return [f"❌ {group_name} ({target_date}): 无数据文件"]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if isinstance(data, list):
            topics = data
        elif isinstance(data, dict) and 'topics' in data:
            topics = data['topics']
        else:
            topics = [data] if data else []
        
        count = len(topics)
        
        # 生成完整报告头
        header_lines = []
        header_lines.append(f"📊 知识星球 - {group_name}")
        header_lines.append(f"日期: {target_date}")
        header_lines.append(f"帖子数: {count} 条")
        header_lines.append("=" * 50)
        header = '\n'.join(header_lines)
        
        if count == 0:
            return [header + "\n\n暂无帖子数据"]
        
        # 生成所有帖子内容
        all_content = []
        for i, topic in enumerate(topics, 1):
            all_content.append(format_topic(topic, i))
        
        # 合并所有内容
        full_content = '\n'.join(all_content)
        
        # 分割成多条消息
        messages = split_message(header + "\n\n" + full_content)
        
        # 为分批消息添加序号
        if len(messages) > 1:
            for i, msg in enumerate(messages, 1):
                messages[i-1] = f"【{i}/{len(messages)}】\n{msg}"
        
        return messages
        
    except Exception as e:
        return [f"❌ {group_name}: 读取失败 - {e}"]


def main():
    """主函数"""
    # 获取参数
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    target_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"🚀 发送知识星球完整报告 ({target_date})")
    print(f"模式: {mode}")
    print(f"目标用户: {TARGET_USER_ID}")
    print(f"单条消息限制: {MAX_MSG_LENGTH} 字符")
    print("-" * 60)
    
    if mode == "group2":
        # 发送Group 2完整报告
        messages = generate_full_group_report("group2", target_date)
        print(f"📤 准备发送 {len(messages)} 条消息...")
        
        for i, msg in enumerate(messages, 1):
            print(f"\n发送第 {i}/{len(messages)} 条...")
            send_feishu_message(msg, TARGET_USER_ID)
            if i < len(messages):
                import time
                time.sleep(1)  # 分批发送间隔
        
    elif mode == "group3":
        # 发送Group 3完整报告
        messages = generate_full_group_report("group3", target_date)
        print(f"📤 准备发送 {len(messages)} 条消息...")
        
        for i, msg in enumerate(messages, 1):
            print(f"\n发送第 {i}/{len(messages)} 条...")
            send_feishu_message(msg, TARGET_USER_ID)
            if i < len(messages):
                import time
                time.sleep(1)
        
    elif mode == "all":
        # 发送所有Group
        for group_key in ["group2", "group3"]:
            messages = generate_full_group_report(group_key, target_date)
            group_name = GROUP_CONFIG[group_key]["name"]
            print(f"\n📤 {group_name}: 准备发送 {len(messages)} 条消息...")
            
            for i, msg in enumerate(messages, 1):
                print(f"  发送第 {i}/{len(messages)} 条...")
                send_feishu_message(msg, TARGET_USER_ID)
                if i < len(messages):
                    import time
                    time.sleep(1)
            
            # Group之间间隔
            import time
            time.sleep(2)
        
    else:
        print(f"❌ 未知模式: {mode}")
        print("用法: send_zsxq_report.py [all|group2|group3]")
        sys.exit(1)
    
    print("\n✅ 全部发送完成")


if __name__ == "__main__":
    main()
