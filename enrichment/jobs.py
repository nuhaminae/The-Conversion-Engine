# enrichment/jobs.py
# This is the web scraping module using Playwright.
# It's designed to be asynchronous.
# This script is a template; the CSS selectors will likely need to be adjusted for the specific websites you target.

import asyncio
from typing import Dict, List

from playwright.async_api import TimeoutError, async_playwright


async def scrape_job_postings(company_name: str, jobs_page_url: str) -> Dict:
    """
    Scrapes job postings from a given URL using Playwright.

    This is a generic scraper and may need its CSS selectors adjusted for specific sites.
    It looks for common patterns in job listings.

    Args:
        company_name: The name of the target company.
        jobs_page_url: The URL of the company's careers or jobs page.

    Returns:
        A dictionary containing the list of jobs found and the scrape status.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        jobs = []
        status = "success"
        error_message = None

        try:
            print(f"Navigating to {jobs_page_url}...")
            await page.goto(jobs_page_url, wait_until="domcontentloaded", timeout=15000)

            # --- Common Selectors to Try ---
            # This is the most brittle part. We try a few common patterns.
            # Pattern 1: Greenhouse boards (e.g., #jobs-board, .opening)
            # Pattern 2: Lever boards (e.g., .postings-group, .posting)
            # Pattern 3: Generic lists (e.g., ul/li with 'job' in class)
            # Pattern 4: Simple links with job titles

            job_elements = await page.query_selector_all(
                ".opening, .posting, [class*='job-item'], [class*='job-listing'], [class*='career-card']"
            )

            if not job_elements:
                # Fallback to more generic link search if specific containers aren't found
                job_elements = await page.query_selector_all(
                    "a[href*='job'], a[href*='career']"
                )

            print(f"Found {len(job_elements)} potential job elements.")

            for el in job_elements:
                try:
                    # Attempt to find a title and a link within the element
                    title_el = await el.query_selector(
                        "h2, h3, h4, .job-title, [class*='title']"
                    )
                    link_el = await el.query_selector("a")

                    title = (
                        await title_el.inner_text() if title_el else "No title found"
                    )
                    link = await link_el.get_attribute("href") if link_el else ""

                    # Clean up title and create an absolute URL for the link
                    title = title.strip()
                    if link and not link.startswith("http"):
                        link = page.url.rstrip("/") + "/" + link.lstrip("/")

                    if title != "No title found" and link:
                        jobs.append({"title": title, "url": link})
                except Exception:
                    # Ignore elements that don't conform to the expected structure
                    continue

        except TimeoutError:
            status = "error"
            error_message = (
                f"Timeout: The page at {jobs_page_url} took too long to load."
            )
            print(error_message)
        except Exception as e:
            status = "error"
            error_message = f"An unexpected error occurred: {e}"
            print(error_message)
        finally:
            await browser.close()

        # Deduplicate results based on URL
        unique_jobs = list({job["url"]: job for job in jobs}.values())

        return {
            "status": status,
            "company": company_name,
            "jobs_page_url": jobs_page_url,
            "job_count": len(unique_jobs),
            "jobs": unique_jobs,
            "error": error_message,
        }


if __name__ == "__main__":
    # Example usage: Scraping a public jobs board known to work well with this structure
    # NOTE: This target may change over time. BuiltIn is used as an example.
    test_url = "https://www.builtinla.com/jobs/mid-level/product-management"

    async def main():
        results = await scrape_job_postings("BuiltIn LA", test_url)
        print("\n--- Scraping Results ---")
        print(f"Status: {results['status']}")
        if results["status"] == "success":
            print(f"Found {results['job_count']} jobs.")
            for job in results["jobs"][:5]:  # Print first 5
                print(f"  - {job['title']} ({job['url']})")

    asyncio.run(main())
