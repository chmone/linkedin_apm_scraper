import time
import json
import re
from typing import Iterator
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import logging
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    InvalidSessionIdException,
)
from selenium.webdriver.common.keys import Keys

from .base import BaseScraper
from .models import Job


class LinkedInScraper(BaseScraper):
    """
    Scrapes job listings from LinkedIn by interacting with the search results page.
    It clicks on each job to reveal the details in a side panel and scrapes the information from there.
    """

    def __init__(self, driver: webdriver.Chrome, logger: logging.Logger, **kwargs):
        super().__init__(driver, logger, **kwargs)
        self.wait = WebDriverWait(self.driver, 10)
    
    def login(self, email: str, password: str, cookie_filepath: str) -> bool:
        self.logger.info("Attempting to log in to LinkedIn.")
        self.driver.get("https://www.linkedin.com/")

        if cookie_filepath and os.path.exists(cookie_filepath):
            self.logger.info(f"Cookie file found at {cookie_filepath}. Attempting cookie-based login.")
            try:
                with open(cookie_filepath, 'r') as f:
                    cookies = json.load(f)
                for cookie in cookies:
                    # Validate and correct sameSite attribute
                    if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                        self.logger.warning(f"Invalid sameSite value '{cookie['sameSite']}' in cookie. Defaulting to 'Lax'.")
                        cookie['sameSite'] = "Lax"

                    if 'domain' in cookie and cookie['domain'].startswith('.'):
                        cookie['domain'] = cookie['domain'][1:]
                    self.driver.add_cookie(cookie)
                
                self.logger.info("Cookies loaded. Refreshing page.")
                self.driver.get("https://www.linkedin.com/feed/") # Go to feed to confirm

                try:
                    # More reliable check for login success
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.ID, "global-nav-search"))
                    )
                    self.logger.info("Cookie login successful! Verified by presence of global nav search.")
                    return True
                except TimeoutException:
                    self.logger.warning("Cookie login failed. Could not verify login via global nav search.")
                    self.take_screenshot("cookie_login_fail")
            except Exception as e:
                self.logger.error(f"An error occurred during cookie login: {e}")
                self.take_screenshot("cookie_login_error")
        else:
            self.logger.info("Cookie file not provided or not found. Proceeding with fallback login.")

        return self._fallback_login(email, password)

    def _fallback_login(self, email: str, password: str) -> bool:
        """Handles login when cookies fail or are not present."""
        self.logger.info("Initiating fallback login process.")
        
        if "login" not in self.driver.current_url and "checkpoint" not in self.driver.current_url:
            self.driver.get("https://www.linkedin.com/login")

        try:
            try:
                self.logger.info("Checking for email input field.")
                email_field = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                self.logger.info("Email field found. Entering email and password.")
                email_field.send_keys(email)
            except TimeoutException:
                self.logger.info("Email field not found. Assuming password-only prompt.")
            
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            password_field.send_keys(password)
            password_field.send_keys(Keys.RETURN)

            WebDriverWait(self.driver, 20).until(EC.url_contains("feed"))
            self.logger.info("Fallback login successful.")
            return True

        except TimeoutException:
            self.logger.error("Fallback login failed. Could not confirm login.")
            self.take_screenshot("fallback_login_failed")
            if "checkpoint" in self.driver.current_url:
                self.logger.error("LinkedIn is presenting a security challenge (CAPTCHA/2FA).")
            return False

    def authenticate(self) -> bool:
        """
        Satisfies the abstract base class method requirement.
        The actual login logic is handled by the `login` method.
        """
        self.logger.info("Verifying authentication status...")
        try:
            self.driver.get("https://www.linkedin.com/feed/")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "global-nav-search"))
            )
            self.logger.info("Authentication verified successfully.")
            return True
        except TimeoutException:
            self.logger.warning("Authentication check failed. User may not be logged in.")
            self.take_screenshot("auth_check_failed")
            return False

    def validate_url(self, url: str) -> bool:
        """
        Validate if the provided URL is a LinkedIn jobs URL.
        """
        return "linkedin.com" in url and ("/jobs/" in url or "/search/" in url)
        
    def scrape(self, search_url: str) -> Iterator[Job]:
        """
        Scrapes job listings from a LinkedIn search URL.

        Args:
            search_url: The URL of the LinkedIn job search results page.

        Yields:
            A Job object for each successfully scraped job posting.
        """
        self.logger.info(f"Navigating to search URL: {search_url}")
        self.driver.get(search_url)

        self.logger.info("Looking for job list elements...")
        
        # Pre-scrape check to ensure we are still logged in
        if not self.authenticate():
            self.logger.error("Session is invalid before scraping. Aborting.")
            return

        try:
            # Alternative selector for the job list container
            job_list_selector = "div.jobs-search-results-list"
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, job_list_selector))
            )
            job_elements = self.driver.find_elements(By.CSS_SELECTOR, f"{job_list_selector} ul > li")
            self.logger.info(f"Found {len(job_elements)} job elements in the list.")
        except TimeoutException:
            self.logger.error("Could not find job list container with any selector. The page structure may have changed.")
            self.take_screenshot("job_list_not_found")
            return

        # Process each job exactly once
        processed_job_urls = set()
        
        for index in range(len(job_elements)):
            try:
                # Re-fetch the list on each iteration to avoid stale elements
                fresh_job_list = self.driver.find_elements(By.CSS_SELECTOR, f"{job_list_selector} ul > li")
                if index >= len(fresh_job_list):
                    self.logger.warning(f"Job index {index} out of bounds, breaking loop.")
                    break
                
                job_to_click = fresh_job_list[index]
                
                # Scroll the job into view and click it to open detail panel
                self.logger.info(f"Processing job {index + 1}/{len(job_elements)}...")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", job_to_click)
                time.sleep(0.5)  # Brief pause for scrolling
                job_to_click.click()
                time.sleep(2)  # Wait for detail panel to load

                # Scrape job details from the opened detail panel
                job_details = self._get_job_details_from_panel(search_url)
                if job_details and job_details.url not in processed_job_urls:
                    processed_job_urls.add(job_details.url)
                    yield job_details
                elif job_details:
                    self.logger.info(f"Skipping duplicate job: {job_details.title}")

            except ElementClickInterceptedException:
                self.logger.warning(f"Could not click job at index {index}, it was obscured. Skipping.")
                continue
            except InvalidSessionIdException:
                self.logger.error("Browser session became invalid. Ending scraping for this URL.")
                break
            except Exception as e:
                self.logger.error(f"An error occurred while processing job index {index}: {e}")
                continue
        
        self.logger.info(f"Job processing complete. Found {len(processed_job_urls)} unique jobs total.")


    def _get_job_details_from_panel(self, search_url: str) -> Job | None:
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
            description_html = description_container.get_attribute('innerHTML').strip()
            description_text = description_container.text.strip()
            
            current_url = self.driver.current_url
            
            self.logger.info(f"✅ Scraped: {title} at {company}")
            
            return Job(
                title=title,
                company=company,
                location=location,
                description=description_html,
                url=current_url,
                search_url=search_url,
                platform="linkedin"
            )
        except TimeoutException:
            self.logger.error("Timed out waiting for job details panel to load.")
            self.take_screenshot("details_panel_timeout")
            return None
        except NoSuchElementException as e:
            self.logger.error(f"Could not find an element in the details panel: {e}")
            self.take_screenshot("details_panel_element_not_found")
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while scraping details panel: {e}")
            self.take_screenshot("details_panel_unexpected_error")
            return None


if __name__ == '__main__':
    # This block is for direct execution of the scraper for testing purposes.
    # It sets up the driver and calls the scraping method.
    pass 