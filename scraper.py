"""
Job scraper using Playwright for JS-rendered sites
Supports streaming callbacks — calls on_job_found immediately when a match is found.
"""
import re
import time
import random
import logging
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_sync

from config import SEARCH_KEYWORDS, LOCATION_FILTER, EXCLUDE_KEYWORDS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_email(text: str) -> str:
    match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else "Cek di halaman lowongan"


def _is_manado(location: str) -> bool:
    """Check if job location is Manado."""
    return LOCATION_FILTER.lower() in location.lower()


def _is_excluded(text: str) -> bool:
    """Check if job text contains excluded keywords (sales, etc)."""
    text_lower = text.lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def scrape_kalibrr(keyword: str, on_job_found=None) -> list:
    """Scrape Kalibrr - extract job links from search, visit detail pages.
    If on_job_found callback is provided, calls it immediately for each match."""
    jobs = []
    url = f"https://www.kalibrr.com/id-ID/home/te/job-posting?q={quote_plus(keyword)}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)

            # Extract job links
            links = page.query_selector_all('a[href*="/jobs/"]')
            job_links = []
            for link in links:
                href = link.get_attribute("href")
                if href and "/jobs/" in href and href not in job_links:
                    if not href.startswith("http"):
                        href = "https://www.kalibrr.com" + href
                    job_links.append(href)

            logger.info(f"Kalibrr: Found {len(job_links)} job links for '{keyword}'")

            # Visit each detail page (limit to 5 for speed)
            for job_url in job_links[:5]:
                try:
                    page.goto(job_url, timeout=20000, wait_until="networkidle")
                    page.wait_for_timeout(2000)

                    # Parse title: "Lowongan Kerja [Posisi] di [Perusahaan]"
                    raw_title = page.title().replace(" | Kalibrr", "").strip()
                    if " di " in raw_title:
                        parts = raw_title.split(" di ", 1)
                        position = parts[0].replace("Lowongan Kerja ", "").strip()
                        company = parts[1].strip()
                    else:
                        position = raw_title
                        company = "Unknown"

                    # Get body text for location and deadline
                    body_text = page.inner_text("body")

                    # Extract location from body text
                    location = "Indonesia"
                    for line in body_text.split("\n"):
                        line = line.strip()
                        m = re.match(r"^([A-Za-z\s]{2,30},\s*Indonesia)$", line)
                        if m:
                            location = m.group(1).strip()
                            break

                    # Extract deadline from body text
                    deadline = "Cek di halaman lowongan"
                    deadline_match = re.search(r"batas waktu lamaran adalah\s*(\d+\s+\w+)", body_text)
                    if deadline_match:
                        deadline = deadline_match.group(1)

                    # Extract email
                    email = _extract_email(body_text)

                    if _is_manado(location) and not _is_excluded(f"{position} {company}"):
                        job = {
                            "company": company,
                            "position": position,
                            "location": location,
                            "deadline": deadline,
                            "email": email,
                            "link": job_url,
                            "source": "Kalibrr",
                        }
                        jobs.append(job)
                        logger.info(f"  ✓ {company} | {position} | {location}")
                        # Stream: call callback immediately
                        if on_job_found:
                            on_job_found(job)

                    time.sleep(random.uniform(1, 2))
                except Exception as e:
                    logger.debug(f"  ✗ Failed to scrape {job_url}: {e}")
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"Kalibrr scrape failed for '{keyword}': {e}")

    return jobs


def scrape_jobstreet(keyword: str, on_job_found=None) -> list:
    """Scrape JobStreet Indonesia."""
    jobs = []
    urls = [
        f"https://www.jobstreet.co.id/en/job-search/{quote_plus(keyword)}/?location=Manado",
        f"https://id.jobstreet.com/en/job-search/{quote_plus(keyword)}/?location=Manado",
        f"https://www.jobstreet.co.id/jobs/{quote_plus(keyword)}/?location=Manado",
    ]

    for url in urls:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                stealth_sync(page)
                page.goto(url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(3000)

                title = page.title()
                if "404" in title or "Just a moment" in title:
                    browser.close()
                    continue

                job_cards = page.query_selector_all("[data-testid='job-card']")
                if not job_cards:
                    job_cards = page.query_selector_all(".job-card")
                if not job_cards:
                    job_cards = page_query_selector_all("article")
                if not job_cards:
                    job_cards = page.query_selector_all("[class*='job']")

                for card in job_cards[:10]:
                    try:
                        title_el = card.query_selector("h2, h3, [class*='title']")
                        company_el = card.query_selector("[class*='company']")
                        location_el = card.query_selector("[class*='location']")
                        link_el = card.query_selector("a[href]")

                        if title_el:
                            title = _clean(title_el.inner_text())
                            company = _clean(company_el.inner_text()) if company_el else "Unknown"
                            location = _clean(location_el.inner_text()) if location_el else "Indonesia"
                            link = link_el.get_attribute("href") if link_el else ""
                            if link and not link.startswith("http"):
                                link = "https://www.jobstreet.co.id" + link

                            if _is_manado(location) and not _is_excluded(f"{title} {company}"):
                                job = {
                                    "company": company,
                                    "position": title,
                                    "location": location,
                                    "deadline": "Cek di halaman lowongan",
                                    "email": "Cek di halaman lowongan",
                                    "link": link,
                                    "source": "JobStreet",
                                }
                                jobs.append(job)
                                if on_job_found:
                                    on_job_found(job)
                    except Exception:
                        continue

                browser.close()
                if jobs:
                    break
        except Exception as e:
            logger.warning(f"JobStreet scrape failed for '{keyword}': {e}")

    return jobs


def scrape_linkedin(keyword: str, on_job_found=None) -> list:
    """Scrape LinkedIn Jobs."""
    jobs = []
    url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(keyword)}&location=Manado"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)

            title = page.title()
            if "Sign In" in title or "Login" in title:
                logger.warning("LinkedIn requires login")
                browser.close()
                return jobs

            job_cards = page.query_selector_all(".base-card")
            if not job_cards:
                job_cards = page.query_selector_all("[class*='job']")

            for card in job_cards[:10]:
                try:
                    title_el = card.query_selector(".base-search-card__title, h3")
                    company_el = card.query_selector(".base-search-card__subtitle, [class*='company']")
                    location_el = card.query_selector(".job-search-card__location, [class*='location']")
                    link_el = card.query_selector("a[href]")

                    if title_el:
                        title = _clean(title_el.inner_text())
                        company = _clean(company_el.inner_text()) if company_el else "Unknown"
                        location = _clean(location_el.inner_text()) if location_el else "Manado"
                        link = link_el.get_attribute("href") if link_el else ""
                        if link and not link.startswith("http"):
                            link = "https://www.linkedin.com" + link

                        if _is_manado(location) and not _is_excluded(f"{title} {company}"):
                            job = {
                                "company": company,
                                "position": title,
                                "location": location,
                                "deadline": "Cek di halaman lowongan",
                                "email": "Cek di halaman lowongan",
                                "link": link,
                                "source": "LinkedIn",
                            }
                            jobs.append(job)
                            if on_job_found:
                                on_job_found(job)
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"LinkedIn scrape failed for '{keyword}': {e}")

    return jobs


def scrape_indeed(keyword: str, on_job_found=None) -> list:
    """Scrape Indeed Indonesia."""
    jobs = []
    url = f"https://id.indeed.com/cari?q={quote_plus(keyword)}&l=Manado"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)

            title = page.title()
            if "Blocked" in title:
                logger.warning("Indeed blocked the request")
                browser.close()
                return jobs

            job_cards = page.query_selector_all(".jobsearch-SerpJobCard")
            if not job_cards:
                job_cards = page.query_selector_all("[class*='job']")
            if not job_cards:
                job_cards = page.query_selector_all("article")

            for card in job_cards[:10]:
                try:
                    title_el = card.query_selector(".jobTitle, h2, h3")
                    company_el = card.query_selector(".companyName, [class*='company']")
                    location_el = card.query_selector(".location, [class*='location']")
                    link_el = card.query_selector("a[href]")

                    if title_el:
                        title = _clean(title_el.inner_text())
                        company = _clean(company_el.inner_text()) if company_el else "Unknown"
                        location = _clean(location_el.inner_text()) if location_el else "Manado"
                        link = link_el.get_attribute("href") if link_el else ""
                        if link and not link.startswith("http"):
                            link = "https://id.indeed.com" + link

                        if _is_manado(location) and not _is_excluded(f"{title} {company}"):
                            job = {
                                "company": company,
                                "position": title,
                                "location": location,
                                "deadline": "Cek di halaman lowongan",
                                "email": "Cek di halaman lowongan",
                                "link": link,
                                "source": "Indeed",
                            }
                            jobs.append(job)
                            if on_job_found:
                                on_job_found(job)
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"Indeed scrape failed for '{keyword}': {e}")

    return jobs


def scrape_google_jobs(keyword: str, on_job_found=None) -> list:
    """Scrape Google Jobs via search."""
    jobs = []
    url = f"https://www.google.com/search?q={quote_plus(keyword)}+manado+job&ibp=htl;jobs"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)

            if "sorry" in page.url or "unusual traffic" in page.content():
                logger.warning("Google blocked the request")
                browser.close()
                return jobs

            job_cards = page.query_selector_all(".gws-plugins-horizon-jobs__li-ed")
            if not job_cards:
                job_cards = page.query_selector_all("[data-ved]")
            if not job_cards:
                job_cards = page.query_selector_all("[class*='job']")

            for card in job_cards[:10]:
                try:
                    title_el = card.query_selector("[class*='title'], h3")
                    company_el = card.query_selector("[class*='company']")
                    location_el = card.query_selector("[class*='location']")
                    link_el = card.query_selector("a[href]")

                    if title_el:
                        title = _clean(title_el.inner_text())
                        company = _clean(company_el.inner_text()) if company_el else "Unknown"
                        location = _clean(location_el.inner_text()) if location_el else "Manado"
                        link = link_el.get_attribute("href") if link_el else ""

                        if _is_manado(location) and not _is_excluded(f"{title} {company}"):
                            job = {
                                "company": company,
                                "position": title,
                                "location": location,
                                "deadline": "Cek di halaman lowongan",
                                "email": "Cek di halaman lowongan",
                                "link": link,
                                "source": "Google Jobs",
                            }
                            jobs.append(job)
                            if on_job_found:
                                on_job_found(job)
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"Google Jobs scrape failed for '{keyword}': {e}")

    return jobs


def scrape_twitter_x(keyword: str, on_job_found=None) -> list:
    """Scrape Twitter/X for job postings (public tweets via search)."""
    jobs = []
    url = f"https://x.com/search?q={quote_plus(keyword)}+manado+lowongan+kerja&f=live"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)

            # Check if login required
            if "Log in" in page.title() or "login" in page.url:
                logger.warning("Twitter/X requires login")
                browser.close()
                return jobs

            # Extract tweets
            tweets = page.query_selector_all("[data-testid='tweet']")
            for tweet in tweets[:10]:
                try:
                    text_el = tweet.query_selector("[data-testid='tweetText']")
                    if text_el:
                        text = _clean(text_el.inner_text())
                        # Check if it's a job posting
                        if any(kw in text.lower() for kw in ["lowongan", "loker", "job", "hiring", "vacancy", "manado"]):
                            # Try to extract company and position
                            company = "Unknown"
                            position = text[:100]
                            location = "Manado" if "manado" in text.lower() else "Indonesia"
                            link = ""
                            link_el = tweet.query_selector("a[href*='/status/']")
                            if link_el:
                                href = link_el.get_attribute("href")
                                if href:
                                    link = f"https://x.com{href}" if not href.startswith("http") else href

                            if _is_manado(location) and not _is_excluded(f"{position} {company}"):
                                job = {
                                    "company": company,
                                    "position": position,
                                    "location": location,
                                    "deadline": "Cek di tweet",
                                    "email": "Cek di tweet",
                                    "link": link,
                                    "source": "Twitter/X",
                                }
                                jobs.append(job)
                                if on_job_found:
                                    on_job_found(job)
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"Twitter/X scrape failed for '{keyword}': {e}")

    return jobs


def scrape_facebook(keyword: str, on_job_found=None) -> list:
    """Scrape Facebook public job postings (via mbasic)."""
    jobs = []
    url = f"https://mbasic.facebook.com/search/posts/?q={quote_plus(keyword)}+manado+lowongan+kerja"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)

            # Check if login required
            if "Log In" in page.title() or "login" in page.url:
                logger.warning("Facebook requires login")
                browser.close()
                return jobs

            # Extract posts
            posts = page.query_selector_all("[data-ft='tn']")
            if not posts:
                posts = page.query_selector_all("div[role='article']")

            for post in posts[:10]:
                try:
                    text_el = post.query_selector("p, [data-ad-preview='message']")
                    if text_el:
                        text = _clean(text_el.inner_text())
                        if any(kw in text.lower() for kw in ["lowongan", "loker", "job", "hiring", "vacancy", "manado"]):
                            company = "Unknown"
                            position = text[:100]
                            location = "Manado" if "manado" in text.lower() else "Indonesia"
                            link = ""
                            link_el = post.query_selector("a[href*='facebook.com']")
                            if link_el:
                                href = link_el.get_attribute("href")
                                if href:
                                    link = href if href.startswith("http") else f"https://mbasic.facebook.com{href}"

                            if _is_manado(location) and not _is_excluded(f"{position} {company}"):
                                job = {
                                    "company": company,
                                    "position": position,
                                    "location": location,
                                    "deadline": "Cek di post",
                                    "email": "Cek di post",
                                    "link": link,
                                    "source": "Facebook",
                                }
                                jobs.append(job)
                                if on_job_found:
                                    on_job_found(job)
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"Facebook scrape failed for '{keyword}': {e}")

    return jobs


def scrape_instagram(keyword: str, on_job_found=None) -> list:
    """Scrape Instagram public posts for job postings."""
    jobs = []
    url = f"https://www.instagram.com/explore/tags/{quote_plus(keyword.replace(' ', ''))}/"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)

            # Check if login required
            if "Log in" in page.title() or "login" in page.url:
                logger.warning("Instagram requires login")
                browser.close()
                return jobs

            # Extract posts
            posts = page.query_selector_all("article")
            for post in posts[:10]:
                try:
                    text_el = post.query_selector("[role='menu'] + div, [data-testid='post-comment']")
                    if text_el:
                        text = _clean(text_el.inner_text())
                        if any(kw in text.lower() for kw in ["lowongan", "loker", "job", "hiring", "vacancy", "manado"]):
                            company = "Unknown"
                            position = text[:100]
                            location = "Manado" if "manado" in text.lower() else "Indonesia"
                            link = ""
                            link_el = post.query_selector("a[href*='/p/']")
                            if link_el:
                                href = link_el.get_attribute("href")
                                if href:
                                    link = f"https://www.instagram.com{href}" if not href.startswith("http") else href

                            if _is_manado(location) and not _is_excluded(f"{position} {company}"):
                                job = {
                                    "company": company,
                                    "position": position,
                                    "location": location,
                                    "deadline": "Cek di post",
                                    "email": "Cek di post",
                                    "link": link,
                                    "source": "Instagram",
                                }
                                jobs.append(job)
                                if on_job_found:
                                    on_job_found(job)
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"Instagram scrape failed for '{keyword}': {e}")

    return jobs


def scrape_jobfair(on_job_found=None) -> list:
    """Scrape job fair events in Manado."""
    jobs = []
    urls = [
        "https://www.google.com/search?q=job+fair+manado+2026",
        "https://www.google.com/search?q=bursa+kerja+manado+2026",
        "https://www.google.com/search?q=lowongan+kerja+manado+event+2026",
    ]

    for url in urls:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                stealth_sync(page)
                page.goto(url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(3000)

                if "sorry" in page.url or "unusual traffic" in page.content():
                    logger.warning("Google blocked job fair search")
                    browser.close()
                    continue

                # Extract search results
                results = page.query_selector_all("div.g, div[data-ved]")
                for result in results[:10]:
                    try:
                        title_el = result.query_selector("h3")
                        link_el = result.query_selector("a[href]")
                        snippet_el = result.query_selector("div[data-sncf], span.aCOpRe")

                        if title_el and link_el:
                            title = _clean(title_el.inner_text())
                            link = link_el.get_attribute("href")
                            snippet = _clean(snippet_el.inner_text()) if snippet_el else ""

                            if any(kw in (title + " " + snippet).lower() for kw in ["job fair", "bursa kerja", "lowongan", "hiring", "vacancy"]) and not _is_excluded(f"{title} {snippet}"):
                                job = {
                                    "company": "Job Fair Event",
                                    "position": title,
                                    "location": "Manado",
                                    "deadline": "Cek di link",
                                    "email": "Cek di link",
                                    "link": link,
                                    "source": "Job Fair",
                                }
                                jobs.append(job)
                                if on_job_found:
                                    on_job_found(job)
                    except Exception:
                        continue

                browser.close()
        except Exception as e:
            logger.warning(f"Job fair scrape failed: {e}")

    return jobs


def scrape_glints(keyword: str, on_job_found=None) -> list:
    """Scrape Glints Indonesia for job listings."""
    jobs = []
    url = f"https://glints.com/id/en/job-finder?keyword={quote_plus(keyword)}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            stealth_sync(page)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(3000)

            # Glints uses various selectors — try common patterns
            job_cards = page.query_selector_all("[class*='job']")
            if not job_cards:
                job_cards = page.query_selector_all("article")
            if not job_cards:
                job_cards = page.query_selector_all("[class*='card']")

            for card in job_cards[:10]:
                try:
                    title_el = card.query_selector("h2, h3, [class*='title']")
                    company_el = card.query_selector("[class*='company']")
                    location_el = card.query_selector("[class*='location']")
                    link_el = card.query_selector("a[href]")

                    if title_el:
                        title = _clean(title_el.inner_text())
                        company = _clean(company_el.inner_text()) if company_el else "Unknown"
                        location = _clean(location_el.inner_text()) if location_el else "Indonesia"
                        link = link_el.get_attribute("href") if link_el else ""
                        if link and not link.startswith("http"):
                            link = "https://glints.com" + link

                        if _is_manado(location) and not _is_excluded(f"{title} {company}"):
                            job = {
                                "company": company,
                                "position": title,
                                "location": location,
                                "deadline": "Cek di halaman lowongan",
                                "email": "Cek di halaman lowongan",
                                "link": link,
                                "source": "Glints",
                            }
                            jobs.append(job)
                            if on_job_found:
                                on_job_found(job)
                except Exception:
                    continue

            browser.close()
    except Exception as e:
        logger.warning(f"Glints scrape failed for '{keyword}': {e}")

    return jobs


def scrape_all(on_job_found=None) -> list:
    """Scrape all sources for all keywords.
    If on_job_found callback is provided, calls it immediately for each match."""
    all_jobs = []
    seen = set()

    # Job fair (no keyword needed)
    logger.info("Searching: Job Fair events")
    try:
        jobs = scrape_jobfair(on_job_found=on_job_found)
        for job in jobs:
            key = f"{job['company'].lower()}|{job['position'].lower()}"
            if key not in seen:
                seen.add(key)
                all_jobs.append(job)
    except Exception as e:
        logger.error(f"Job fair scraper error: {e}")

    for keyword in SEARCH_KEYWORDS:
        logger.info(f"Searching: {keyword}")

        # Only sources confirmed working (tested 2026-10-07)
        for scraper in [scrape_kalibrr, scrape_linkedin]:
            try:
                jobs = scraper(keyword, on_job_found=on_job_found)
                for job in jobs:
                    key = f"{job['company'].lower()}|{job['position'].lower()}"
                    if key not in seen:
                        seen.add(key)
                        all_jobs.append(job)
                time.sleep(random.uniform(1, 3))
            except Exception as e:
                logger.error(f"Scraper error: {e}")

    logger.info(f"Total unique jobs found: {len(all_jobs)}")
    return all_jobs
