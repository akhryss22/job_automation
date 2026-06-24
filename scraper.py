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

# Keywords used for the broad LinkedIn search (Non-Hiring Partners tab)
BROAD_SEARCH_KEYWORDS = [
    "cloud engineer Philippines",
    "AWS junior Philippines",
    "IT support Philippines",
    "cloud support associate Philippines",
    "junior sysadmin Philippines",
    "DevOps associate Philippines",
    "technical support Philippines",
    "cloud administrator Philippines",
]


def extract_linkedin_handle(url):
    """Extracts the company handle from a LinkedIn company URL."""
    url = url.rstrip('/')
    match = re.search(r'/company/([^/?#]+)', url)
    if match:
        return match.group(1)
    return None


def is_within_5_days(date_str_or_datetime):
    """
    Checks if a relative date string OR ISO datetime fits within 5 days ago.
    """
    if not date_str_or_datetime:
        return True

    s = str(date_str_or_datetime).lower().strip()

    try:
        iso_str = re.sub(r'[Zz]$', '', s)
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=5)
        return dt >= cutoff
    except Exception:
        pass

    if any(unit in s for unit in ["hour", "minute", "second", "now", "today", "yesterday", "just now"]):
        return True

    match = re.search(r'(\d+)\s+day', s)
    if match:
        return int(match.group(1)) <= 5

    if any(unit in s for unit in ["week", "month", "year"]):
        return False

    return True


def fetch_linkedin_company_jobs(handle, company_name):
    """
    Scrapes the public LinkedIn company jobs page using the company handle.
    """
    url = f"https://www.linkedin.com/company/{handle}/jobs/"
    logger.info(f"Fetching LinkedIn company jobs for {company_name}: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 999:
            logger.warning(f"LinkedIn blocked request for {company_name} (status 999).")
            return []
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}. Status: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []
        seen = set()

        for a in soup.find_all("a", href=lambda x: x and "/jobs/view/" in x):
            href = a.get("href", "")
            clean_link = href.split("?")[0]
            if clean_link in seen:
                continue
            seen.add(clean_link)

            title = a.get_text(strip=True)
            if not title:
                parent = a.find_parent()
                if parent:
                    h = parent.find(["h3", "h4", "span"])
                    title = h.get_text(strip=True) if h else ""

            parent_li = a.find_parent("li")
            time_tag = parent_li.find("time") if parent_li else None
            date_text = time_tag.get_text(strip=True) if time_tag else ""
            datetime_attr = time_tag.get("datetime", "") if time_tag else ""

            if title and is_within_5_days(datetime_attr or date_text):
                jobs.append({
                    "title": title,
                    "link": clean_link,
                    "company": company_name,
                    "post_date": date_text or datetime_attr,
                    "source": "LinkedIn Company Page"
                })

        logger.info(f"Found {len(jobs)} recent jobs (<=5 days) for {company_name}")
        return jobs

    except Exception as e:
        logger.error(f"Error scraping LinkedIn company page for {company_name}: {e}")
        return []


def search_linkedin_broad(max_results=30):
    """
    Broad LinkedIn search using multiple keywords to find jobs in Philippines
    that could suit AWS re/Start alumni. Used for the Non-Hiring Partners tab.
    Returns a combined deduplicated list of raw job listings.
    """
    logger.info("Running broad LinkedIn search for Non-Hiring Partners tab...")
    all_jobs = []
    seen_links = set()

    for keyword in BROAD_SEARCH_KEYWORDS:
        query = urllib.parse.quote(keyword)
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={query}&start=0"

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all("li")

            for card in cards:
                title_tag = card.find("h3", class_="base-search-card__title")
                link_tag = card.find("a", class_="base-search-card__full-link")
                company_tag = card.find("h4", class_="base-search-card__subtitle")
                time_tag = card.find("time")

                if not (title_tag and link_tag):
                    continue

                clean_link = link_tag.get("href", "").split("?")[0]
                if clean_link in seen_links:
                    continue
                seen_links.add(clean_link)

                date_attr = time_tag.get("datetime", "") if time_tag else ""
                date_text = time_tag.get_text(strip=True) if time_tag else ""

                if is_within_5_days(date_attr or date_text):
                    all_jobs.append({
                        "title": title_tag.get_text(strip=True),
                        "link": clean_link,
                        "company": company_tag.get_text(strip=True) if company_tag else "",
                        "post_date": date_text,
                        "source": "LinkedIn Broad Search"
                    })

            if len(all_jobs) >= max_results:
                break

        except Exception as e:
            logger.error(f"Error during broad LinkedIn search for '{keyword}': {e}")
            continue

    logger.info(f"Broad search collected {len(all_jobs)} unique raw jobs to evaluate.")
    return all_jobs[:max_results]


def fetch_careers_page_jobs(url):
    """
    Fetches raw text and links from standard company careers websites.
    """
    logger.info(f"Fetching careers page content: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch {url}. Status: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            full_href = urllib.parse.urljoin(url, href)
            if text and len(href) > 1 and not href.startswith("javascript:") and not href.startswith("mailto:"):
                links.append({"text": text, "url": full_href})

        text_content = soup.get_text(separator=" ", strip=True)
        text_content = re.sub(r'\s+', ' ', text_content)[:10000]

        return {"text": text_content, "links": links}
    except Exception as e:
        logger.error(f"Error fetching careers page {url}: {e}")
        return None


def get_jobs_for_company(company_name, url):
    """
    Decides the scrape strategy based on URL type.
    If url is None/empty, uses the company jobs page via handle guess.
    """
    if not url:
        # Try to guess LinkedIn handle from company name
        slug = re.sub(r'[^a-z0-9]+', '-', company_name.lower()).strip('-')
        jobs = fetch_linkedin_company_jobs(slug, company_name)
        return {"type": "jobs_list", "data": jobs}

    if "linkedin.com" in url:
        handle = extract_linkedin_handle(url)
        if handle:
            jobs = fetch_linkedin_company_jobs(handle, company_name)
            return {"type": "jobs_list", "data": jobs}
        logger.warning(f"Could not extract LinkedIn handle from: {url}")
        return {"type": "jobs_list", "data": []}

    content = fetch_careers_page_jobs(url)
    if content:
        return {"type": "raw_page", "data": content}
    return {"type": "jobs_list", "data": []}
