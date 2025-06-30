import time
import json
import re
from typing import Iterator
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
)

from .base import BaseScraper
from .models import Job


class LinkedInScraper(BaseScraper):
    """
    Scrapes job listings from LinkedIn by interacting with the search results page.
    It clicks on each job to reveal the details in a side panel and scrapes the information from there.
    """

    def __init__(self, driver: webdriver.Chrome, cookies_path: str = "cookies.json"):
        super().__init__(driver)
        self.cookies_path = cookies_path
        self.wait = WebDriverWait(self.driver, 10)
        self._load_cookies()

    def _load_cookies(self):
        """Loads session cookies into the browser to maintain the user's session."""
        try:
            # We must be on the linkedin.com domain to set cookies for it.
            self.driver.get("https://www.linkedin.com")
            with open(self.cookies_path, "r") as f:
                cookies = json.load(f)
            for cookie in cookies:
                # Sanitize the 'sameSite' attribute if it's invalid.
                # Some browser extensions export this with values Selenium doesn't recognize.
                if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                    del cookie['sameSite']
                self.driver.add_cookie(cookie)
            print("Successfully loaded session cookies.")
        except FileNotFoundError:
            print(f"Cookie file not found at '{self.cookies_path}'. Proceeding without authentication.")
        except Exception as e:
            logging.error(f"An error occurred while loading cookies: {e}", exc_info=True)

    def scrape(self, search_url: str) -> Iterator[Job]:
        """
        Scrapes a LinkedIn job search URL.

        Args:
            search_url: The URL of the LinkedIn job search results page.

        Yields:
            A Job object for each successfully scraped job posting.
        """
        print(f"Navigating to search URL: {search_url}")
        self.driver.get(search_url)

        # Handle the potential sign-in modal that can block clicks
        try:
            close_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Dismiss']"))
            )
            self.driver.execute_script("arguments[0].click();", close_button)
            print("Dismissed a pop-up modal.")
            time.sleep(2)  # Wait for modal to disappear
        except TimeoutException:
            print("No pop-up modal found to dismiss.")
        except Exception as e:
            print(f"An error occurred trying to dismiss modal: {e}")

        try:
            # Wait for the main job list container to be present on the page
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ul.jobs-search__results-list"))
            )
            print("Job list container found.")
        except TimeoutException:
            print("Timeout waiting for job list to load. Cannot continue scraping this URL.")
            return

        # We get the list of job items to iterate over
        job_list_items = self.driver.find_elements(By.CSS_SELECTOR, "ul.jobs-search__results-list > li")
        print(f"Found {len(job_list_items)} job items in the list.")

        for index in range(len(job_list_items)):
            try:
                # Re-fetch the list on each iteration to prevent stale element exceptions
                job_elements = self.driver.find_elements(By.CSS_SELECTOR, "ul.jobs-search__results-list > li")
                if index >= len(job_elements):
                    print("Index out of bounds, stopping iteration.")
                    break
                job_element = job_elements[index]

                # Scroll to the element and click it to load details
                self.driver.execute_script("arguments[0].scrollIntoView(true);", job_element)
                time.sleep(1) # Pause for UI to settle
                
                # Use a Javascript click to bypass potential overlays
                self.driver.execute_script("arguments[0].click();", job_element)
                
                time.sleep(1) # Pause for details to load

                # Wait for the details panel to be loaded
                details_panel = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-search__job-details--container"))
                )

                # Click the "See more" button to expand the description if it exists
                try:
                    see_more_button = details_panel.find_element(By.CSS_SELECTOR, "button.jobs-description__footer-button")
                    if see_more_button.is_displayed():
                        self.driver.execute_script("arguments[0].click();", see_more_button)
                        time.sleep(1) # Wait for description to expand
                except NoSuchElementException:
                    pass # Button not found, description is likely not truncated.
                except Exception as e:
                    logging.warning(f"Could not click 'See more' button, proceeding with potentially truncated description. Error: {e}")

                # Scrape information from the details panel
                title = details_panel.find_element(By.CSS_SELECTOR, "h2.jobs-details-top-card__job-title").text
                company = details_panel.find_element(By.CSS_SELECTOR, "a.jobs-details-top-card__company-url").text
                # The location is in one of the 'bullets'. We'll take the first one.
                location = details_panel.find_element(By.CSS_SELECTOR, "span.jobs-details-top-card__bullet").text
                description = details_panel.find_element(By.ID, "job-details").text

                # Get the direct URL and construct the notification URL
                href = job_element.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                direct_url = href.split('?')[0]
                
                job_id_match = re.search(r'view/(\d+)/', href)
                if not job_id_match:
                    print(f"Could not extract job ID from URL: {href}")
                    continue
                job_id = job_id_match.group(1)

                parsed_search_url = urlparse(search_url)
                query_params = parse_qs(parsed_search_url.query)
                query_params['currentJobId'] = [job_id]
                new_query = urlencode(query_params, doseq=True)
                search_url_with_id = urlunparse(
                    (parsed_search_url.scheme, parsed_search_url.netloc, parsed_search_url.path, parsed_search_url.params, new_query, parsed_search_url.fragment)
                )

                print(f"Successfully scraped job: '{title}' at '{company}'")
                yield Job(
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=direct_url,
                    search_url=search_url_with_id,
                )

            except (NoSuchElementException, TimeoutException) as e:
                print(f"Skipping a job due to a scraping error (element not found or timeout): {e}")
                # It's safer to just continue to the next item
                continue
            except Exception as e:
                print(f"An unexpected error occurred while processing a job: {e}")
                continue

if __name__ == '__main__':
    # This is for testing the class structure
    # NOTE: This will not run successfully without valid cookies and a running Selenium WebDriver.
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from config.config import Config
    
    # Create dummy files for config to load
    os.makedirs("writing_style_samples", exist_ok=True)
    with open(".env", "w") as f: f.write("")
    with open("search_urls.txt", "w") as f: f.write("https://www.linkedin.com/jobs/search/?keywords=product%20manager")
    # A valid cookies.json would be a list of dicts, not just one object
    with open("cookies.json", "w") as f: f.write('[]') 
    with open("resume.json", "w") as f: f.write("{}")
    with open("ideal_job_profile.txt", "w") as f: f.write("")
    
    print("--- Running Scraper Test ---")
    print("NOTE: This test requires a valid cookies.json file and a working internet connection.")
    print("It will likely fail with an empty cookies file, but it tests the class structure.")
    
    try:
        test_config = Config.get_instance()
        scraper = LinkedInScraper(driver=webdriver.Chrome(options=webdriver.ChromeOptions()))
        jobs = list(scraper.scrape(test_config.search_urls[0]))
        print(f"Scraper finished. Scraped {len(jobs)} jobs.")
    except Exception as e:
        print(f"Test run failed as expected (likely due to invalid cookies): {e}")
    finally:
        # Clean up
        os.remove(".env")
        os.remove("search_urls.txt")
        os.remove("cookies.json")
        os.remove("resume.json")
        os.remove("ideal_job_profile.txt")
        os.rmdir("writing_style_samples") 