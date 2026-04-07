#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务: 飞书多维表格URL提取 (每日19:35执行)

功能: 遍历飞书多维表格所有记录，提取"网址"列中的所有URL链接
表格URL: https://www.feishu.cn/base/CcVhbCCFna7nPMsXnSRlIWv9nwg?table=tbllr4k6yLw1fpyr

作者: AI Assistant
创建时间: 2026-04-07
定时: 每日19:35
"""

import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.feishu_bitable_extract_urls import (
    feishu_bitable_extract_urls,
    get_tenant_access_token
)
from tools.feishu_bitable_extract_urls import feishu_bitable_extract_urls as extract_urls

import requests


# 配置信息
CONFIG = {
    "app_token": "CcVhbCCFna7nPMsXnSRlIWv9nwg",
    "table_id": "tbllr4k6yLw1fpyr",
    "field_name": "网址",
    "feishu_user_id": "ou_efbad805767f4572e8f93ebafa8d5402"
}


def get_all_records(app_token: str, table_id: str, token: str, page_size: int = 500) -> List[Dict]:
    """
    获取表格中的所有记录
    
    Args:
        app_token: 多维表格app_token
        table_id: 表格ID
        token: tenant_access_token
        page_size: 每页记录数
        
    Returns:
        List[Dict]: 所有记录列表
    """
    all_records = []
    page_token = None
    
    base_url = "https://open.feishu.cn/open-apis/bitable/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    while True:
        url = f"{base_url}/apps/{app_token}/tables/{table_id}/records"
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            result = response.json()
            
            if result.get("code") != 0:
                error_msg = result.get("msg", "未知错误")
                raise Exception(f"获取记录列表失败: {error_msg}")
            
            data = result.get("data", {})
            records = data.get("items", [])
            all_records.extend(records)
            
            # 检查是否有下一页
            page_token = data.get("page_token")
            has_more = data.get("has_more", False)
            
            print(f"  ✅ 获取到 {len(records)} 条记录，累计 {len(all_records)} 条")
            
            if not has_more or not page_token:
                break
                
        except Exception as e:
            raise Exception(f"获取记录列表失败: {str(e)}")
    
    return all_records


def extract_urls_from_all_records(
    app_token: str,
    table_id: str,
    field_name: str,
    token: str
) -> Dict[str, Any]:
    """
    从所有记录中提取URL
    
    Args:
        app_token: 多维表格app_token
        table_id: 表格ID
        field_name: 字段名
        token: tenant_access_token
        
    Returns:
        Dict: 提取结果汇总
    """
    print("📋 步骤1: 获取所有记录...")
    records = get_all_records(app_token, table_id, token)
    print(f"✅ 共获取到 {len(records)} 条记录\n")
    
    print("🔗 步骤2: 提取URL链接...")
    all_urls = []
    records_with_urls = 0
    records_without_urls = 0
    errors = []
    
    for i, record in enumerate(records, 1):
        record_id = record.get("record_id", "unknown")
        fields = record.get("fields", {})
        
        # 显示进度
        if i % 10 == 0 or i == len(records):
            print(f"  处理中... {i}/{len(records)} ({i*100//len(records)}%)")
        
        # 检查字段是否存在
        if field_name not in fields:
            continue
        
        # 提取URL
        try:
            # 导入提取函数
            from tools.feishu_bitable_extract_urls import extract_urls_from_text
            
            raw_text = fields[field_name]
            if isinstance(raw_text, list):
                raw_text = '\n'.join(str(item) for item in raw_text)
            elif not isinstance(raw_text, str):
                raw_text = str(raw_text)
            
            if not raw_text.strip():
                records_without_urls += 1
                continue
            
            urls = extract_urls_from_text(raw_text)
            
            if urls:
                records_with_urls += 1
                for url_info in urls:
                    all_urls.append({
                        "record_id": record_id,
                        **url_info
                    })
            else:
                records_without_urls += 1
                
        except Exception as e:
            errors.append({
                "record_id": record_id,
                "error": str(e)
            })
    
    print(f"✅ URL提取完成\n")
    
    # 统计域名
    domains = {}
    for url_info in all_urls:
        domain = url_info.get("domain", "unknown")
        domains[domain] = domains.get(domain, 0) + 1
    
    return {
        "success": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "table_info": {
            "app_token": app_token,
            "table_id": table_id,
            "field_name": field_name
        },
        "summary": {
            "total_records": len(records),
            "records_with_urls": records_with_urls,
            "records_without_urls": records_without_urls,
            "total_urls": len(all_urls),
            "errors": len(errors)
        },
        "domain_stats": sorted(
            [{"domain": k, "count": v} for k, v in domains.items()],
            key=lambda x: x["count"],
            reverse=True
        ),
        "urls": all_urls,
        "errors": errors
    }


def send_to_feishu(user_id: str, message: str, title: str = "") -> bool:
    """
    发送消息到飞书用户
    
    Args:
        user_id: 飞书用户ID
        message: 消息内容
        title: 消息标题
        
    Returns:
        bool: 是否发送成功
    """
    # 从环境变量获取token
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    
    if not app_id or not app_secret:
        print("⚠️ 未配置FEISHU_APP_ID/FEISHU_APP_SECRET，跳过发送")
        return False
    
    try:
        token = get_tenant_access_token(app_id, app_secret)
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        # 构建消息内容
        content = {
            "text": message
        }
        
        payload = {
            "receive_id": user_id,
            "msg_type": "text",
            "content": json.dumps(content, ensure_ascii=False)
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        result = response.json()
        
        if result.get("code") == 0:
            print(f"✅ 消息已发送到飞书用户: {user_id}")
            return True
        else:
            print(f"❌ 发送失败: {result.get('msg', '未知错误')}")
            return False
            
    except Exception as e:
        print(f"❌ 发送失败: {str(e)}")
        return False


def format_report(result: Dict[str, Any]) -> str:
    """
    格式化报告内容为飞书消息
    
    Args:
        result: 提取结果
        
    Returns:
        str: 格式化后的消息文本
    """
    summary = result["summary"]
    domain_stats = result["domain_stats"]
    urls = result["urls"]
    
    # 限制显示的URL数量（避免消息过长）
    max_display_urls = 20
    
    lines = [
        "📊 **飞书多维表格URL提取报告**",
        f"📅 提取时间: {result['timestamp']}",
        "",
        "**📈 统计概览**",
        f"• 总记录数: {summary['total_records']}",
        f"• 含URL记录: {summary['records_with_urls']}",
        f"• 空记录: {summary['records_without_urls']}",
        f"• 总URL数: {summary['total_urls']}",
        "",
        "**🌐 域名分布 (TOP 10)**",
    ]
    
    for i, domain_info in enumerate(domain_stats[:10], 1):
        lines.append(f"{i}. {domain_info['domain']}: {domain_info['count']}个")
    
    lines.extend([
        "",
        f"**🔗 URL列表 (显示前{min(len(urls), max_display_urls)}个)**",
        ""
    ])
    
    for i, url_info in enumerate(urls[:max_display_urls], 1):
        display = url_info.get('display_text', '')
        url = url_info['url']
        domain = url_info.get('domain', '')
        
        if display:
            lines.append(f"{i}. [{display}]({url})")
        else:
            lines.append(f"{i}. {url}")
        
        if domain:
            lines[-1] += f" ({domain})"
    
    if len(urls) > max_display_urls:
        lines.append(f"\n... 还有 {len(urls) - max_display_urls} 个URL未显示")
    
    if result.get("errors"):
        lines.extend([
            "",
            f"⚠️ **错误**: {len(result['errors'])}条记录处理失败"
        ])
    
    lines.extend([
        "",
        "---",
        f"📁 完整数据已保存至: `data/feishu_urls_{datetime.now().strftime('%Y%m%d')}.json`"
    ])
    
    return "\n".join(lines)


def main():
    """
    主函数 - 定时任务入口
    """
    print("=" * 60)
    print("🌅 飞书多维表格URL提取任务")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    # 检查环境变量
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    
    if not app_id or not app_secret:
        print("❌ 错误: 未配置FEISHU_APP_ID或FEISHU_APP_SECRET环境变量")
        print("请先设置环境变量:")
        print("  export FEISHU_APP_ID='your_app_id'")
        print("  export FEISHU_APP_SECRET='your_app_secret'")
        sys.exit(1)
    
    try:
        # 获取token
        print("🔑 获取访问令牌...")
        token = get_tenant_access_token(app_id, app_secret)
        print("✅ 令牌获取成功\n")
        
        # 提取URL
        result = extract_urls_from_all_records(
            app_token=CONFIG["app_token"],
            table_id=CONFIG["table_id"],
            field_name=CONFIG["field_name"],
            token=token
        )
        
        # 保存完整数据到文件
        output_file = f"data/feishu_urls_{datetime.now().strftime('%Y%m%d')}.json"
        os.makedirs("data", exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 完整数据已保存: {output_file}\n")
        
        # 格式化并发送报告
        report = format_report(result)
        print("📤 发送报告到飞书...")
        send_to_feishu(CONFIG["feishu_user_id"], report)
        
        print("\n" + "=" * 60)
        print("✅ 任务完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 任务执行失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
