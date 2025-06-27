import time
import json
from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config.config import Config
from .base import Scraper
from scraper.models import Job
from selenium.common.exceptions import TimeoutException, InvalidArgumentException

class LinkedInScraper(Scraper):
    """
    Scrapes job listings from LinkedIn.
    """
    def __init__(self, search_urls, cookies_file):
        self.search_urls = search_urls
        self.cookies_file = cookies_file
        self.driver = self._initialize_driver()
        self._load_cookies()
        print("LinkedIn Scraper Initialized.")

    def _initialize_driver(self):
        """Initializes a headless Selenium WebDriver."""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")  # Recommended for Docker
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            print("Initializing Chrome driver...")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            driver = webdriver.Chrome(options=chrome_options)
            return driver
        except Exception as e:
            print(f"Error initializing driver: {e}")
            return None

    def _load_cookies(self):
        """Loads session cookies into the browser."""
        # LinkedIn requires you to be on the domain to set cookies
        self.driver.get("https://www.linkedin.com")

        with open(self.cookies_file, 'r') as f:
            cookies = json.load(f)

        for cookie in cookies:
            # Sanitize the 'sameSite' attribute if it's invalid
            if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                del cookie['sameSite']
            self.driver.add_cookie(cookie)
        
        print("Cookies loaded. Page will not be refreshed.")

    def scrape(self) -> List[Job]:
        """
        Scrapes LinkedIn for job postings.
        """
        self._load_cookies()
        all_jobs = []

        for url in self.search_urls:
            if not url or not url.strip().startswith('http'):
                print(f"Skipping invalid or empty URL: {url}")
                continue

            try:
                print(f"Scraping search results from: {url}")
                self.driver.get(url)
                time.sleep(5) # Wait for page to load and modal to potentially appear

                # Try to close the sign-in modal by clicking the dismiss button
                try:
                    print("Trying to find and click modal dismiss button with aria-label='Dismiss'...")
                    close_button = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Dismiss']"))
                    )
                    self.driver.execute_script("arguments[0].click();", close_button)
                    print("Clicked the modal dismiss button via JavaScript.")
                    time.sleep(2)  # wait for modal to close
                except TimeoutException:
                    print("Could not find modal dismiss button with aria-label='Dismiss'.")
                except Exception as e:
                    print(f"An error occurred while trying to close the modal: {e}")

                try:
                    # Find all job links directly on the page, waiting for at least one to be present
                    job_links = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href*='/jobs/view/']"))
                    )
                    print(f"Found {len(job_links)} potential job links on the page.")

                    job_urls = [link.get_attribute("href") for link in job_links]

                    # Remove duplicate URLs
                    job_urls = list(dict.fromkeys(job_urls))

                    print(f"Found {len(job_urls)} unique job links on the page.")

                    for job_url in job_urls:
                        try:
                            job = self._scrape_job_details(job_url)
                            if job:
                                all_jobs.append(job)
                        except Exception as e:
                            print(f"Error scraping job detail for {job_url}: {e}")

                except TimeoutException as e:
                    screenshot_path = "/app/linkedin_error_screenshot.png"
                    print(f"Error scraping search results page {url} : {e.msg}")
                    self.driver.save_screenshot(screenshot_path)
                    print(f"Saved a screenshot to {screenshot_path} for debugging.")
                except Exception as e:
                    screenshot_path = "/app/linkedin_error_screenshot.png"
                    print(f"An unexpected error occurred on search page {url}: {e}")
                    self.driver.save_screenshot(screenshot_path)
                    print(f"Saved a screenshot to {screenshot_path} for debugging.")

            except InvalidArgumentException as e:
                print(f"Invalid argument error for URL '{url}': {e.msg}")
                print("This usually means the URL is malformed. Skipping.")
                continue
            except TimeoutException as e:
                screenshot_path = "/app/linkedin_error_screenshot.png"
                print(f"Error scraping search results page {url} : {e.msg}")
                self.driver.save_screenshot(screenshot_path)
                print(f"Saved a screenshot to {screenshot_path} for debugging.")

        self.driver.quit()
        print(f"Scraping complete. Found {len(all_jobs)} total jobs.")
        return all_jobs

    def _scrape_job_details(self, job_url: str) -> Job | None:
        """Scrapes the details from a single job posting page."""
        self.driver.get(job_url)
        time.sleep(3) # Wait for page to load

        try:
            title = self.driver.find_element(By.CLASS_NAME, "top-card-layout__title").text
            company = self.driver.find_element(By.CLASS_NAME, "topcard__org-name-link").text
            description = self.driver.find_element(By.CLASS_NAME, "show-more-less-html__markup").text
            
            job = Job(
                title=title,
                company=company,
                url=job_url,
                description=description
            )
            print(f"Successfully scraped: {title} at {company}")
            return job

        except Exception as e:
            print(f"Could not extract job details from {job_url}: {e}")
            return None

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
        scraper = LinkedInScraper(search_urls=test_config.search_urls, cookies_file="cookies.json")
        jobs = scraper.scrape()
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