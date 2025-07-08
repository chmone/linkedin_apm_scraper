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
            
            # Wait for page to load and verify login state
            time.sleep(3)
            
            # Check if we're logged in by looking for profile elements
            try:
                # Look for elements that indicate we're logged in
                profile_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-test-id='profile-button'], .global-nav__me, .feed-identity-module")
                if profile_elements:
                    print("Successfully loaded session cookies - Login verified.")
                else:
                    print("Warning: Cookies loaded but login verification failed. May need fresh cookies.")
            except:
                print("Warning: Could not verify login state after loading cookies.")
                
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
        # Ensure we start from LinkedIn main page to maintain session context
        print("Ensuring session is established on LinkedIn main page...")
        self.driver.get("https://www.linkedin.com")
        time.sleep(2)
        
        # Verify we're still logged in on main page before proceeding
        try:
            profile_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-test-id='profile-button'], .global-nav__me, .feed-identity-module")
            if not profile_elements:
                print("Warning: Not logged in on main page. Session may have expired.")
                self.driver.save_screenshot("/app/login_failed_main_page.png")
                return
            else:
                print("Login verified on main page. Proceeding to job search.")
        except Exception as e:
            print(f"Could not verify login state on main page: {e}")
            return
        
        # Now navigate to the job search URL
        self.driver.get(search_url)
        print(f"Navigating to search URL: {search_url}")
        time.sleep(3)  # Give extra time for job search page to load

        # Check for sign-in modal immediately after navigation
        if self._check_for_signin_modal():
            print("Sign-in modal detected after navigating to job search. Session was lost during navigation.")
            self.driver.save_screenshot("/app/signin_modal_after_navigation.png")
            print("Debug screenshot saved: signin_modal_after_navigation.png")
            return

        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.job-search-card")))
            print("Job list items found.")
        except TimeoutException:
            print("Timeout waiting for job list items to load.")
            # Check if modal appeared during wait
            if self._check_for_signin_modal():
                print("Sign-in modal appeared while waiting for job list.")
                self.driver.save_screenshot("/app/signin_modal_during_wait.png")
            return

        job_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.job-search-card")
        print(f"Found {len(job_elements)} job items to process.")
        
        # Take a screenshot to verify login and page state
        try:
            self.driver.save_screenshot("/app/job_search_ready.png")
            print("Debug screenshot saved: job_search_ready.png")
        except:
            pass
        
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
                job_to_click.click()
                time.sleep(2)  # Wait for panel to load

                job_details = self._get_job_details_from_panel(search_url)
                if job_details:
                    yield job_details

            except ElementClickInterceptedException:
                print(f"Could not click job at index {index}, it was obscured. Skipping.")
                # Take a screenshot to debug clicking issues
                try:
                    self.driver.save_screenshot(f"/app/click_error_{index}.png")
                    print(f"Debug screenshot saved: click_error_{index}.png")
                except:
                    pass
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

    def _check_for_signin_modal(self):
        """
        Checks if the 'Sign in to view more jobs' modal is present on the page.
        Returns True if modal is detected, False otherwise.
        """
        signin_modal_selectors = [
            # Text-based detection
            "//*[contains(text(), 'Sign in to view more jobs')]",
            "//*[contains(text(), 'Continue with Google')]", 
            "//*[contains(text(), 'Sign In') and contains(@class, 'button')]",
            # Modal container detection
            ".auth-modal",
            ".contextual-sign-in-modal",
            "[data-tracking-control-name*='sign-in-modal']",
            # Button detection
            "button[data-tracking-control-name*='contextual-sign-in']",
            # Generic modal patterns
            "[role='dialog'][aria-labelledby*='sign']"
        ]
        
        for selector in signin_modal_selectors:
            try:
                if selector.startswith("//"):
                    # XPath selector
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    # CSS selector
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                if elements and any(elem.is_displayed() for elem in elements):
                    print(f"Sign-in modal detected using selector: {selector}")
                    return True
            except Exception:
                continue
        
        return False


if __name__ == '__main__':
    # This block is for direct execution of the scraper for testing purposes.
    # It sets up the driver and calls the scraping method.
    pass 