import time
import json
from typing import Iterator
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .base import BaseScraper
from .models import Job


class LinkedInScraper(BaseScraper):
    """
    Scrapes job listings from LinkedIn by navigating to each job's individual page.
    """

    def __init__(self, driver: webdriver.Chrome, cookies_path: str = "cookies.json"):
        super().__init__(driver)
        self.cookies_path = cookies_path
        self.wait = WebDriverWait(self.driver, 15) # Increased wait time for page loads
        self._load_cookies()

    def _load_cookies(self):
        """Loads session cookies into the browser to maintain login state."""
        try:
            with open(self.cookies_path, "r") as file:
                cookies = json.load(file)
            self.driver.get("https://www.linkedin.com")
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            print("Successfully loaded session cookies.")
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Cookie file not found or invalid at {self.cookies_path}. Proceeding unauthenticated.")
        except Exception as e:
            print(f"An error occurred loading cookies: {e}")

    def scrape(self, search_url: str) -> Iterator[Job]:
        """
        Scrapes a LinkedIn job search URL by extracting direct job links and visiting each one.

        Args:
            search_url: The URL of the LinkedIn job search results page.

        Yields:
            A Job object for each successfully scraped job posting.
        """
        self.driver.get(search_url)
        print(f"Navigating to search results: {search_url}")
        
        # Add a delay and scroll to mimic human behavior and trigger lazy-loading
        time.sleep(5)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        try:
            job_list_container = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.jobs-search__results-list")))
            job_links = job_list_container.find_elements(By.CSS_SELECTOR, "a.job-card-list__title")
            
            urls_to_scrape = [link.get_attribute('href') for link in job_links]
            print(f"Found {len(urls_to_scrape)} job URLs to scrape.")

            for i, url in enumerate(urls_to_scrape):
                print(f"Scraping job {i+1}/{len(urls_to_scrape)}: {url}")
                try:
                    job = self._scrape_job_page(url)
                    if job:
                        yield job
                except Exception as e:
                    print(f"Error scraping job page {url}: {e}")

        except TimeoutException:
            print("Timeout waiting for job search results to load.")
            return

    def _scrape_job_page(self, job_url: str) -> Job | None:
        """Scrapes the details from a direct job posting URL."""
        self.driver.get(job_url)
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.top-card-layout__title")))
            
            title = self.driver.find_element(By.CSS_SELECTOR, "h1.top-card-layout__title").text.strip()
            
            company_info = self.driver.find_element(By.CSS_SELECTOR, "div.top-card-layout__entity-info-container")
            company = company_info.find_element(By.css_selector, "a").text.strip()
            location = company_info.find_element(By.css_selector, "span.topcard__flavor--bullet").text.strip()
            
            description = self.driver.find_element(By.CSS_SELECTOR, "div.description__text").get_attribute('innerHTML').strip()
            
            print(f"Successfully scraped: {title} at {company}")
            return Job(title=title, company=company, location=location, description=description, url=job_url)
            
        except TimeoutException:
            print(f"Timeout waiting for job page to load: {job_url}")
            return None
        except NoSuchElementException as e:
            print(f"Could not find an element on job page {job_url}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred on job page {job_url}: {e}")
            return None


if __name__ == '__main__':
    # This block is for direct execution of the scraper for testing purposes.
    # It sets up the driver and calls the scraping method.
    pass 