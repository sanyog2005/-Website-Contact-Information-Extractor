import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

app = FastAPI(title="Web Contact Extractor API")

# Standard email extraction
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Strict Phone Regex: Requires at least one formatting character (+, -, space, ()) 
# to avoid grabbing pure integer tracking IDs like Facebook Pixels
# Highly tolerant regex: Ignores extra spaces injected by HTML spans while maintaining strict digit counts
PHONE_REGEX = r'(?<!\d)(?:(?:\(?\+?91\)?[\s\-]*)?(?:\(?0\)?[\s\-]*)?[6-9](?:[\s\-]*\d){9}|(?:\(?\+?91\)?[\s\-]*|\(?0\)?[\s\-]*)[1-8](?:[\s\-]*\d){9}|1800(?:[\s\-]*\d){6,7})(?!\d)'class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 10  
    delay: float = 1.0

def extract_contact_info(text):
    """Extracts unique emails and phone numbers from raw text."""
    emails = set(re.findall(EMAIL_REGEX, text))
    phones = set(re.findall(PHONE_REGEX, text))
    return emails, phones

def is_valid_url(url, base_domain):
    """Ensures the URL belongs to the same domain and is HTTP/HTTPS."""
    parsed = urlparse(url)
    return parsed.netloc == base_domain and parsed.scheme in ['http', 'https']

@app.post("/api/crawl")
def crawl_endpoint(request: CrawlRequest):
    start_url = request.url
    base_domain = urlparse(start_url).netloc
    
    if not base_domain:
        raise HTTPException(status_code=400, detail="Invalid URL provided.")
        
    visited = set()
    to_visit = {start_url}
    all_emails = set()
    all_phones = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            while to_visit and len(visited) < request.max_pages:
                current_url = to_visit.pop().split('#')[0]
                
                if current_url in visited:
                    continue
                    
                visited.add(current_url)
                text_content = ""
                soup = None

                # 1. Attempt lightweight fetch with Requests + BeautifulSoup
                try:
                    response = requests.get(current_url, headers=headers, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # --- CLEAN THE DOM: Destroy hidden scripts, styles, and meta tags ---
                    for element in soup(["script", "style", "noscript", "meta"]):
                        element.decompose()
                        
                    text_content = soup.get_text(separator=' ', strip=True)
                    
                    # SPA Heuristic
                    if len(text_content) < 300 or "You need to enable JavaScript" in response.text:
                        raise ValueError("SPA Detection")
                        
                except Exception:
                    # 2. Fallback to Playwright for dynamic rendering
                    try:
                        page.goto(current_url, timeout=15000, wait_until='networkidle')
                        html = page.content()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # --- CLEAN THE DOM AGAIN for dynamic content ---
                        for element in soup(["script", "style", "noscript", "meta"]):
                            element.decompose()
                            
                        text_content = soup.get_text(separator=' ', strip=True)
                    except Exception:
                        continue 

                # Extract data from the cleaned text
                emails, phones = extract_contact_info(text_content)
                all_emails.update(emails)
                all_phones.update(phones)

                # Find all internal links to continue crawling
                if soup:
                    for a_tag in soup.find_all('a', href=True):
                        link = a_tag['href']
                        full_url = urljoin(current_url, link)
                        if is_valid_url(full_url, base_domain) and full_url not in visited:
                            to_visit.add(full_url)

                time.sleep(request.delay)

            browser.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crawling error: {str(e)}")

    return {
        "target_url": start_url,
        "pages_crawled": len(visited),
        "emails": list(all_emails),
        "phones": list(all_phones)
    }