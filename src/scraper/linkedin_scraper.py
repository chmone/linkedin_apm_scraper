import time
import json
import logging
from typing import Iterator

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
            self.driver.get("https://www.linkedin.com")
            with open(self.cookies_path, "r") as f:
                cookies = json.load(f)
            for cookie in cookies:
                if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                    del cookie['sameSite']
                self.driver.add_cookie(cookie)
            print("Successfully loaded session cookies.")
        except FileNotFoundError:
            print(f"Cookie file not found at '{self.cookies_path}'. Proceeding without authentication.")
        except Exception as e:
            logging.error(f"An error occurred while loading cookies: {e}", exc_info=True)

    def _dismiss_modal(self):
        """Checks for and dismisses a sign-in modal that can overlay the page."""
        try:
            close_button = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Dismiss']"))
            )
            self.driver.execute_script("arguments[0].click();", close_button)
            print("Dismissed a pop-up modal.")
            time.sleep(1)
        except TimeoutException:
            print("No pop-up modal found to dismiss.")
        except Exception as e:
            # It's not critical if this fails, so we log and continue.
            print(f"An error occurred trying to dismiss modal, continuing: {e}")

    def scrape(self, search_url: str) -> Iterator[Job]:
        """
        Scrapes a LinkedIn job search URL by clicking each job and extracting details from the side panel.

        Args:
            search_url: The URL of the LinkedIn job search results page.

        Yields:
            A Job object for each successfully scraped job posting.
        """
        self.driver.get(search_url)
        print(f"Navigating to search URL: {search_url}")

        self._dismiss_modal()

        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.scaffold-layout__list-item")))
            print("Job list items found.")
        except TimeoutException:
            print("Timeout waiting for job list items to load.")
            return

        job_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
        print(f"Found {len(job_elements)} job items to process.")

        for index in range(len(job_elements)):
            try:
                # Re-fetch elements to prevent staleness
                job_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
                if index >= len(job_elements):
                    break
                
                job_element = job_elements[index]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", job_element)
                time.sleep(1)
                job_element.click()
                time.sleep(2) # Wait for details to load

                details_container = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.jobs-search__job-details--container")))
                
                # Expand description
                try:
                    see_more_button = details_container.find_element(By.CSS_SELECTOR, "button.jobs-description__footer-button")
                    if see_more_button.is_displayed():
                        self.driver.execute_script("arguments[0].click();", see_more_button)
                        time.sleep(1)
                except (NoSuchElementException, TimeoutException):
                    pass # No button, or it's not visible

                title = details_container.find_element(By.CSS_SELECTOR, ".jobs-details-top-card__job-title").text
                company = details_container.find_element(By.CSS_SELECTOR, ".jobs-details-top-card__company-info a").text
                location = details_container.find_element(By.CSS_SELECTOR, ".jobs-details-top-card__company-info > span").text
                description = self.driver.find_element(By.ID, "job-details").text
                
                # Get the direct URL from the list item link and clean it
                direct_url = job_element.find_element(By.CSS_SELECTOR, "a").get_attribute("href").split('?')[0]
                
                search_url_with_id = self.driver.current_url

                print(f"Successfully scraped job: '{title}' at '{company}'")
                yield Job(
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=direct_url,
                    search_url=search_url_with_id,
                )

            except Exception as e:
                print(f"An unexpected error occurred while processing job {index + 1}: {e}")
                continue


if __name__ == '__main__':
    # This block is for direct execution of the scraper for testing purposes.
    # It sets up the driver and calls the scraping method.
    pass 