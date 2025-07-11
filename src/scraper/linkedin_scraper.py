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

    def __init__(self, driver: webdriver.Chrome, platform_config=None, 
                 linkedin_email: str = None, linkedin_password: str = None, 
                 notifier=None, **kwargs):
        super().__init__(driver, platform_config, **kwargs)
        self.linkedin_email = linkedin_email
        self.linkedin_password = linkedin_password
        self.notifier = notifier
        self.wait = WebDriverWait(self.driver, 10)
        # Don't load cookies at initialization - do it when we actually need authentication
    
    def _mask_automation_properties(self):
        """Execute JavaScript to hide automation properties that sites might detect."""
        try:
            # Override navigator.webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Override other automation detection properties
            self.driver.execute_script("""
                // Remove webdriver property
                delete navigator.__proto__.webdriver;
                
                // Override plugins and languages to appear more realistic
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Override chrome property to appear like regular Chrome
                Object.defineProperty(navigator, 'chrome', {
                    get: () => ({
                        app: {
                            isInstalled: false,
                        },
                        webstore: {
                            onInstallStageChanged: {},
                            onDownloadProgress: {},
                        },
                        runtime: {
                            onConnect: {},
                            onMessage: {},
                        },
                    })
                });
                
                // Override permissions property
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' })
                    })
                });
            """)
            print("Successfully masked automation properties on current page.")
        except Exception as e:
            print(f"Warning: Could not mask automation properties: {e}")
    
    def _reapply_stealth_javascript(self):
        """Re-apply JavaScript masking on the current page to maintain stealth."""
        try:
            # Override navigator.webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Override other automation detection properties
            self.driver.execute_script("""
                // Remove webdriver property
                delete navigator.__proto__.webdriver;
                
                // Override plugins and languages to appear more realistic
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Override chrome property to appear like regular Chrome
                Object.defineProperty(navigator, 'chrome', {
                    get: () => ({
                        app: {
                            isInstalled: false,
                        },
                        webstore: {
                            onInstallStageChanged: {},
                            onDownloadProgress: {},
                        },
                        runtime: {
                            onConnect: {},
                            onMessage: {},
                        },
                    })
                });
                
                // Override permissions property
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' })
                    })
                });
            """)
            print("Re-applied stealth JavaScript for current page.")
        except Exception as e:
            print(f"Warning: Could not re-apply stealth JavaScript: {e}")
    
    def authenticate(self) -> bool:
        """
        Perform LinkedIn-specific authentication using email and password.
        Returns True if authentication was successful, False otherwise.
        """
        if not self.linkedin_email or not self.linkedin_password:
            logging.error("LinkedIn email or password not provided in environment variables.")
            return False

        try:
            logging.info("Attempting full login with email and password...")
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(2)

            # Find and fill the email/username field
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_field.send_keys(self.linkedin_email)
            logging.info("Filled in email.")
            time.sleep(0.5)

            # Find and fill the password field
            password_field = self.wait.until(EC.presence_of_element_located((By.ID, "password")))
            password_field.send_keys(self.linkedin_password)
            logging.info("Filled in password.")
            time.sleep(0.5)

            # Click the sign-in button
            sign_in_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
            sign_in_button.click()
            logging.info("Clicked sign-in button.")

            # Wait for login to complete by checking for a known element on the feed page
            self.wait.until(EC.presence_of_element_located((By.ID, "global-nav-search")))
            
            logging.info("✅ Login successful - redirected to feed or profile!")
            return True

        except TimeoutException:
            logging.error("Login failed: Timeout waiting for feed page after login.")
            self._send_auth_failure_notification("Timeout after login attempt.")
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during login: {e}")
            self._send_auth_failure_notification(f"Unexpected login error: {e}")
            return False
    
    def validate_url(self, url: str) -> bool:
        """
        Validate if the provided URL is a LinkedIn jobs URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is a valid LinkedIn jobs URL, False otherwise
        """
        return "linkedin.com" in url and ("/jobs/" in url or "/search/results/people/" in url)
    
    def _attempt_login(self) -> bool:
        """
        DEPRECATED: This method is no longer used for primary authentication.
        Attempt to authenticate by loading cookies when we detect we need login.
        Returns True if authentication appears successful, False otherwise.
        """
        return False # Deprecating cookie-based login

    def _check_for_welcome_back_screen(self) -> bool:
        """
        DEPRECATED: No longer needed with direct login.
        """
        return False
    
    def _wait_for_welcome_back_screen(self, timeout: int = 15) -> bool:
        """
        DEPRECATED: No longer needed with direct login.
        """
        return False

    def _complete_password_login(self) -> bool:
        """
        DEPRECATED: No longer needed with direct login.
        """
        return False
    
    def _load_cookies(self):
        """
        DEPRECATED: No longer used.
        """
        pass
        
    def scrape(self, search_url: str) -> Iterator[Job]:
        """
        Scrapes job listings from a LinkedIn search URL.

        Args:
            search_url: The URL of the LinkedIn job search results page.

        Yields:
            A Job object for each successfully scraped job posting.
        """
        logging.info(f"Navigating to search URL: {search_url}")
        self.driver.get(search_url)
        self._mask_automation_properties()

        # Check if we need to log in by looking for a sign-in modal or button
        if self._check_for_signin_modal():
            logging.info("Sign-in modal detected. Attempting to authenticate...")
            if not self.authenticate():
                logging.error("Authentication failed. Cannot continue scraping.")
                self._send_auth_failure_notification("Failed to log in with email/password.")
                return [] # Stop scraping if authentication fails
            
            # After successful login, re-navigate to the search URL
            logging.info("Authentication successful. Returning to search page...")
            self.driver.get(search_url)
            self._reapply_stealth_javascript()

        # Additional check after re-navigation
        if self._check_for_signin_modal():
            logging.error("Still seeing sign-in modal after authentication. Login may have failed.")
            self._send_auth_failure_notification("Sign-in modal still present after login attempt.")
            return []

        # Use streamlined approach to get all jobs from the table directly
        print("Looking for job elements using optimized path...")
        
        # Primary selector that we know works best
        primary_selector = ".job-card-container"
        
        # Single fallback for when primary doesn't work
        fallback_selector = ".artdeco-list li"
        
        working_selector = None
        all_job_elements = []
        
        # Try primary selector first
        try:
            job_elements = self.driver.find_elements(By.CSS_SELECTOR, primary_selector)
            
            if job_elements:
                working_selector = primary_selector
                all_job_elements = job_elements
                print(f"✅ Found {len(job_elements)} jobs with primary selector: {primary_selector}")
            else:
                print(f"Primary selector found no elements")
        except Exception as e:
            print(f"Primary selector failed: {e}")
        
        # Try fallback if primary didn't work
        if not working_selector:
            try:
                job_elements = self.driver.find_elements(By.CSS_SELECTOR, fallback_selector)
                
                if job_elements:
                    working_selector = fallback_selector
                    all_job_elements = job_elements
                    print(f"✅ Found {len(job_elements)} jobs with fallback selector: {fallback_selector}")
                else:
                    print(f"Fallback selector found no elements")
            except Exception as e:
                print(f"Fallback selector failed: {e}")
        
        if not working_selector or not all_job_elements:
            print("❌ Could not find any job elements.")
            return
            
        print(f"Using working selector: {working_selector}")
        print(f"Processing {len(all_job_elements)} jobs from the job table...")
        
        # Process each job exactly once
        processed_job_urls = set()  # Track processed jobs to avoid duplicates
        jobs_found_count = 0
        
        for index in range(len(all_job_elements)):
            try:
                # Re-fetch the list on each iteration to avoid stale elements
                fresh_job_list = self.driver.find_elements(By.CSS_SELECTOR, working_selector)
                if index >= len(fresh_job_list):
                    print(f"Job index {index} out of bounds, breaking loop.")
                    break
                
                job_to_click = fresh_job_list[index]
                
                # Scroll the job into view and click it to open detail panel
                print(f"Processing job {index + 1}/{len(all_job_elements)}...")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", job_to_click)
                time.sleep(0.5)  # Brief pause for scrolling
                job_to_click.click()
                time.sleep(2)  # Wait for detail panel to load

                # Scrape job details from the opened detail panel
                job_details = self._get_job_details_from_panel(search_url)
                if job_details and job_details.url not in processed_job_urls:
                    processed_job_urls.add(job_details.url)
                    jobs_found_count += 1
                    yield job_details
                elif job_details:
                    print(f"Skipping duplicate job: {job_details.title}")

            except ElementClickInterceptedException:
                print(f"Could not click job at index {index}, it was obscured. Skipping.")
                continue
            except InvalidSessionIdException:
                print("Browser session became invalid. Ending scraping for this URL.")
                break
            except Exception as e:
                print(f"An error occurred while processing job index {index}: {e}")
                continue
        
        print(f"Job processing complete. Found {jobs_found_count} unique jobs total.")

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
            
            print(f"✅ Scraped: {title} at {company}")
            
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
    
    def _send_auth_failure_notification(self, failure_reason: str):
        """Send a Telegram notification when authentication fails."""
        if self.notifier:
            try:
                message = f"🚨 **LinkedIn Authentication Failed** 🚨\n\n"
                message += f"**Reason:** {failure_reason}\n\n"
                message += f"**Action Required:** Please update the cookies.json file\n\n"
                message += f"**Steps:**\n"
                message += f"1. Log into LinkedIn manually in your browser\n"
                message += f"2. Export fresh cookies using the browser extension\n"
                message += f"3. Replace the cookies.json file in the repository\n\n"
                message += f"**Time:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
                
                print("Sending authentication failure notification via Telegram...")
                self.notifier.send_message(message)
                print("✅ Telegram notification sent successfully")
            except Exception as e:
                print(f"❌ Failed to send Telegram notification: {e}")
        else:
            print("⚠️ No notifier configured - cannot send authentication failure alert")


if __name__ == '__main__':
    # This block is for direct execution of the scraper for testing purposes.
    # It sets up the driver and calls the scraping method.
    pass 