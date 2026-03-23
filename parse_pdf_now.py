#!/root/.openclaw/workspace/venv/bin/python3
"""
立即下载并解析PDF
"""

import requests
import re
from io import BytesIO

# 刚获取的下载链接
DOWNLOAD_URL = "https://files.zsxq.com/lsitHMtY87Pz1UnKTR7eKozsuJSI?attname=%E5%91%A8%E5%BA%A6%E6%80%9D%E8%80%83%202026.3.22.pdf&e=1774174853&token=kIxbL07-8jAj8w1n4s9zv64FuZZNEATmlU_Vm6zD:sJpWqBSJokpstXphWmucGztq194="
COOKIE = "sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%22421882554581888%22%2C%22first_id%22%3A%2219957298c826cb-08f4b144c21fe3-1f525631-1484784-19957298c83903%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E8%87%AA%84%E6%90%9C%E7%B4%A2%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fwww.baidu.com%2Flink%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk5NTcyOThjODI2Y2ItMDhmNGIxNDRjMjFmZTMtMWY1MjU2MzEtMTQ4NDc4NC0xOTk1NzI5OGM4MzkwMyIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjQyMTg4MjU0NDU4MTg4OCJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%22NDIxODgyNTQ0NTgxODg4%22%7D%2C%22%24device_id%22%3A%221OTk1NzI5OGM4MzkwMyJ9; abtest_env=product; zsxq_access_token=AD5BC203-E94C-4B32-9BA2-6BFD0C435426_C1F959E538CA66E8"

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

print("="*80)
print("📄 周度思考 2026.3.22.pdf")
print("👤 反诈先锋 | 知识星球 Truth and Justice")
print("="*80)
print()

try:
    # 下载PDF
    print("📥 下载中...")
    resp = requests.get(DOWNLOAD_URL, headers=headers, timeout=60)
    resp.raise_for_status()
    
    size_mb = len(resp.content) / 1024 / 1024
    print(f"✅ 下载成功! {size_mb:.2f} MB\n")
    
    # 解析PDF
    import pdfplumber
    
    pdf_bytes = BytesIO(resp.content)
    full_text = []
    
    with pdfplumber.open(pdf_bytes) as pdf:
        total = len(pdf.pages)
        print(f"📖 共 {total} 页，开始解析...\n")
        
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                full_text.append(f"{'='*60}")
                full_text.append(f"📄 第 {i+1} 页 / 共 {total} 页")
                full_text.append(f"{'='*60}")
                full_text.append(text)
                full_text.append("")
    
    content = "\n".join(full_text)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # 输出统计
    total_chars = len(content)
    print(f"📊 总字符数: {total_chars}\n")
    
    # 分批输出 (每批不超过4000字符)
    max_batch = 4000
    if total_chars <= max_batch:
        print(content)
    else:
        # 按页分批
        pages = content.split("="*60)
        batches = []
        current = []
        current_len = 0
        
        for page in pages:
            page = page.strip()
            if not page:
                continue
            
            page_content = "="*60 + "\n" + page
            page_len = len(page_content)
            
            if current_len + page_len > max_batch and current:
                batches.append("\n".join(current))
                current = [page_content]
                current_len = page_len
            else:
                current.append(page_content)
                current_len += page_len + 1
        
        if current:
            batches.append("\n".join(current))
        
        # 输出所有批次
        for i, batch in enumerate(batches):
            if i > 0:
                print(f"\n{'='*80}")
                print(f"📖 第 {i+1}/{len(batches)} 批")
                print(f"{'='*80}\n")
            else:
                print("="*80)
                print("📖 PDF全文内容 - 第 1 批")
                print("="*80)
            print(batch)
        
        print(f"\n{'='*80}")
        print(f"✅ 全部输出完成 (共 {len(batches)} 批)")
        print(f"{'='*80}")
        
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
