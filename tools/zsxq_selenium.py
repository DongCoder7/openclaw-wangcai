#!/usr/bin/env python3
"""
知识星球Selenium版本 - 模拟浏览器登录搜索
使用Chrome浏览器模拟真实用户操作
"""
import os
import time
import json
from datetime import datetime

# Selenium导入
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("❌ Selenium未安装，请先安装: pip3 install selenium")

# 配置
GROUP_ID = "28855458518111"
ZSXQ_URL = f"https://wx.zsxq.com/group/{GROUP_ID}"

# Cookie配置（从环境变量读取，避免硬编码）
def get_cookies():
    """从环境变量获取cookie配置"""
    cookie_json = os.environ.get('ZSXQ_SELENIUM_COOKIES')
    if cookie_json:
        try:
            return json.loads(cookie_json)
        except:
            pass
    
    # 默认空配置，需要用户设置环境变量
    print("⚠️ 未找到ZSXQ_SELENIUM_COOKIES环境变量，请设置后重试")
    print("示例: export ZSXQ_SELENIUM_COOKIES='[{\"name\": \"zsxq_access_token\", \"value\": \"你的token\", \"domain\": \".zsxq.com\"}]'")
    return []

COOKIES = get_cookies()

def create_driver(headless=True):
    """创建Chrome浏览器驱动"""
    if not SELENIUM_AVAILABLE:
        return None
    
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")  # 无头模式
    
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 尝试多种方式找到chromedriver
    chromedriver_paths = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/snap/bin/chromium.chromedriver",
    ]
    
    driver = None
    for path in chromedriver_paths:
        try:
            service = Service(path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print(f"✅ 使用chromedriver: {path}")
            break
        except:
            continue
    
    if driver is None:
        # 尝试使用默认路径
        try:
            driver = webdriver.Chrome(options=chrome_options)
            print("✅ 使用默认chromedriver")
        except Exception as e:
            print(f"❌ 无法创建Chrome驱动: {e}")
            return None
    
    return driver

def login_with_cookies(driver):
    """使用cookie登录"""
    try:
        # 先访问知识星球主页
        driver.get("https://wx.zsxq.com")
        time.sleep(2)
        
        # 添加cookie
        for cookie in COOKIES:
            try:
                driver.add_cookie(cookie)
            except:
                pass
        
        print("✅ Cookie已加载")
        return True
    except Exception as e:
        print(f"❌ Cookie登录失败: {e}")
        return False

def search_topics_selenium(driver, keyword, max_wait=30):
    """使用Selenium搜索话题"""
    try:
        # 访问星球页面
        print(f"🌐 访问知识星球页面...")
        driver.get(ZSXQ_URL)
        time.sleep(3)
        
        # 等待页面加载
        wait = WebDriverWait(driver, max_wait)
        
        # 尝试点击搜索按钮
        print(f"🔍 尝试点击搜索框...")
        
        # 方法1: 通过placeholder找到搜索框
        search_input = None
        try:
            search_input = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='搜索']"))
            )
            print("✅ 找到搜索框(方法1)")
        except:
            pass
        
        # 方法2: 通过class name
        if search_input is None:
            try:
                search_input = driver.find_element(By.CLASS_NAME, "search-input")
                print("✅ 找到搜索框(方法2)")
            except:
                pass
        
        # 方法3: 通过CSS selector
        if search_input is None:
            try:
                search_input = driver.find_element(By.CSS_SELECTOR, "input[type='search']")
                print("✅ 找到搜索框(方法3)")
            except:
                pass
        
        if search_input is None:
            print("❌ 无法找到搜索框")
            # 打印当前页面源码帮助调试
            print("\n当前页面标题:", driver.title)
            print("页面URL:", driver.current_url)
            return []
        
        # 输入搜索关键词
        search_input.clear()
        search_input.send_keys(keyword)
        time.sleep(1)
        
        # 按回车键
        search_input.submit()
        print(f"⏳ 等待搜索结果...")
        time.sleep(3)
        
        # 获取搜索结果
        results = []
        
        # 尝试找到话题列表
        try:
            # 等待话题加载
            topics = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "topic-item"))
            )
            
            print(f"✅ 找到 {len(topics)} 个话题")
            
            for topic in topics[:10]:  # 取前10个
                try:
                    # 提取标题/内容
                    text_elem = topic.find_element(By.CLASS_NAME, "topic-text")
                    text = text_elem.text[:200] + "..." if len(text_elem.text) > 200 else text_elem.text
                    
                    # 提取作者
                    author_elem = topic.find_element(By.CLASS_NAME, "user-name")
                    author = author_elem.text
                    
                    # 提取时间
                    time_elem = topic.find_element(By.CLASS_NAME, "topic-time")
                    topic_time = time_elem.text
                    
                    results.append({
                        "author": author,
                        "time": topic_time,
                        "text": text
                    })
                except:
                    continue
        except Exception as e:
            print(f"⚠️ 获取话题列表失败: {e}")
            # 尝试截图保存
            try:
                driver.save_screenshot("/tmp/zsxq_search.png")
                print("📸 已保存截图: /tmp/zsxq_search.png")
            except:
                pass
        
        return results
        
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        return []

def get_latest_topics_selenium(driver, count=10):
    """使用Selenium获取最新话题"""
    try:
        print(f"🌐 访问知识星球页面...")
        driver.get(ZSXQ_URL)
        time.sleep(3)
        
        # 等待话题加载
        wait = WebDriverWait(driver, 30)
        topics = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "topic-item"))
        )
        
        print(f"✅ 找到 {len(topics)} 个话题")
        
        results = []
        for topic in topics[:count]:
            try:
                text_elem = topic.find_element(By.CLASS_NAME, "topic-text")
                text = text_elem.text[:200] + "..." if len(text_elem.text) > 200 else text_elem.text
                
                author_elem = topic.find_element(By.CLASS_NAME, "user-name")
                author = author_elem.text
                
                time_elem = topic.find_element(By.CLASS_NAME, "topic-time")
                topic_time = time_elem.text
                
                results.append({
                    "author": author,
                    "time": topic_time,
                    "text": text
                })
            except:
                continue
        
        return results
        
    except Exception as e:
        print(f"❌ 获取最新话题失败: {e}")
        return []

def main():
    """主函数"""
    import sys
    
    if not SELENIUM_AVAILABLE:
        print("""
❌ Selenium未安装

安装方法:
  pip3 install selenium --break-system-packages

同时需要安装Chrome浏览器:
  apt-get install chromium-browser chromium-chromedriver
        """)
        return
    
    if len(sys.argv) < 2:
        print("""
用法:
  python3 zsxq_selenium.py search <关键词>   - 搜索话题
  python3 zsxq_selenium.py latest [数量]     - 获取最新话题
  
示例:
  python3 zsxq_selenium.py search 半导体
  python3 zsxq_selenium.py latest 5
        """)
        return
    
    command = sys.argv[1]
    
    # 创建浏览器驱动
    print("🚀 启动Chrome浏览器...")
    driver = create_driver(headless=True)
    
    if driver is None:
        print("❌ 无法创建浏览器驱动，请检查Chrome安装")
        return
    
    try:
        # 登录
        if not login_with_cookies(driver):
            print("❌ 登录失败")
            return
        
        if command == "search":
            if len(sys.argv) < 3:
                print("❌ 请提供搜索关键词")
                return
            keyword = sys.argv[2]
            
            print(f"\n🔍 搜索 '{keyword}'...")
            results = search_topics_selenium(driver, keyword)
            
            if results:
                print(f"\n✅ 找到 {len(results)} 条相关内容\n")
                for i, r in enumerate(results, 1):
                    print(f"【{i}】{r['time']} | {r['author']}")
                    print(f"{r['text']}")
                    print("-" * 60)
            else:
                print("⚠️ 未找到相关内容")
        
        elif command == "latest":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            
            print(f"\n📥 获取最新 {count} 条话题...")
            results = get_latest_topics_selenium(driver, count)
            
            if results:
                print(f"\n✅ 获取成功\n")
                for i, r in enumerate(results, 1):
                    print(f"【{i}】{r['time']} | {r['author']}")
                    print(f"{r['text']}")
                    print("-" * 60)
            else:
                print("⚠️ 获取失败")
        
        else:
            print(f"❌ 未知命令: {command}")
    
    finally:
        # 关闭浏览器
        if driver:
            driver.quit()
            print("\n👋 浏览器已关闭")

if __name__ == "__main__":
    main()
