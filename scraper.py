import re
import urllib.parse
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}

def extract_linkedin_handle(url):
    """
    Extracts the company handle from a LinkedIn company URL.
    e.g., https://www.linkedin.com/company/ecloudvalley-digital-tech/ -> ecloudvalley-digital-tech
    """
    url = url.rstrip('/')
    match = re.search(r'/company/([^/?#]+)', url)
    if match:
        return match.group(1)
    return None

def is_within_5_days(date_str_or_datetime):
    """
    Checks if a relative date string OR a datetime string fits maximum of 5 days ago.
    Handles:
    - ISO datetime strings: "2026-06-22T12:34:56"
    - Relative strings: "2 days ago", "3 hours ago", "1 week ago"
    """
    if not date_str_or_datetime:
        return True  # Default to include if no date info

    s = str(date_str_or_datetime).lower().strip()

    # Try to parse as ISO datetime (from datetime attribute)
    try:
        # Trim timezone or trailing chars
        iso_str = re.sub(r'[Zz]$', '', s)
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=5)
        return dt >= cutoff
    except Exception:
        pass

    # Handle relative strings
    if any(unit in s for unit in ["hour", "minute", "second", "now", "today", "yesterday", "just now"]):
        return True

    match = re.search(r'(\d+)\s+day', s)
    if match:
        return int(match.group(1)) <= 5

    if any(unit in s for unit in ["week", "month", "year"]):
        return False

    return True  # Include if unparseable

def fetch_linkedin_company_jobs(handle, company_name):
    """
    Scrapes the public LinkedIn company jobs page directly using the company handle.
    No login required. Works without the broken guest API.
    """
    url = f"https://www.linkedin.com/company/{handle}/jobs/"
    logger.info(f"Fetching LinkedIn company jobs page for {company_name}: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 999:
            logger.warning(f"LinkedIn blocked request for {company_name} (status 999). Skipping.")
            return []
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}. Status: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        jobs = []
        # Look for job links directly
        job_links = soup.find_all("a", href=lambda x: x and "/jobs/view/" in x)

        seen = set()
        for a in job_links:
            href = a.get("href", "")
            # Clean tracking params
            clean_link = href.split("?")[0]
            if clean_link in seen:
                continue
            seen.add(clean_link)

            # Try to find title from this anchor or parent
            title = a.get_text(strip=True)
            if not title:
                parent = a.find_parent()
                if parent:
                    h = parent.find(["h3", "h4", "span"])
                    title = h.get_text(strip=True) if h else ""

            # Find time tag nearby
            parent_li = a.find_parent("li")
            time_tag = parent_li.find("time") if parent_li else None
            date_text = time_tag.get_text(strip=True) if time_tag else ""
            datetime_attr = time_tag.get("datetime", "") if time_tag else ""

            # Use the ISO datetime attribute for more accurate filtering
            date_for_filter = datetime_attr or date_text

            if title and is_within_5_days(date_for_filter):
                jobs.append({
                    "title": title,
                    "link": clean_link,
                    "company": company_name,
                    "post_date": date_text or datetime_attr,
                    "source": "LinkedIn Company Page"
                })

        logger.info(f"Found {len(jobs)} recent jobs (≤5 days) for {company_name} on LinkedIn company page.")
        return jobs

    except Exception as e:
        logger.error(f"Error scraping LinkedIn company page for {company_name}: {e}")
        return []

def fetch_careers_page_jobs(url):
    """
    Fetches raw text and links from standard company careers websites.
    This content is sent to Gemini for parsing, which is robust and adaptable.
    """
    logger.info(f"Fetching careers page content: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}. Status: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove noisy tags
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Extract links with context
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            full_href = urllib.parse.urljoin(url, href)
            if text and len(href) > 1 and not href.startswith("javascript:") and not href.startswith("mailto:"):
                links.append({"text": text, "url": full_href})

        # Get page plain text
        text_content = soup.get_text(separator=" ", strip=True)
        text_content = re.sub(r'\s+', ' ', text_content)[:10000]

        return {
            "text": text_content,
            "links": links
        }
    except Exception as e:
        logger.error(f"Error fetching careers page {url}: {e}")
        return None

def get_jobs_for_company(company_name, url):
    """
    Decides the scrape strategy based on URL type and returns job listings or page text.
    """
    is_linkedin = "linkedin.com" in url

    if is_linkedin:
        handle = extract_linkedin_handle(url)
        if handle:
            jobs = fetch_linkedin_company_jobs(handle, company_name)
            return {"type": "jobs_list", "data": jobs}
        else:
            logger.warning(f"Could not extract LinkedIn handle from URL: {url}. Skipping.")
            return {"type": "jobs_list", "data": []}
    else:
        content = fetch_careers_page_jobs(url)
        if content:
            return {"type": "raw_page", "data": content}
        return {"type": "jobs_list", "data": []}
