import os
import json
import time
import random
import urllib.parse
from bs4 import BeautifulSoup
from curl_cffi import requests


DATA_DIR = "../DATA/data"

STARTING_URL = "https://novelphoenix.com/novel/shadow-slave/chapter-1"

def parse_chapter(html_content, current_url):
    soup = BeautifulSoup(html_content, "html.parser")
    
    title_element = soup.select_one("span.chapter-title")
    chapter_title = title_element.get_text(strip=True) if title_element else "Unknown Title"
    
    content_div = soup.select_one("div#content")
    paragraphs = []
    
    if content_div:
        for p in content_div.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)
                
    clean_text = "\n\n".join(paragraphs)
    word_count = len(clean_text.split())
    
    next_btn = soup.select_one("a.nextchap")
    next_url = None
    
    if next_btn and next_btn.has_attr('href'):
        raw_href = next_btn['href']
        # The site uses href="javascript:;" when there is no next chapter available
        if "javascript" not in raw_href.lower():
            next_url = urllib.parse.urljoin(current_url, raw_href)
        
    return {
        "title": chapter_title,
        "text": clean_text,
        "word_count": word_count,
        "next_url": next_url
    }

def get_resume_state():
    files = [f for f in os.listdir(DATA_DIR) if f.startswith("chapter_") and f.endswith(".json")]
    
    if not files:
        return 1, STARTING_URL
    
    files.sort()
    last_file = files[-1]
    
    last_chapter_num = int(last_file.replace("chapter_", "").replace(".json", ""))
    
    with open(os.path.join(DATA_DIR, last_file), "r", encoding="utf-8") as f:
        last_data = json.load(f)
        
    next_url_to_fetch = last_data.get("next_url")
    
    if not next_url_to_fetch:
        print(f"[!] This might be the final chapter since last chapter ({last_chapter_num}) did not contain a next URL .")
        return last_chapter_num, None
        
    print(f"[!] resuming from chapter {last_chapter_num + 1}...")
    return last_chapter_num + 1, next_url_to_fetch


print(".....STARTING THE SS SCRAPER.....")

session = requests.Session(impersonate="chrome124")
e
current_chapter_num, current_url = get_resume_state()

while current_url:
    json_path = os.path.join(DATA_DIR, f"chapter_{current_chapter_num:04d}.json")
    
    try:
        response = session.get(current_url, timeout=15)
        response.raise_for_status() # Throw an error when we get a 404 or 500


        #Parse the data
        parsed_data = parse_chapter(response.text, current_url)
        
        # Structure of the final JSON dictionary
        record = {
            "chapter_number": current_chapter_num,
            "title": parsed_data["title"],
            "url": current_url,
            "word_count": parsed_data["word_count"],
            "text": parsed_data["text"],
            "next_url": parsed_data["next_url"]
        }
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            
        print(f"[✓] Saved Chapter {current_chapter_num:04d} | Words: {parsed_data['word_count']} | {parsed_data['title']}")
        
        current_url = parsed_data["next_url"]
        current_chapter_num += 1
        
        time.sleep(random.uniform(1.2, 2.5))
        
    except Exception as e:
        print(f"[!] Error parsing Chapter {current_chapter_num} ({current_url}): {e}")
        print("[!] Sleeping for 10 seconds before retrying...")
        time.sleep(10)
        
print("\n Scraping completed.")
