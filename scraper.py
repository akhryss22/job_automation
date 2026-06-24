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

# Philippines LinkedIn geoId
PH_GEO_ID = "103121230"
METRO_MANILA_GEO_ID = "105246114"

# Curated list of known PH-based IT companies, cloud employers, and tech recruiters.
# These are scraped for the Non-Hiring Partners tab since LinkedIn keyword search
# is blocked. Add or remove handles here to customize.
# Format: (display_name, linkedin_handle)
PH_IT_COMPANIES = [
    # ── Tech Recruiters ──────────────────────────────────
    ("Monroe Consulting",       "monroe-consulting-group"),
    ("Hunters Hub",             "hunters-hub"),
    ("Manpower Philippines",    "manpower-group"),
    ("Adecco",                  "adecco"),
    ("Sprout Solutions",        "sprout-solutions"),
    ("JobsDB Philippines",      "jobsdb"),
    # ── Telcos & IT Giants ───────────────────────────────
    ("Globe Telecom",           "globe-telecom"),
    ("PLDT",                    "pldt"),
    ("Converge ICT",            "converge-ict-solutions-inc"),
    ("DITO Telecommunity",      "dito-telecommunity"),
    # ── IT Services / Outsourcing ────────────────────────
    ("Accenture Philippines",   "accenture"),
    ("IBM",                     "ibm"),
    ("DXC Technology",          "dxctechnology"),
    ("Wipro",                   "wipro"),
    ("Concentrix",              "concentrix"),
    ("Stefanini",               "stefanini"),
    ("MicroSourcing",           "microsourcing"),
    # ── Cloud / AWS Partners ─────────────────────────────
    ("Ingram Micro",            "ingram-micro"),
    ("TD SYNNEX",               "td-synnex"),
    ("Fujitsu",                 "fujitsu"),
    ("NTT DATA",                "ntt-data"),
    ("Logicalis",               "logicalis"),
    ("Exist Software Labs",     "exist-software-labs"),
    ("Cloudstaff",              "cloudstaff"),
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



def search_linkedin_broad(max_results=50):
    """
    Scrapes a curated list of known PH IT companies and tech recruiters
    from their LinkedIn company jobs pages.
    """
    logger.info(f"LinkedIn: Scanning {len(PH_IT_COMPANIES)} curated PH IT companies...")
    all_jobs = []
    seen_links = set()

    for display_name, handle in PH_IT_COMPANIES:
        if len(all_jobs) >= max_results:
            break
        try:
            jobs = fetch_linkedin_company_jobs(handle, display_name)
            for job in jobs:
                link = job.get("link", "")
                if link and link not in seen_links:
                    seen_links.add(link)
                    all_jobs.append(job)
        except Exception as e:
            logger.error(f"Error scraping {display_name}: {e}")
            continue

    logger.info(f"LinkedIn: collected {len(all_jobs)} jobs.")
    return all_jobs


# Indeed Philippines search keywords and locations
INDEED_KEYWORDS = [
    "cloud support",
    "AWS cloud",
    "IT support",
    "technical support engineer",
    "NOC engineer",
    "junior devops",
    "IT helpdesk",
    "systems administrator",
    "cloud administrator",
    "IT operations",
]
INDEED_LOCATIONS = [
    "Metro Manila",
    "Cebu City",
    "Baguio",
    "Clark Pampanga",
]


def search_indeed_ph(max_results=50):
    """
    Scrapes Indeed Philippines for recent IT/cloud job postings across PH locations.
    Uses fromage=5 to get only last 5 days of postings.
    """
    logger.info("Indeed PH: Starting broad search...")
    all_jobs = []
    seen_links = set()

    for keyword in INDEED_KEYWORDS:
        if len(all_jobs) >= max_results:
            break
        for location in INDEED_LOCATIONS:
            if len(all_jobs) >= max_results:
                break
            try:
                q = urllib.parse.quote(keyword)
                loc = urllib.parse.quote(location)
                url = f"https://ph.indeed.com/jobs?q={q}&l={loc}&sort=date&fromage=5"
                response = requests.get(url, headers=HEADERS, timeout=15)

                if response.status_code != 200:
                    logger.debug(f"Indeed blocked for '{keyword}' in {location}: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.find_all("div", attrs={"data-testid": "slider_item"})
                if not cards:
                    cards = soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c)

                found = 0
                for card in cards:
                    title_tag = card.find("h2")
                    company_tag = card.find("span", {"data-testid": "company-name"})
                    location_tag = card.find("div", {"data-testid": "text-location"})
                    link_tag = card.find("a", href=lambda h: h and "/rc/clk" in str(h))
                    if not link_tag:
                        link_tag = card.find("a", href=lambda h: h and "/pagead/clk" in str(h))

                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)

                    # Build Indeed job URL from jk param
                    raw_href = link_tag.get("href", "") if link_tag else ""
                    jk_match = re.search(r'jk=([a-f0-9]+)', raw_href)
                    if jk_match:
                        clean_link = f"https://ph.indeed.com/viewjob?jk={jk_match.group(1)}"
                    elif raw_href:
                        clean_link = "https://ph.indeed.com" + raw_href if raw_href.startswith("/") else raw_href
                    else:
                        continue

                    if clean_link in seen_links:
                        continue
                    seen_links.add(clean_link)

                    all_jobs.append({
                        "title": title,
                        "company": company_tag.get_text(strip=True) if company_tag else "",
                        "location": location_tag.get_text(strip=True) if location_tag else location,
                        "link": clean_link,
                        "source": "Indeed PH"
                    })
                    found += 1

                if found > 0:
                    logger.info(f"Indeed: '{keyword}' in {location} → {found} jobs")

            except Exception as e:
                logger.error(f"Indeed error for '{keyword}' in {location}: {e}")
                continue

    logger.info(f"Indeed PH: collected {len(all_jobs)} jobs.")
    return all_jobs


def search_broad(max_results=60):
    """
    Multi-source broad search for Non-Hiring Partners tab.
    Combines LinkedIn company pages + Indeed Philippines.
    Returns deduplicated list of raw jobs for AI to filter.
    """
    logger.info("=== Starting multi-source broad search ===")
    all_jobs = []
    seen_links = set()

    sources = [
        ("LinkedIn",  lambda: search_linkedin_broad(max_results=40)),
        ("Indeed PH", lambda: search_indeed_ph(max_results=40)),
    ]

    for source_name, fetch_fn in sources:
        try:
            jobs = fetch_fn()
            added = 0
            for job in jobs:
                link = job.get("link", "")
                if link and link not in seen_links:
                    seen_links.add(link)
                    all_jobs.append(job)
                    added += 1
            logger.info(f"{source_name}: added {added} unique jobs to pool.")
        except Exception as e:
            logger.error(f"{source_name} source failed: {e}")
            continue

    logger.info(f"Multi-source total: {len(all_jobs)} unique raw jobs collected.")
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
