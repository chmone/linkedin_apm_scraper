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
    ElementClickInterceptedException,
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
        """Loads session cookies into the browser to maintain login state."""
        try:
            with open(self.cookies_path, "r") as file:
                cookies = json.load(file)
            self.driver.get("https://www.linkedin.com")
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            self.driver.refresh()
            print("Successfully loaded session cookies.")
        except FileNotFoundError:
            print(
                f"Cookie file not found at {self.cookies_path}. The scraper will operate without being logged in."
            )
        except Exception as e:
            print(f"An error occurred loading cookies: {e}")

    def _dismiss_modal(self):
        """Dismisses the messaging pop-up modal if it appears."""
        try:
            modal_button = self.wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.msg-overlay-bubble-header__control--new-convo-btn")
                )
            )
            modal_button.click()
            print("Dismissed the pop-up modal.")
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
                # Re-fetch the list on each iteration to prevent stale element exceptions
                job_list = self.driver.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
                if index >= len(job_list):
                    print("Index out of bounds, breaking loop.")
                    break
                
                job_to_click = job_list[index]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", job_to_click)
                time.sleep(1) # a small pause
                job_to_click.click()
                time.sleep(2)  # Wait for panel to load

                job_details = self._get_job_details_from_panel()
                if job_details:
                    yield job_details

            except ElementClickInterceptedException:
                print(f"Could not click job at index {index}, it was obscured. Skipping.")
                # self._dismiss_modal() # Check again for modals
                continue
            except Exception as e:
                print(f"An error occurred while processing job index {index}: {e}")
                continue

    def _get_job_details_from_panel(self) -> Job | None:
        """
        Extracts all job details from the right-hand side panel.
        """
        try:
            # Wait for the main panel container to ensure it's loaded
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.job-view-layout.jobs-details")))
            
            title = self.driver.find_element(By.CSS_SELECTOR, "div.job-details-jobs-unified-top-card__job-title h1").text.strip()
            
            company = self.driver.find_element(By.CSS_SELECTOR, "div.job-details-jobs-unified-top-card__company-name a").text.strip()
            
            # The location is the first part of a container with other info
            tertiary_info = self.driver.find_element(By.CSS_SELECTOR, "div.job-details-jobs-unified-top-card__tertiary-description-container").text.strip()
            location = tertiary_info.split('·')[0].strip()

            # Expand the job description
            try:
                see_more_button = self.driver.find_element(By.CSS_SELECTOR, "button.jobs-description__footer-button")
                self.driver.execute_script("arguments[0].click();", see_more_button)
                time.sleep(0.5) # A minimal pause for content to reflow
            except NoSuchElementException:
                pass # No "see more" button

            description_container = self.driver.find_element(By.CSS_SELECTOR, "div#job-details")
            description = description_container.get_attribute('innerHTML').strip()
            
            current_url = self.driver.current_url
            
            print(f"Successfully scraped: {title} at {company}")
            return Job(
                title=title,
                company=company,
                location=location,
                description=description,
                url=current_url,
            )
        except TimeoutException:
            print("Timed out waiting for job details panel to load.")
            return None
        except NoSuchElementException as e:
            print(f"Could not find an element in the details panel: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while scraping details panel: {e}")
            return None


if __name__ == '__main__':
    # This block is for direct execution of the scraper for testing purposes.
    # It sets up the driver and calls the scraping method.
    pass 