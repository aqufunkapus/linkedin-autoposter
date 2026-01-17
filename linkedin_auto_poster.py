#!/usr/bin/env python3
"""
LinkedIn Auto-Poster - Full Automation
Monitors Squarespace RSS, generates LinkedIn posts with Claude AI,
and automatically posts to LinkedIn with intelligent variant selection.
"""

import feedparser
import requests
import json
import os
import time
from datetime import datetime
from pathlib import Path
import hashlib

# Configuration - Set these as environment variables in Railway
SQUARESPACE_RSS_URL = os.getenv("SQUARESPACE_RSS_URL", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

# Tracking
POSTED_CACHE_FILE = Path("posted_articles.json")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# LinkedIn posting via browser automation
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
    print("⚠️  Selenium not installed - LinkedIn posting disabled")


def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    
    # Write to log file
    log_file = LOG_DIR / f"autopost_{datetime.now().strftime('%Y%m%d')}.log"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message + "\n")


def get_article_hash(url):
    """Generate unique hash for article URL"""
    return hashlib.md5(url.encode()).hexdigest()


def load_posted_articles():
    """Load list of already posted articles"""
    if POSTED_CACHE_FILE.exists():
        with open(POSTED_CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_posted_article(url, post_info):
    """Save posted article to cache"""
    posted = load_posted_articles()
    article_hash = get_article_hash(url)
    posted[article_hash] = {
        'url': url,
        'posted_at': datetime.now().isoformat(),
        'title': post_info.get('title', ''),
        'variant_used': post_info.get('variant_used', '')
    }
    with open(POSTED_CACHE_FILE, 'w') as f:
        json.dump(posted, f, indent=2)


def is_already_posted(url):
    """Check if article was already posted"""
    posted = load_posted_articles()
    article_hash = get_article_hash(url)
    return article_hash in posted


def fetch_latest_blog_post(rss_url):
    """Fetch the latest unposted blog post from RSS feed"""
    try:
        log("📡 Fetching RSS feed...")
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            log("⚠️  No posts found in RSS feed")
            return None
        
        # Check each post until we find one that hasn't been posted
        for entry in feed.entries:
            url = entry.get('link', '')
            if not is_already_posted(url):
                post_data = {
                    'title': entry.get('title', 'Untitled'),
                    'link': url,
                    'published': entry.get('published', ''),
                    'summary': entry.get('summary', ''),
                    'content': entry.get('content', [{}])[0].get('value', entry.get('summary', ''))
                }
                log(f"✅ Found new post: {post_data['title']}")
                return post_data
        
        log("ℹ️  No new posts to share (all already posted)")
        return None
        
    except Exception as e:
        log(f"❌ Error fetching RSS feed: {e}")
        return None


def clean_html(html_content):
    """Strip HTML tags from content"""
    from html.parser import HTMLParser
    
    class HTMLStripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.reset()
            self.strict = False
            self.convert_charrefs = True
            self.text = []
            
        def handle_data(self, data):
            self.text.append(data)
            
        def get_text(self):
            return ''.join(self.text)
    
    stripper = HTMLStripper()
    stripper.feed(html_content)
    return ' '.join(stripper.get_text().split())


def generate_linkedin_variants(blog_post):
    """Generate 3 LinkedIn caption variants using Claude API"""
    
    clean_content = clean_html(blog_post['content'])
    
    prompt = f"""You are an expert LinkedIn content strategist for Steven, an Education Director with 25+ years in special education leadership, recently completed Ed.D., and building a Human-First AI Leadership platform.

Generate 3 distinct LinkedIn caption variations for this blog post. Each should be engagement-optimized but authentic to Steven's voice.

**OPTIMIZATION FRAMEWORK:**

1. **Personal Story Hook** - Lead with Steven's experience
2. **Question Pattern Interrupt** - Start with provocative question  
3. **Contrarian/Stat Hook** - Challenge common assumption

**REQUIREMENTS:**
- Hook that stops the scroll
- Mini-insight that provides value
- Natural flow (not salesy)
- 3-5 strategic hashtags
- NO link in caption (will be added in comments)

**STEVEN'S VOICE:**
- Thoughtful, authentic educator
- Challenges conventional wisdom
- Purpose-driven leadership focus
- Integrates AI + human dignity

**OUTPUT FORMAT (CRITICAL):**
Return ONLY valid JSON with no markdown, no preamble, no explanation:

{{
  "variants": [
    {{
      "type": "personal_story",
      "caption": "full caption text here",
      "hashtags": ["tag1", "tag2", "tag3"],
      "engagement_score": 85,
      "why_it_works": "brief explanation"
    }},
    {{
      "type": "question_interrupt", 
      "caption": "full caption text here",
      "hashtags": ["tag1", "tag2", "tag3"],
      "engagement_score": 90,
      "why_it_works": "brief explanation"
    }},
    {{
      "type": "contrarian_hook",
      "caption": "full caption text here", 
      "hashtags": ["tag1", "tag2", "tag3"],
      "engagement_score": 88,
      "why_it_works": "brief explanation"
    }}
  ]
}}

---

**BLOG POST:**

Title: {blog_post['title']}
Content: {clean_content[:3000]}
URL: {blog_post['link']}

---

Return ONLY the JSON object, nothing else:"""

    try:
        log("🤖 Generating LinkedIn variants with Claude AI...")
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 2500,
                'messages': [{
                    'role': 'user',
                    'content': prompt
                }]
            },
            timeout=60
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Extract text and parse JSON
        generated_text = result['content'][0]['text']
        
        # Clean up any markdown formatting
        generated_text = generated_text.replace('```json', '').replace('```', '').strip()
        
        # Parse JSON
        variants_data = json.loads(generated_text)
        
        log(f"✅ Generated {len(variants_data['variants'])} variants")
        
        return variants_data['variants']
        
    except json.JSONDecodeError as e:
        log(f"❌ Error parsing JSON from Claude: {e}")
        log(f"Response text: {generated_text[:200]}")
        return None
    except Exception as e:
        log(f"❌ Error calling Claude API: {e}")
        return None


def select_best_variant(variants):
    """Use AI to select the best variant based on engagement scores"""
    if not variants:
        return None
    
    # Sort by engagement score (highest first)
    sorted_variants = sorted(variants, key=lambda x: x.get('engagement_score', 0), reverse=True)
    
    best = sorted_variants[0]
    log(f"🎯 Selected best variant: {best['type']} (score: {best['engagement_score']})")
    log(f"   Why: {best['why_it_works']}")
    
    return best


def post_to_linkedin(caption, hashtags, blog_url):
    """Post to LinkedIn using browser automation"""
    
    if not SELENIUM_AVAILABLE:
        log("❌ Selenium not available - cannot post to LinkedIn")
        return False
    
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        log("❌ LinkedIn credentials not configured")
        return False
    
    try:
        log("🚀 Starting LinkedIn posting process...")
        
        # Setup Chrome options for headless mode (works on cloud servers)
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        
        try:
            # 1. Login to LinkedIn
            log("   🔐 Logging into LinkedIn...")
            driver.get('https://www.linkedin.com/login')
            time.sleep(2)
            
            # Enter credentials
            email_field = driver.find_element(By.ID, 'username')
            password_field = driver.find_element(By.ID, 'password')
            
            email_field.send_keys(LINKEDIN_EMAIL)
            password_field.send_keys(LINKEDIN_PASSWORD)
            
            # Click login
            login_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            login_button.click()
            time.sleep(5)
            
            # Check if login successful
            if 'feed' not in driver.current_url and 'checkpoint' not in driver.current_url:
                log("❌ Login may have failed - unexpected URL")
                return False
            
            log("   ✅ Logged in successfully")
            
            # 2. Navigate to post creation
            log("   📝 Creating post...")
            driver.get('https://www.linkedin.com/feed/')
            time.sleep(3)
            
            # Click "Start a post" button
            start_post = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label*="Start a post"]'))
            )
            start_post.click()
            time.sleep(2)
            
            # 3. Write the post
            log("   ✍️  Writing caption...")
            
            # Combine caption and hashtags
            full_caption = f"{caption}\n\n{' '.join(['#' + tag for tag in hashtags])}"
            
            # Find the post textarea
            post_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[contenteditable="true"]'))
            )
            post_box.send_keys(full_caption)
            time.sleep(2)
            
            # 4. Post it
            log("   🚀 Publishing post...")
            post_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Post"]')
            post_button.click()
            time.sleep(5)
            
            log("   ✅ Main post published!")
            
            # 5. Add comment with link
            log("   💬 Adding comment with blog link...")
            time.sleep(3)
            
            # Find the comment box on the newly created post
            comment_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-placeholder*="comment"]'))
            )
            comment_box.click()
            time.sleep(1)
            comment_box.send_keys(f"Read the full post: {blog_url}")
            
            # Submit comment
            comment_button = driver.find_element(By.CSS_SELECTOR, 'button[data-control-name*="comment"]')
            comment_button.click()
            time.sleep(3)
            
            log("   ✅ Comment with link posted!")
            log("🎉 SUCCESSFULLY POSTED TO LINKEDIN!")
            
            return True
            
        finally:
            driver.quit()
            
    except Exception as e:
        log(f"❌ Error posting to LinkedIn: {e}")
        return False


def main():
    """Main automation loop"""
    
    log("=" * 80)
    log("LINKEDIN AUTO-POSTER - Starting")
    log("=" * 80)
    
    # Validate configuration
    if not SQUARESPACE_RSS_URL:
        log("❌ SQUARESPACE_RSS_URL not configured")
        return
    
    if not ANTHROPIC_API_KEY:
        log("❌ ANTHROPIC_API_KEY not configured")
        return
    
    # Step 1: Check for new blog post
    log("\n📡 Step 1: Checking for new blog posts...")
    blog_post = fetch_latest_blog_post(SQUARESPACE_RSS_URL)
    
    if not blog_post:
        log("✅ No action needed - will check again on next run")
        return
    
    # Step 2: Generate LinkedIn variants
    log("\n🤖 Step 2: Generating optimized LinkedIn captions...")
    variants = generate_linkedin_variants(blog_post)
    
    if not variants:
        log("❌ Failed to generate variants")
        return
    
    # Step 3: Select best variant
    log("\n🎯 Step 3: Selecting best variant with AI...")
    best_variant = select_best_variant(variants)
    
    if not best_variant:
        log("❌ Failed to select variant")
        return
    
    # Step 4: Post to LinkedIn
    log("\n📤 Step 4: Posting to LinkedIn...")
    success = post_to_linkedin(
        caption=best_variant['caption'],
        hashtags=best_variant['hashtags'],
        blog_url=blog_post['link']
    )
    
    if success:
        # Step 5: Save to posted cache
        save_posted_article(blog_post['link'], {
            'title': blog_post['title'],
            'variant_used': best_variant['type']
        })
        
        log("\n" + "=" * 80)
        log("✨ AUTOMATION COMPLETE - POST LIVE ON LINKEDIN!")
        log("=" * 80)
        log(f"Blog: {blog_post['title']}")
        log(f"Variant: {best_variant['type']}")
        log(f"Score: {best_variant['engagement_score']}")
        log("=" * 80)
    else:
        log("\n❌ Posting failed - will retry on next run")


if __name__ == "__main__":
    main()
