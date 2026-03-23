#!/root/.openclaw/workspace/venv/bin/python3
"""
获取知识星球PDF下载链接并解析内容
"""

import requests
import json
import os
import re
from datetime import datetime
from io import BytesIO

# 尝试导入PDF解析库
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

GROUP_ID = "88512145458842"
FILE_ID = "812222181818442"  # 从之前解析得到
TOPIC_ID = "45811258122824288"
COOKIE = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%84%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU0NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22NDIxODgyNTQ0NTgxODg4%22%7D%2C%22%24device_id%22%3A%221OTk1NzI5OGM4MzkwMyJ9; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

BASE_URL = "https://api.zsxq.com/v2"

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

def get_file_download_url(file_id: str) -> str:
    """获取文件下载链接"""
    # 尝试多种可能的API端点
    endpoints = [
        f"{BASE_URL}/files/{file_id}/download_url",
        f"{BASE_URL}/groups/{GROUP_ID}/files/{file_id}/download_url",
    ]
    
    for url in endpoints:
        try:
            print(f"🔄 尝试: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("succeeded"):
                resp_data = data.get("resp_data", {})
                download_url = resp_data.get("download_url")
                if download_url:
                    return download_url
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            continue
    
    return None

def download_and_parse_pdf(download_url: str) -> str:
    """下载并解析PDF内容"""
    try:
        print(f"📥 下载PDF...")
        response = requests.get(download_url, timeout=60)
        response.raise_for_status()
        
        pdf_bytes = BytesIO(response.content)
        
        # 使用pdfplumber (效果更好)
        if HAS_PDFPLUMBER:
            print("📖 使用pdfplumber解析...")
            text = ""
            with pdfplumber.open(pdf_bytes) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- 第{i+1}页 ---\n"
                        text += page_text
            return text
        
        # 使用PyPDF2
        elif HAS_PYPDF2:
            print("📖 使用PyPDF2解析...")
            text = ""
            pdf_reader = PyPDF2.PdfReader(pdf_bytes)
            for i, page in enumerate(pdf_reader.pages):
                text += f"\n--- 第{i+1}页 ---\n"
                text += page.extract_text() or ""
            return text
        
        else:
            return "❌ 未安装PDF解析库，请安装: pip install pdfplumber"
            
    except Exception as e:
        return f"❌ PDF解析失败: {e}"

def split_text(text: str, max_length: int = 3500) -> list:
    """将长文本分割成多个部分"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current = ""
    lines = text.split('\n')
    
    for line in lines:
        if len(current) + len(line) + 1 > max_length:
            if current:
                parts.append(current)
            current = line
        else:
            current += '\n' + line if current else line
    
    if current:
        parts.append(current)
    
    return parts

print("="*80)
print("📄 知识星球PDF获取与解析")
print("="*80)
print(f"📝 文件: 周度思考 2026.3.22.pdf")
print(f"📎 file_id: {FILE_ID}")
print(f"💬 topic_id: {TOPIC_ID}")
print()

# 获取下载链接
download_url = get_file_download_url(FILE_ID)

if download_url:
    print(f"✅ 获取到下载链接!")
    print(f"🔗 URL: {download_url[:100]}...")
    print()
    
    # 下载并解析
    pdf_text = download_and_parse_pdf(download_url)
    
    if pdf_text and not pdf_text.startswith("❌"):
        print("\n" + "="*80)
        print("📖 PDF全文内容")
        print("="*80)
        
        # 清理文本
        pdf_text = re.sub(r'\n+', '\n', pdf_text)  # 合并多余换行
        pdf_text = pdf_text.strip()
        
        # 分批输出
        parts = split_text(pdf_text, 3500)
        
        print(f"\n📊 总长度: {len(pdf_text)} 字符")
        print(f"📑 分批数: {len(parts)} 批\n")
        
        for i, part in enumerate(parts):
            print(f"\n{'='*80}")
            print(f"📄 第 {i+1}/{len(parts)} 批")
            print(f"{'='*80}")
            print(part)
        
        print(f"\n{'='*80}")
        print("✅ PDF内容输出完成")
        print(f"{'='*80}")
        
    else:
        print(pdf_text)
else:
    print("❌ 无法获取下载链接")
    print("\n尝试备用方案: 直接从topic获取file信息...")
    
    # 尝试从topic详情获取
    try:
        url = f"{BASE_URL}/topics/{TOPIC_ID}"
        response = requests.get(url, headers=headers, timeout=30)
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print(f"❌ 获取topic详情失败: {e}")
