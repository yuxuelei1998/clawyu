import os
import re
import urllib.parse
import urllib.request
import json
import ssl
from bs4 import BeautifulSoup
from typing import Optional

# We use sync playwright to keep the tool simple. 
# Long running tools will be handled by the async task manager in Phase 2.
def read_web_page(url: str) -> str:
    """
    Opens a URL in a headless browser, waits for it to load, and extracts the main text content.
    Use this to read articles, documentation, or any webpage.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Error: Playwright is not installed. Please run 'pip install playwright' and 'playwright install chromium'."

    print(f"[Browser] Navigating to {url}...")
    try:
        with sync_playwright() as p:
            # We use chromium as it's the most reliable
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Navigate and wait for network to be idle to ensure JS renders
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Simple scrolling to trigger lazy loading if any
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
            
            html_content = page.content()
            browser.close()
            
            # Parse HTML and extract text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "noscript", "iframe", "svg"]):
                script.extract()
                
            # Get text
            text = soup.get_text(separator='\n')
            
            # Clean up empty lines
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Limit returned text to avoid context window explosion
            max_chars = 15000
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n\n[Content truncated. Showing first {max_chars} characters.]"
                
            return f"--- Content of {url} ---\n\n{text}"
            
    except Exception as e:
        return f"Error reading web page {url}: {str(e)}"

def search_web(query: str) -> str:
    """
    Searches the web using DuckDuckGo HTML search and returns top result snippets and URLs.
    Use this to find information online. Pass the URLs to read_web_page to read the full content.
    """
    print(f"[Browser] Searching web (Bing) for: {query}...")
    try:
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(
            url, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'zh-CN,zh;q=0.9'
            }
        )
        
        # Build proxy handler if environment variables are set
        proxies = {}
        if os.environ.get("HTTP_PROXY"):
            proxies["http"] = os.environ.get("HTTP_PROXY")
        if os.environ.get("HTTPS_PROXY"):
            proxies["https"] = os.environ.get("HTTPS_PROXY")
            
        proxy_support = urllib.request.ProxyHandler(proxies)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = urllib.request.build_opener(proxy_support, urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
            
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        for li in soup.find_all('li', class_='b_algo', limit=6):
            h2 = li.find('h2')
            if not h2 or not h2.find('a'):
                continue
                
            a = h2.find('a')
            title = a.text.strip()
            href = a.get('href')
            
            caption_div = li.find('div', class_='b_caption')
            snippet_p = caption_div.find('p') if caption_div else li.find('p')
            snippet = snippet_p.text.strip() if snippet_p else "No description available."
            
            results.append(f"Title: {title}\nURL: {href}\nSnippet: {snippet}\n")
            
        if not results:
            return f"No results found for query: {query}"
            
        return "Search Results:\n\n" + "\n---\n".join(results)
        
    except Exception as e:
        return f"获取搜索结果失败 (Error searching the web): {str(e)}。由于网络原因，该请求可能触发了超时。"
