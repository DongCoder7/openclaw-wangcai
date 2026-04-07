#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书多维表格-多行文本链接提取模块

功能: 从飞书多维表格的多行文本列中提取所有URL链接
支持: HTTP/HTTPS/FTP等多种协议的URL识别

作者: AI Assistant
创建时间: 2026-04-07
"""

import requests
import json
import os
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """
    获取飞书tenant_access_token
    
    Args:
        app_id: 飞书应用的App ID
        app_secret: 飞书应用的App Secret
        
    Returns:
        tenant_access_token字符串
        
    Raises:
        Exception: 获取token失败时抛出异常
    """
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    
    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }
    
    payload = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"获取token失败: {result.get('msg', '未知错误')}")
        
        return result["tenant_access_token"]
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"请求获取token失败: {str(e)}")


def extract_urls_from_text(text: str) -> List[Dict[str, str]]:
    """
    从多行文本中提取所有URL链接
    
    支持格式:
    - 纯URL: https://example.com
    - 带协议的URL: http://example.com/path?query=1
    - Markdown链接: [显示文本](https://example.com)
    - 飞书链接格式: <a href="https://example.com">文本</a>
    
    Args:
        text: 多行文本内容
        
    Returns:
        List[Dict]: 提取的URL列表，每个URL包含:
            - url: 原始URL
            - display_text: 显示文本（如果有）
            - protocol: 协议类型
            - domain: 域名
    """
    if not text:
        return []
    
    urls = []
    
    # 1. 匹配Markdown链接格式: [文本](URL)
    markdown_pattern = r'\[([^\]]+)\]\((https?://[^\s\)]+)\)'
    for match in re.finditer(markdown_pattern, text):
        display_text = match.group(1)
        url = match.group(2)
        parsed = urlparse(url)
        urls.append({
            "url": url,
            "display_text": display_text,
            "protocol": parsed.scheme,
            "domain": parsed.netloc,
            "type": "markdown"
        })
    
    # 2. 匹配HTML链接格式: <a href="URL">文本</a>
    html_pattern = r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]*)</a>'
    for match in re.finditer(html_pattern, text):
        url = match.group(1)
        display_text = match.group(2).strip()
        parsed = urlparse(url)
        urls.append({
            "url": url,
            "display_text": display_text,
            "protocol": parsed.scheme,
            "domain": parsed.netloc,
            "type": "html"
        })
    
    # 3. 匹配纯URL（排除已匹配的）
    # 先标记已匹配的位置
    matched_positions = set()
    for match in re.finditer(markdown_pattern, text):
        matched_positions.update(range(match.start(), match.end()))
    for match in re.finditer(html_pattern, text):
        matched_positions.update(range(match.start(), match.end()))
    
    # URL正则：匹配 http://, https://, ftp:// 开头的URL
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?::\d+)?(?:/[^\s<>"\'\)\]\}]*)?'
    
    for match in re.finditer(url_pattern, text):
        # 跳过已匹配的位置
        if any(pos in matched_positions for pos in range(match.start(), match.end())):
            continue
            
        url = match.group(0)
        # 清理末尾的常见标点符号
        url = url.rstrip('.,;:!?)\'\"')
        
        parsed = urlparse(url)
        urls.append({
            "url": url,
            "display_text": "",
            "protocol": parsed.scheme,
            "domain": parsed.netloc,
            "type": "plain"
        })
    
    # 去重（基于URL）
    seen_urls = set()
    unique_urls = []
    for url_info in urls:
        if url_info["url"] not in seen_urls:
            seen_urls.add(url_info["url"])
            unique_urls.append(url_info)
    
    return unique_urls


def feishu_bitable_extract_urls(
    app_token: str,
    table_id: str,
    record_id: str,
    text_field_name: str,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    tenant_access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    从飞书多维表格记录的多行文本列中提取所有URL链接
    
    Args:
        app_token: 多维表格的app_token
        table_id: 表格ID
        record_id: 记录ID
        text_field_name: 多行文本列的字段名
        app_id: 飞书应用的App ID（可选）
        app_secret: 飞书应用的App Secret（可选）
        tenant_access_token: 已获取的tenant_access_token（可选）
        
    Returns:
        Dict: 包含提取结果的JSON格式数据:
        {
            "success": true,
            "record_id": "recxxxxxxxx",
            "field_name": "链接列",
            "raw_text": "原始文本内容",
            "url_count": 5,
            "urls": [
                {
                    "url": "https://example.com",
                    "display_text": "示例网站",
                    "protocol": "https",
                    "domain": "example.com",
                    "type": "markdown"
                }
            ],
            "domains": ["example.com", "feishu.cn"],
            "source": "feishu_bitable"
        }
        
    Raises:
        ValueError: 参数缺失或格式错误
        Exception: API调用失败或字段不存在
    """
    # 参数校验
    if not app_token:
        raise ValueError("app_token不能为空")
    if not table_id:
        raise ValueError("table_id不能为空")
    if not record_id:
        raise ValueError("record_id不能为空")
    if not text_field_name:
        raise ValueError("text_field_name（多行文本列字段名）不能为空")
    
    # 获取tenant_access_token
    token = tenant_access_token
    
    if not token:
        app_id = app_id or os.environ.get("FEISHU_APP_ID")
        app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
        
        if not app_id or not app_secret:
            raise ValueError(
                "未提供有效的tenant_access_token，且无法从参数或环境变量获取"
            )
        
        token = get_tenant_access_token(app_id, app_secret)
    
    # 调用飞书API获取记录
    base_url = "https://open.feishu.cn/open-apis/bitable/v1"
    url = f"{base_url}/apps/{app_token}/tables/{table_id}/records/{record_id}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        result = response.json()
        
        if result.get("code") != 0:
            error_msg = result.get("msg", "未知错误")
            error_codes = {
                1254044: "多维表格不存在或无权访问",
                1254043: "表格不存在或无权访问",
                1254042: "记录不存在或已被删除",
                1254026: "tenant_access_token无效或已过期",
                1254009: "参数错误",
                1254037: "应用无权限访问此多维表格"
            }
            error_code = result.get("code")
            if error_code in error_codes:
                error_msg = f"{error_codes[error_code]} (code: {error_code})"
            raise Exception(f"飞书API调用失败: {error_msg}")
        
        # 获取记录数据
        record = result.get("data", {}).get("record", {})
        fields = record.get("fields", {})
        
        # 检查字段是否存在
        if text_field_name not in fields:
            available_fields = list(fields.keys())
            raise Exception(
                f"字段 '{text_field_name}' 不存在于该记录中。\n"
                f"可用字段: {', '.join(available_fields)}"
            )
        
        # 获取多行文本内容
        raw_text = fields[text_field_name]
        
        # 处理不同类型的字段值
        if isinstance(raw_text, list):
            # 如果是数组类型（如多选、人员等），尝试转换为字符串
            raw_text = '\n'.join(str(item) for item in raw_text)
        elif not isinstance(raw_text, str):
            raw_text = str(raw_text)
        
        # 提取URL
        urls = extract_urls_from_text(raw_text)
        
        # 构建返回结果
        domains = list(set(url["domain"] for url in urls if url["domain"]))
        
        return {
            "success": True,
            "record_id": record_id,
            "field_name": text_field_name,
            "raw_text": raw_text,
            "url_count": len(urls),
            "urls": urls,
            "domains": domains,
            "source": "feishu_bitable",
            "timestamp": result.get("data", {}).get("record", {}).get("updated_time")
        }
        
    except requests.exceptions.Timeout:
        raise Exception("请求超时，请检查网络连接")
    except requests.exceptions.ConnectionError:
        raise Exception("网络连接失败")
    except requests.exceptions.RequestException as e:
        raise Exception(f"HTTP请求异常: {str(e)}")


def feishu_bitable_extract_urls_batch(
    app_token: str,
    table_id: str,
    record_ids: List[str],
    text_field_name: str,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    tenant_access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    批量从多条记录中提取URL链接
    
    Args:
        record_ids: 记录ID列表
        其他参数同 feishu_bitable_extract_urls
        
    Returns:
        Dict: 批量提取结果
    """
    # 获取token（一次性获取，复用）
    token = tenant_access_token
    if not token:
        app_id = app_id or os.environ.get("FEISHU_APP_ID")
        app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
        if app_id and app_secret:
            token = get_tenant_access_token(app_id, app_secret)
    
    results = []
    total_urls = 0
    all_domains = set()
    
    for record_id in record_ids:
        try:
            result = feishu_bitable_extract_urls(
                app_token=app_token,
                table_id=table_id,
                record_id=record_id,
                text_field_name=text_field_name,
                tenant_access_token=token  # 复用token
            )
            results.append(result)
            total_urls += result["url_count"]
            all_domains.update(result.get("domains", []))
        except Exception as e:
            results.append({
                "success": False,
                "record_id": record_id,
                "error": str(e)
            })
    
    return {
        "success": True,
        "batch_size": len(record_ids),
        "success_count": sum(1 for r in results if r.get("success")),
        "fail_count": sum(1 for r in results if not r.get("success")),
        "total_urls": total_urls,
        "all_domains": sorted(list(all_domains)),
        "results": results
    }


def parse_bitable_url(url: str) -> Dict[str, str]:
    """
    从飞书多维表格URL中解析app_token和table_id
    
    Args:
        url: 飞书多维表格URL，支持格式:
            - https://www.feishu.cn/base/XXX?table=YYY
            - https://www.feishu.cn/wiki/XXX?table=YYY
            - https://base.feishu.cn/base/XXX?table=YYY
            
    Returns:
        Dict: {"app_token": "XXX", "table_id": "YYY"}
        
    Raises:
        ValueError: URL格式不正确
    """
    import re
    
    # 提取app_token
    app_token_match = re.search(r'/(?:base|wiki)/([a-zA-Z0-9]+)', url)
    if not app_token_match:
        raise ValueError(f"无法从URL中解析app_token: {url}")
    
    app_token = app_token_match.group(1)
    
    # 提取table_id
    table_id_match = re.search(r'[?&]table=([a-zA-Z0-9]+)', url)
    if not table_id_match:
        raise ValueError(f"无法从URL中解析table_id，请确保URL包含table参数: {url}")
    
    table_id = table_id_match.group(1)
    
    return {
        "app_token": app_token,
        "table_id": table_id
    }


def main():
    """
    命令行调用入口
    
    使用方式:
        # 单条记录提取
        python feishu_bitable_extract_urls.py \
            --app_token XXX --table_id XXX --record_id XXX \
            --field_name "链接列"
            
        # 从URL自动解析
        python feishu_bitable_extract_urls.py \
            --url "https://www.feishu.cn/base/XXX?table=YYY" \
            --record_id XXX \
            --field_name "链接列"
            
        # 批量提取
        python feishu_bitable_extract_urls.py \
            --app_token XXX --table_id XXX \
            --record_ids "id1,id2,id3" \
            --field_name "链接列"
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="从飞书多维表格多行文本列中提取URL链接"
    )
    
    # URL或手动指定参数
    parser.add_argument("--url", help="飞书多维表格完整URL（会自动解析app_token和table_id）")
    parser.add_argument("--app_token", help="多维表格app_token")
    parser.add_argument("--table_id", help="表格ID")
    
    # 记录ID（支持单条或批量）
    parser.add_argument("--record_id", help="单条记录ID")
    parser.add_argument("--record_ids", help="批量记录ID，用逗号分隔")
    
    # 字段名
    parser.add_argument("--field_name", required=True, help="多行文本列的字段名")
    
    # 认证信息
    parser.add_argument("--app_id", help="飞书应用App ID")
    parser.add_argument("--app_secret", help="飞书应用App Secret")
    parser.add_argument("--token", dest="tenant_access_token", help="tenant_access_token")
    
    # 输出
    parser.add_argument("--output", "-o", help="输出文件路径（JSON格式）")
    
    args = parser.parse_args()
    
    try:
        # 解析URL参数
        if args.url:
            parsed = parse_bitable_url(args.url)
            app_token = parsed["app_token"]
            table_id = parsed["table_id"]
        else:
            if not args.app_token or not args.table_id:
                raise ValueError("请提供 --url 或同时提供 --app_token 和 --table_id")
            app_token = args.app_token
            table_id = args.table_id
        
        # 确定记录ID列表
        if args.record_ids:
            record_ids = [rid.strip() for rid in args.record_ids.split(",")]
            result = feishu_bitable_extract_urls_batch(
                app_token=app_token,
                table_id=table_id,
                record_ids=record_ids,
                text_field_name=args.field_name,
                app_id=args.app_id,
                app_secret=args.app_secret,
                tenant_access_token=args.tenant_access_token
            )
        elif args.record_id:
            result = feishu_bitable_extract_urls(
                app_token=app_token,
                table_id=table_id,
                record_id=args.record_id,
                text_field_name=args.field_name,
                app_id=args.app_id,
                app_secret=args.app_secret,
                tenant_access_token=args.tenant_access_token
            )
        else:
            raise ValueError("请提供 --record_id（单条）或 --record_ids（批量，逗号分隔）")
        
        # 格式化输出
        output_json = json.dumps(result, ensure_ascii=False, indent=2)
        print(output_json)
        
        # 保存到文件
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print(f"\n✅ 结果已保存到: {args.output}")
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}", file=__import__('sys').stderr)
        exit(1)


if __name__ == "__main__":
    main()
