#!/root/.openclaw/workspace/venv/bin/python3
"""
获取知识星球PDF：实时获取下载链接并立即下载解析
"""

import requests
import json
import re
from io import BytesIO

GROUP_ID = "88512145458842"
FILE_ID = "812222181818442"
TOPIC_ID = "45811258122824288"
COOKIE = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%84%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU0NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22NDIxODgyNTQ0NTgxODg4%22%7D%2C%22%24device_id%22%3A%221OTk1NzI5OGM4MzkwMyJ9; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

BASE_URL = "https://api.zsxq.com/v2"

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

def get_file_download_url():
    """获取文件下载链接"""
    # 知识星球获取文件下载链接的API
    url = f"{BASE_URL}/files/{FILE_ID}/download_url"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("succeeded"):
            return data.get("resp_data", {}).get("download_url")
    except Exception as e:
        print(f"❌ 获取下载链接失败: {e}")
    
    return None

def download_and_parse_pdf(download_url):
    """下载并解析PDF"""
    try:
        # 下载PDF (使用相同的headers保持认证)
        download_headers = {
            "Cookie": COOKIE,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        
        print("📥 下载PDF...")
        response = requests.get(download_url, headers=download_headers, timeout=60)
        response.raise_for_status()
        
        print(f"✅ 下载成功! 大小: {len(response.content)/1024/1024:.2f} MB")
        
        # 解析PDF
        import pdfplumber
        pdf_bytes = BytesIO(response.content)
        
        full_text = ""
        with pdfplumber.open(pdf_bytes) as pdf:
            total_pages = len(pdf.pages)
            print(f"📖 解析 {total_pages} 页内容...\n")
            
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    full_text += f"\n{'='*60}\n"
                    full_text += f"📄 第 {i+1} 页 / 共 {total_pages} 页\n"
                    full_text += f"{'='*60}\n"
                    full_text += page_text + "\n"
        
        return full_text
        
    except Exception as e:
        return f"❌ 错误: {e}"

def print_in_batches(text, max_chars=3500):
    """分批打印文本"""
    # 清理
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    if len(text) <= max_chars:
        print(text)
        return
    
    # 按页分割
    pages = text.split("="*60)
    batches = []
    current = ""
    
    for page in pages:
        page = page.strip()
        if not page:
            continue
            
        # 加上分隔符
        page_content = "="*60 + "\n" + page
        
        if len(current) + len(page_content) > max_chars:
            if current:
                batches.append(current)
            current = page_content
        else:
            current += "\n" + page_content
    
    if current:
        batches.append(current)
    
    print(f"\n📑 内容共 {len(batches)} 批\n")
    
    for i, batch in enumerate(batches):
        if i > 0:
            print(f"\n{'='*80}")
            print(f"📖 第 {i+1}/{len(batches)} 批")
            print(f"{'='*80}\n")
        print(batch)

# ==================== 主程序 ====================
print("="*80)
print("📄 周度思考 2026.3.22.pdf - 知识星球")
print("="*80)
print(f"👤 作者: 反诈先锋")
print(f"📎 文件ID: {FILE_ID}")
print()

# 获取下载链接
print("🔑 获取下载链接...")
download_url = get_file_download_url()

if download_url:
    print(f"✅ 获取成功\n")
    
    # 立即下载并解析
    pdf_text = download_and_parse_pdf(download_url)
    
    if pdf_text and not pdf_text.startswith("❌"):
        print("\n" + "="*80)
        print("📖 PDF全文内容 - 第 1 批")
        print("="*80)
        print_in_batches(pdf_text)
        
        print(f"\n{'='*80}")
        print("✅ PDF解析完成")
        print(f"{'='*80}")
    else:
        print(pdf_text)
else:
    print("❌ 无法获取下载链接")
