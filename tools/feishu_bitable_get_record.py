#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书多维表格API调用模块
模块名: feishu_bitable_get_record
功能: 根据record_id获取单条记录详情

作者: AI Assistant
创建时间: 2026-04-07
"""

import requests
import json
import os
from typing import Dict, Any, Optional


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


def feishu_bitable_get_record(
    app_token: str,
    table_id: str,
    record_id: str,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    tenant_access_token: Optional[str] = None,
    with_shared_url: bool = False
) -> Dict[str, Any]:
    """
    根据record_id获取飞书多维表格单条记录详情
    
    官方API文档: https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/bitable-v1/app-table-record/get
    
    Args:
        app_token: 多维表格的app_token（从URL /base/XXX 或 /wiki/XXX 中获取）
        table_id: 表格ID（从URL ?table=YYY 中获取）
        record_id: 记录ID（行ID）
        app_id: 飞书应用的App ID（可选，如提供则会自动获取token）
        app_secret: 飞书应用的App Secret（可选，如提供则会自动获取token）
        tenant_access_token: 已获取的tenant_access_token（可选，优先级高于app_id/app_secret）
        with_shared_url: 是否返回记录分享链接（可选，默认False）
        
    Returns:
        Dict: 包含记录详情的JSON格式数据，结构如下:
        {
            "code": 0,
            "msg": "success",
            "data": {
                "record": {
                    "record_id": "recxxxxxxxx",
                    "fields": {
                        "字段名": "字段值",
                        ...
                    },
                    "created_time": 1604181439,
                    "updated_time": 1604181439,
                    "created_by": {
                        "id": "ou_xxxxxxxx",
                        "name": "张三",
                        "en_name": "Zhang San"
                    },
                    "updated_by": {
                        "id": "ou_xxxxxxxx",
                        "name": "张三",
                        "en_name": "Zhang San"
                    },
                    "shared_url": "https://base.feishu.cn/..."  # 仅当with_shared_url=True时返回
                }
            }
        }
        
    Raises:
        ValueError: 参数缺失或格式错误
        Exception: API调用失败
        
    Examples:
        # 方式1: 使用已获取的tenant_access_token
        result = feishu_bitable_get_record(
            app_token="OuXxxxxx",
            table_id="tblXxxxxx",
            record_id="recXxxxxx",
            tenant_access_token="your_token"
        )
        
        # 方式2: 使用app_id和app_secret自动获取token
        result = feishu_bitable_get_record(
            app_token="OuXxxxxx",
            table_id="tblXxxxxx",
            record_id="recXxxxxx",
            app_id="cli_xxxxxx",
            app_secret="xxxxxx"
        )
        
        # 方式3: 从环境变量读取凭证
        result = feishu_bitable_get_record(
            app_token="OuXxxxxx",
            table_id="tblXxxxxx",
            record_id="recXxxxxx"
        )
    """
    # 参数校验
    if not app_token:
        raise ValueError("app_token不能为空")
    if not table_id:
        raise ValueError("table_id不能为空")
    if not record_id:
        raise ValueError("record_id不能为空")
    
    # 获取tenant_access_token
    token = tenant_access_token
    
    if not token:
        # 优先从参数获取
        app_id = app_id or os.environ.get("FEISHU_APP_ID")
        app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
        
        if not app_id or not app_secret:
            raise ValueError(
                "未提供有效的tenant_access_token，且无法从参数或环境变量(FEISHU_APP_ID/FEISHU_APP_SECRET)获取"
            )
        
        token = get_tenant_access_token(app_id, app_secret)
    
    # 构建API请求
    base_url = "https://open.feishu.cn/open-apis/bitable/v1"
    url = f"{base_url}/apps/{app_token}/tables/{table_id}/records/{record_id}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 请求参数
    params = {}
    if with_shared_url:
        params["with_shared_url"] = "true"
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        # 解析响应
        result = response.json()
        
        # 检查API返回状态
        if result.get("code") != 0:
            error_msg = result.get("msg", "未知错误")
            
            # 常见错误码处理
            error_codes = {
                1254044: "多维表格不存在或无权访问",
                1254043: "表格不存在或无权访问",
                1254042: "记录不存在或已被删除",
                1254026: "tenant_access_token无效或已过期",
                1254009: "参数错误，请检查app_token/table_id/record_id格式",
                1254037: "应用无权限访问此多维表格"
            }
            
            error_code = result.get("code")
            if error_code in error_codes:
                error_msg = f"{error_codes[error_code]} (code: {error_code})"
            
            raise Exception(f"飞书API调用失败: {error_msg}")
        
        return result
        
    except requests.exceptions.Timeout:
        raise Exception("请求超时，请检查网络连接或稍后重试")
    except requests.exceptions.ConnectionError:
        raise Exception("网络连接失败，请检查网络状态")
    except requests.exceptions.RequestException as e:
        raise Exception(f"HTTP请求异常: {str(e)}")


def main():
    """
    命令行调用入口
    
    使用方式:
        python feishu_bitable_get_record.py --app_token XXX --table_id XXX --record_id XXX
        
    环境变量:
        FEISHU_APP_ID: 飞书应用App ID
        FEISHU_APP_SECRET: 飞书应用App Secret
        FEISHU_TENANT_ACCESS_TOKEN: 已获取的tenant_access_token
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="获取飞书多维表格单条记录详情")
    parser.add_argument("--app_token", required=True, help="多维表格app_token")
    parser.add_argument("--table_id", required=True, help="表格ID")
    parser.add_argument("--record_id", required=True, help="记录ID")
    parser.add_argument("--app_id", help="飞书应用App ID（可选）")
    parser.add_argument("--app_secret", help="飞书应用App Secret（可选）")
    parser.add_argument("--token", dest="tenant_access_token", help="tenant_access_token（可选）")
    parser.add_argument("--with_shared_url", action="store_true", help="返回记录分享链接")
    
    args = parser.parse_args()
    
    try:
        result = feishu_bitable_get_record(
            app_token=args.app_token,
            table_id=args.table_id,
            record_id=args.record_id,
            app_id=args.app_id,
            app_secret=args.app_secret,
            tenant_access_token=args.tenant_access_token,
            with_shared_url=args.with_shared_url
        )
        
        # 格式化输出
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}", file=__import__('sys').stderr)
        exit(1)


if __name__ == "__main__":
    main()
