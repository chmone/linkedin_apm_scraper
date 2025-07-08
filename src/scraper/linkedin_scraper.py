import time
import json
import re
from typing import Iterator
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    InvalidSessionIdException,
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
            
            # Take screenshot to verify login state
            time.sleep(2)  # Wait for page to load after cookie refresh
            self.driver.save_screenshot("/app/debug_0_login_state.png")
            print("Successfully loaded session cookies.")
            print("Screenshot saved: debug_0_login_state.png")
        except FileNotFoundError:
            print(
                f"Cookie file not found at {self.cookies_path}. The scraper will operate without being logged in."
            )
        except Exception as e:
            print(f"An error occurred loading cookies: {e}")

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

        # Take screenshot after page load
        self.driver.save_screenshot("/app/debug_1_after_page_load.png")
        print("Screenshot saved: debug_1_after_page_load.png")

        # Dismiss any modals that might be blocking interactions
        self._dismiss_modals()

        # Take screenshot after modal dismissal
        self.driver.save_screenshot("/app/debug_2_after_modal_dismiss.png")
        print("Screenshot saved: debug_2_after_modal_dismiss.png")

        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.job-search-card")))
            print("Job list items found.")
        except TimeoutException:
            print("Timeout waiting for job list items to load.")
            return

        job_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.job-search-card")
        print(f"Found {len(job_elements)} job items to process.")
        
        for index in range(len(job_elements)):
            try:
                # Re-fetch the list on each iteration to prevent stale element exceptions
                job_list = self.driver.find_elements(By.CSS_SELECTOR, "div.job-search-card")
                if index >= len(job_list):
                    print("Index out of bounds, breaking loop.")
                    break
                
                job_to_click = job_list[index]
                self.driver.execute_script("arguments[0].scrollIntoView(true);", job_to_click)
                time.sleep(1) # a small pause
                
                # Take screenshot before clicking job
                self.driver.save_screenshot(f"/app/debug_3_before_click_job_{index}.png")
                print(f"Screenshot saved: debug_3_before_click_job_{index}.png")
                
                job_to_click.click()
                time.sleep(2)  # Wait for panel to load
                
                # Take screenshot after clicking job
                self.driver.save_screenshot(f"/app/debug_4_after_click_job_{index}.png")
                print(f"Screenshot saved: debug_4_after_click_job_{index}.png")

                job_details = self._get_job_details_from_panel(search_url)
                if job_details:
                    yield job_details

            except ElementClickInterceptedException:
                print(f"Could not click job at index {index}, it was obscured. Skipping.")
                continue
            except InvalidSessionIdException:
                print("Browser session became invalid. Ending scraping for this URL.")
                break # Exit the loop for this search URL
            except Exception as e:
                print(f"An error occurred while processing job index {index}: {e}")
                continue

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
            
            print(f"Successfully scraped: {title} at {company}")
            print(f"Description snippet: {description_text[:150]}...")
            
            return Job(
                title=title,
                company=company,
                location=location,
                description=description_html,
                url=current_url,
                search_url=search_url,
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

    def _dismiss_modals(self):
        """
        Attempts to dismiss any modal dialogs that might be blocking interactions.
        """
        time.sleep(2)  # Give page time to load any modals
        
        # Try multiple common modal dismiss selectors
        dismiss_selectors = [
            "button[aria-label='Dismiss']",
            "button[data-tracking-control-name='public_jobs_contextual-sign-in-modal_modal_dismiss']",
            ".modal__dismiss",
            ".artdeco-modal__dismiss",
            "button.artdeco-button--circle",
            ".jobs-modal__dismiss-button",
            "[data-test-modal-close-btn]"
        ]
        
        for selector in dismiss_selectors:
            try:
                dismiss_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                if dismiss_button.is_displayed():
                    print(f"Trying to find and click modal dismiss button with selector: {selector}")
                    self.driver.execute_script("arguments[0].click();", dismiss_button)
                    print("Clicked the modal dismiss button via JavaScript.")
                    time.sleep(1)  # Wait for modal to close
                    return
            except NoSuchElementException:
                continue
            except Exception as e:
                print(f"Error trying to dismiss modal with selector {selector}: {e}")
                continue
        
        # Try sending ESCAPE key as fallback
        try:
            print("Trying to close modal by sending ESCAPE key...")
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            print("Sent ESCAPE key and waited for modal to close.")
            time.sleep(1)
        except Exception as e:
            print(f"Error sending ESCAPE key: {e}")


if __name__ == '__main__':
    # This block is for direct execution of the scraper for testing purposes.
    # It sets up the driver and calls the scraping method.
    pass 