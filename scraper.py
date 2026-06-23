import re
import urllib.parse
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}

def clean_linkedin_url_to_company_name(url):
    """
    Extracts company handle or name from a LinkedIn company URL.
    e.g., https://www.linkedin.com/company/ecloudvalley-digital-tech/ -> ecloudvalley-digital-tech
    """
    url = url.rstrip('/')
    match = re.search(r'/company/([^/?#]+)', url)
    if match:
        handle = match.group(1)
        # Replace hyphens with spaces to make it a search keyword
        return handle.replace('-', ' ')
    return None

def fetch_linkedin_jobs_via_guest_api(company_name):
    """
    Scrapes job listings from LinkedIn's public guest job search endpoint.
    No login required.
    """
    query = urllib.parse.quote(company_name)
    # Add f_TPR=r604800 to restrict LinkedIn results to the past week
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={query}&f_TPR=r604800&start=0"
    
    logger.info(f"Fetching LinkedIn guest jobs for: {company_name} from {url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch LinkedIn jobs. Status: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        job_cards = soup.find_all("li")
        
        jobs = []
        for card in job_cards:
            title_tag = card.find("h3", class_="base-search-card__title")
            link_tag = card.find("a", class_="base-search-card__full-link")
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            location_tag = card.find("span", class_="job-search-card__location")
            time_tag = card.find("time")
            
            if title_tag and link_tag:
                title = title_tag.get_text(strip=True)
                link = link_tag.get("href", "").split("?")[0]  # Clean tracking parameters
                company = company_tag.get_text(strip=True) if company_tag else company_name
                location = location_tag.get_text(strip=True) if location_tag else ""
                
                # Parse date text
                post_date = time_tag.get_text(strip=True) if time_tag else ""
                
                # Check if it fits the 5 days requirement
                if is_within_5_days(post_date):
                    jobs.append({
                        "title": title,
                        "link": link,
                        "company": company,
                        "location": location,
                        "post_date": post_date,
                        "source": "LinkedIn Public Search"
                    })
        logger.info(f"Found and filtered {len(jobs)} recent jobs for {company_name} on LinkedIn.")
        return jobs
    except Exception as e:
        logger.error(f"Error scraping LinkedIn guest API for {company_name}: {e}")
        return []

def is_within_5_days(date_str):
    """Checks if a relative date string fits maximum of 5 days ago."""
    if not date_str:
        return True # Default to True if no date is specified
        
    date_str = date_str.lower().strip()
    if any(unit in date_str for unit in ["hour", "minute", "second", "now", "today", "yesterday"]):
        return True
        
    import re
    match = re.search(r'(\d+)\s+day', date_str)
    if match:
        days = int(match.group(1))
        return days <= 5
        
    if any(unit in date_str for unit in ["week", "month", "year"]):
        return False
        
    return True

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
            # Resolve relative URLs
            full_href = urllib.parse.urljoin(url, href)
            if text and len(href) > 1 and not href.startswith("javascript:") and not href.startswith("mailto:"):
                links.append({"text": text, "url": full_href})
                
        # Get page plain text
        text_content = soup.get_text(separator=" ", strip=True)
        # Normalize whitespace
        text_content = re.sub(r'\s+', ' ', text_content)[:10000] # Cap text to avoid massive inputs
        
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
        # Resolve company search term
        search_term = clean_linkedin_url_to_company_name(url) or company_name
        jobs = fetch_linkedin_jobs_via_guest_api(search_term)
        if jobs:
            return {"type": "jobs_list", "data": jobs}
        
        # Try search term without cleaning if handle extraction fails
        if search_term != company_name:
            jobs = fetch_linkedin_jobs_via_guest_api(company_name)
            if jobs:
                return {"type": "jobs_list", "data": jobs}
        
        return {"type": "jobs_list", "data": []}
    else:
        # Standard career portal scraping
        content = fetch_careers_page_jobs(url)
        if content:
            return {"type": "raw_page", "data": content}
        return {"type": "jobs_list", "data": []}
