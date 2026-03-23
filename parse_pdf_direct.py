#!/root/.openclaw/workspace/venv/bin/python3
"""
直接下载PDF并解析内容
"""

import requests
import re
from io import BytesIO

# 从第一次成功获取的下载链接
DOWNLOAD_URL = "https://files.zsxq.com/lsitHMtY87Pz1UnKTR7eKozsuJSI?attname=%E5%91%A8%E5%BA%A6%E6%80%9D%E8%80%83%202026.3.22.pdf"

# Cookie
COOKIE = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%84%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU0NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22NDIxODgyNTQ0NTgxODg4%22%7D%2C%22%24device_id%22%3A%221OTk1NzI5OGM4MzkwMyJ9; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

print("="*80)
print("📄 周度思考 2026.3.22.pdf")
print("="*80)
print()

try:
    print("📥 下载PDF中...")
    response = requests.get(DOWNLOAD_URL, headers=headers, timeout=60)
    response.raise_for_status()
    print(f"✅ 下载成功! 大小: {len(response.content)/1024/1024:.2f} MB\n")
    
    pdf_bytes = BytesIO(response.content)
    
    # 使用pdfplumber解析
    import pdfplumber
    
    print("📖 解析PDF内容...\n")
    text = ""
    
    with pdfplumber.open(pdf_bytes) as pdf:
        total_pages = len(pdf.pages)
        print(f"📊 总页数: {total_pages}\n")
        
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n{'='*60}\n"
                text += f"📄 第 {i+1} 页 / 共 {total_pages} 页\n"
                text += f"{'='*60}\n"
                text += page_text + "\n"
    
    # 清理文本
    text = re.sub(r'\n{3,}', '\n\n', text)  # 合并多余空行
    
    # 分批输出 (每批约3500字符)
    max_batch = 3500
    if len(text) <= max_batch:
        print(text)
    else:
        # 按段落分割
        paragraphs = text.split('\n\n')
        batches = []
        current = ""
        
        for p in paragraphs:
            if len(current) + len(p) + 2 > max_batch:
                if current:
                    batches.append(current)
                current = p
            else:
                current = current + '\n\n' + p if current else p
        
        if current:
            batches.append(current)
        
        print(f"📑 内容将分 {len(batches)} 批发送\n")
        print(f"{'='*80}")
        print("📖 PDF全文内容 - 第 1 批")
        print(f"{'='*80}\n")
        print(batches[0])
        
        # 保存剩余批次到文件，然后发送
        for i in range(1, len(batches)):
            print(f"\n{'='*80}")
            print(f"📖 PDF全文内容 - 第 {i+1}/{len(batches)} 批")
            print(f"{'='*80}\n")
            print(batches[i])
        
        print(f"\n{'='*80}")
        print("✅ PDF内容全部输出完成")
        print(f"{'='*80}")
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
