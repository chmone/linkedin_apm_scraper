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

    def __init__(self, driver: webdriver.Chrome, cookies_path: str = "cookies.json", linkedin_password: str = None):
        super().__init__(driver)
        self.cookies_path = cookies_path
        self.linkedin_password = linkedin_password
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
    
    def _attempt_login(self) -> bool:
        """
        Attempt to authenticate by loading cookies when we detect we need login.
        Returns True if authentication appears successful, False otherwise.
        """
        try:
            print("Loading cookies for authentication...")
            
            # Navigate to the signin page first - this is where authentication context is most appropriate
            print("Navigating to LinkedIn signin page to inject cookies...")
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(2)  # Allow page to fully load
            
            # Apply stealth JavaScript on login page
            self._reapply_stealth_javascript()
            
            with open(self.cookies_path, "r") as f:
                cookies = json.load(f)
            
            print(f"Loading {len(cookies)} cookies...")
            for cookie in cookies:
                # Sanitize the 'sameSite' attribute if it's invalid.
                # Some browser extensions export this with values Selenium doesn't recognize.
                if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                    del cookie['sameSite']
                self.driver.add_cookie(cookie)
            
            print("Successfully loaded session cookies.")
            
            # After loading cookies, wait for page to refresh and show the "Welcome back" screen
            print("Waiting for page to refresh to show Welcome back screen...")
            time.sleep(2)  # Give time for cookies to process
            
            # Refresh the page to ensure cookies take effect
            self.driver.refresh()
            time.sleep(1)  # Wait for refresh to complete
            
            # Wait for the Welcome back screen to appear
            welcome_back_detected = self._wait_for_welcome_back_screen(timeout=10)
            
            if welcome_back_detected:
                print("Detected 'Welcome back' screen. Completing login with password...")
                
                if not self.linkedin_password:
                    print("Error: LinkedIn password not provided in environment variables.")
                    return False
                
                # Complete the login by filling password and clicking sign in
                login_success = self._complete_password_login()
                if not login_success:
                    print("Failed to complete password login.")
                    return False
                
                print("Password login completed successfully! Authentication complete.")
                return True
            else:
                print("No 'Welcome back' screen detected. May already be fully logged in.")
                return True
                
        except FileNotFoundError:
            print(f"Cookie file not found at '{self.cookies_path}'. Cannot authenticate.")
            return False
        except Exception as e:
            print(f"An error occurred during authentication: {e}")
            return False
    
    def _check_for_welcome_back_screen(self) -> bool:
        """
        Check if we're on the 'Welcome back' screen that requires password completion.
        Returns True ONLY if we're on the specific welcome back screen with the user's name.
        """
        try:
            print("Checking for Welcome back screen...")
            
            # First, look for the specific "Welcome back" heading text
            welcome_text_selectors = [
                "//h1[contains(text(), 'Welcome back')]",
                "//*[contains(text(), 'Welcome back')]"
            ]
            
            welcome_text_found = False
            for selector in welcome_text_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements and any(elem.is_displayed() for elem in elements):
                        print(f"Welcome back text found using selector: {selector}")
                        welcome_text_found = True
                        break
                except Exception:
                    continue
            
            # Only if we found "Welcome back" text, then check for password field
            if welcome_text_found:
                password_selectors = [
                    "input[name='session_password']",
                    "input[type='password']",
                    "#password"
                ]
                
                for selector in password_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements and any(elem.is_displayed() for elem in elements):
                            print(f"Welcome back screen confirmed - password field found: {selector}")
                            return True
                    except Exception:
                        continue
                
                print("Welcome back text found but no password field - may already be logged in")
                return False
            else:
                print("No 'Welcome back' text found - not on welcome back screen")
                return False
                
        except Exception as e:
            print(f"Error checking for welcome back screen: {e}")
            return False
    
    def _wait_for_welcome_back_screen(self, timeout: int = 15) -> bool:
        """
        Wait for the Welcome back screen to appear after loading cookies.
        Returns True if welcome back screen appears, False if timeout.
        """
        print(f"Waiting up to {timeout} seconds for Welcome back screen to appear...")
        
        for attempt in range(timeout):
            if self._check_for_welcome_back_screen():
                return True
            time.sleep(1)
        
        print("Timeout waiting for Welcome back screen.")
        return False
    
    def _complete_password_login(self) -> bool:
        """
        Complete the login process by filling in the password and clicking sign in.
        Returns True if login appears successful, False otherwise.
        """
        try:
            # Find and fill the password field
            password_selectors = [
                "input[name='session_password']",
                "input[type='password']",
                "#password",
                "input[id*='password']"
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            password_field = element
                            break
                    if password_field:
                        break
                except Exception:
                    continue
            
            if not password_field:
                print("Could not find password field.")
                return False
            
            print("Found password field. Filling in password...")
            password_field.clear()
            password_field.send_keys(self.linkedin_password)
            time.sleep(1)
            
            # Find and click the sign in button
            signin_selectors = [
                "button[data-litms-control-urn='login-submit']",
                "button[type='submit']",
                "button:contains('Sign in')",
                ".login__form_action_container button",
                "input[type='submit']"
            ]
            
            signin_button = None
            for selector in signin_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            signin_button = element
                            break
                    if signin_button:
                        break
                except Exception:
                    continue
            
            if not signin_button:
                print("Could not find sign in button.")
                return False
            
            print("Found sign in button. Clicking to complete login...")
            signin_button.click()
            time.sleep(3)  # Wait for LinkedIn to process login
            
            # Check if login was successful by looking at the current URL and page content
            current_url = self.driver.current_url
            print(f"Current URL after login attempt: {current_url}")
            
            # Check for login success indicators
            if "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                print("✅ Login successful - redirected to feed or profile!")
                return True
            elif "linkedin.com/login" in current_url or "linkedin.com/uas/login" in current_url:
                print("❌ Login failed - still on login page")
                return False
            elif "challenge" in current_url or "checkpoint" in current_url:
                print("⚠️  Login requires additional verification (CAPTCHA/email)")
                return False
            else:
                # Check page content for success/failure indicators
                page_text = self.driver.page_source.lower()
                if "welcome back" in page_text and "password" in page_text:
                    print("❌ Still on welcome back screen - login may have failed")
                    return False
                elif "feed" in page_text or "home" in page_text:
                    print("✅ Login appears successful based on page content")
                    return True
                else:
                    print(f"⚠️  Uncertain login status. Current URL: {current_url}")
                    return False
            
        except Exception as e:
            print(f"Error completing password login: {e}")
            return False

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
            print(f"An error occurred while loading cookies: {e}")

    def scrape(self, search_url: str) -> Iterator[Job]:
        """
        Scrapes a LinkedIn job search URL by clicking each job and extracting details from the side panel.

        Args:
            search_url: The URL of the LinkedIn job search results page.

        Yields:
            A Job object for each successfully scraped job posting.
        """
        print(f"Navigating to search URL: {search_url}")
        self.driver.get(search_url)
        
        # Apply JavaScript masking for this page
        self._mask_automation_properties()

        # Check for sign-in modal - if detected, attempt login
        if self._check_for_signin_modal():
            print("Sign-in modal detected. Attempting to authenticate...")
            
            # Attempt to load cookies and authenticate
            success = self._attempt_login()
            if not success:
                print("Authentication failed. Cannot proceed with job scraping.")
                self.driver.save_screenshot("signin_modal_detected.png")
                print("Debug screenshot saved: signin_modal_detected.png")
                return
            
            # Navigate back to search URL after successful authentication
            print("Authentication successful. Returning to search page...")
            self.driver.get(search_url)
            self._reapply_stealth_javascript()
            
            # Check one more time if we're properly authenticated
            if self._check_for_signin_modal():
                print("Still seeing sign-in modal after authentication. Login may have failed.")
                self.driver.save_screenshot("signin_modal_after_auth.png")
                print("Debug screenshot saved: signin_modal_after_auth.png")
                return

        # Focus on the job search results list container to find only visible jobs
        print("Looking for job search results container...")
        
        # Wait for the main job results container
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-search-results-list")))
            print("✅ Job search results container found")
        except TimeoutException:
            print("❌ Could not find job search results container. Taking screenshot for debugging...")
            self.driver.save_screenshot("no_job_container_found.png")
            print("Debug screenshot saved: no_job_container_found.png")
            return

        # Target selectors specifically within the visible job search results area
        job_container_selectors = [
            ".jobs-search-results-list .job-card-container",  # Jobs within the search results list
            ".jobs-search-results-list .job-search-card", 
            ".jobs-search-results-list li",  # Generic list items in job results
            ".scaffold-layout__list-container .job-card-container",  # Alternative structure
        ]
        
        visible_job_elements = []
        working_selector = None
        
        for selector in job_container_selectors:
            try:
                print(f"Trying targeted selector: {selector}")
                job_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                # Filter for only visible elements (not hidden or off-screen)
                visible_elements = []
                for element in job_elements:
                    try:
                        if element.is_displayed() and element.size['height'] > 0 and element.size['width'] > 0:
                            # Additional check: is the element in the viewport?
                            location = element.location
                            size = element.size
                            if location['y'] >= 0 and (location['y'] + size['height']) <= self.driver.get_window_size()['height']:
                                visible_elements.append(element)
                    except Exception:
                        continue  # Skip elements that can't be checked
                
                if visible_elements:
                    visible_job_elements = visible_elements
                    working_selector = selector
                    print(f"✅ Found {len(visible_elements)} visible job elements using selector: {selector}")
                    break
                else:
                    print(f"❌ No visible jobs found with selector: {selector}")
                    
            except Exception as e:
                print(f"❌ Error with selector {selector}: {e}")
                continue
        
        if not visible_job_elements:
            print("❌ Could not find any visible job elements. Taking screenshot for debugging...")
            self.driver.save_screenshot("no_visible_jobs_found.png") 
            print("Debug screenshot saved: no_visible_jobs_found.png")
            return
            
        print(f"Found {len(visible_job_elements)} visible job items to process.")
        print(f"Using working selector: {working_selector}")
        
        # Implement dynamic scrolling approach to discover all available jobs
        processed_job_urls = set()  # Track processed jobs to avoid duplicates
        jobs_found_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 10  # Prevent infinite scrolling
        
        print("Starting dynamic job discovery with left sidebar scrolling...")
        
        while scroll_attempts < max_scroll_attempts:
            # Get currently visible jobs
            current_visible_jobs = self._get_current_visible_jobs(working_selector)
            
            if not current_visible_jobs:
                print("No visible jobs found in current view.")
                break
            
            print(f"Found {len(current_visible_jobs)} visible jobs in current view (scroll attempt {scroll_attempts + 1})")
            
            # Process each visible job
            new_jobs_found = False
            for job_index, job_element in enumerate(current_visible_jobs):
                try:
                    # Scroll the job into view and click it
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", job_element)
                    time.sleep(0.5)  # Brief pause for scrolling
                    job_element.click()
                    time.sleep(2)  # Wait for panel to load

                    job_details = self._get_job_details_from_panel(search_url)
                    if job_details and job_details.url not in processed_job_urls:
                        processed_job_urls.add(job_details.url)
                        jobs_found_count += 1
                        new_jobs_found = True
                        yield job_details

                except ElementClickInterceptedException:
                    print(f"Could not click job at position {job_index}, it was obscured. Skipping.")
                    continue
                except InvalidSessionIdException:
                    print("Browser session became invalid. Ending scraping for this URL.")
                    return
                except Exception as e:
                    print(f"An error occurred while processing job at position {job_index}: {e}")
                    continue
            
            # Try scrolling down in the left sidebar to load more jobs
            if new_jobs_found:
                print(f"Processed {jobs_found_count} unique jobs so far. Scrolling to find more...")
                self._scroll_job_list_down()
                time.sleep(2)  # Wait for new jobs to load
                scroll_attempts += 1
            else:
                print("No new jobs found in current view. Ending search.")
                break
        
        print(f"Job discovery complete. Found {jobs_found_count} unique jobs total.")
    
    def _get_current_visible_jobs(self, working_selector: str) -> list:
        """Get currently visible job elements in the viewport."""
        try:
            job_elements = self.driver.find_elements(By.CSS_SELECTOR, working_selector)
            visible_jobs = []
            
            for element in job_elements:
                try:
                    if element.is_displayed() and element.size['height'] > 0 and element.size['width'] > 0:
                        location = element.location
                        size = element.size
                        window_height = self.driver.get_window_size()['height']
                        
                        # Check if element is in viewport (at least partially visible)
                        if (location['y'] + size['height'] > 0 and 
                            location['y'] < window_height):
                            visible_jobs.append(element)
                except Exception:
                    continue
            
            return visible_jobs
        except Exception as e:
            print(f"Error getting visible jobs: {e}")
            return []
    
    def _scroll_job_list_down(self):
        """Scroll down in the job list container to load more jobs."""
        try:
            # Find the job list container and scroll it
            job_list_containers = [
                ".jobs-search-results-list",
                ".scaffold-layout__list-container", 
                ".job-search-results-list"
            ]
            
            for container_selector in job_list_containers:
                try:
                    container = self.driver.find_element(By.CSS_SELECTOR, container_selector)
                    # Scroll down within the container
                    self.driver.execute_script("arguments[0].scrollTop += 300;", container)
                    print(f"Scrolled down in container: {container_selector}")
                    return
                except NoSuchElementException:
                    continue
            
            # Fallback: scroll the entire page
            self.driver.execute_script("window.scrollBy(0, 300);")
            print("Scrolled page down as fallback")
            
        except Exception as e:
            print(f"Error scrolling job list: {e}")

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