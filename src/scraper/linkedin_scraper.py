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

    def __init__(self, driver: webdriver.Chrome, platform_config=None, cookies_path: str = "cookies.json", 
                 linkedin_email: str = None, linkedin_password: str = None, notifier=None, **kwargs):
        super().__init__(driver, platform_config, **kwargs)
        self.cookies_path = cookies_path
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
        Perform LinkedIn-specific authentication using cookies and password.
        Returns True if authentication was successful, False otherwise.
        """
        return self._attempt_login()
    
    def authenticate_proactively(self) -> bool:
        """
        Proactively authenticate before starting to scrape jobs.
        This is called once at the beginning to ensure we're logged in.
        
        Follows the user's required flow:
        1. Try to inject cookies
        2. If "Welcome back" screen with profile, enter password  
        3. If email field present, enter email + password
        
        Returns True if authentication was successful, False otherwise.
        """
        print("🔐 Starting proactive LinkedIn authentication...")
        
        try:
            # First, check if we're already logged in by going to LinkedIn feed
            print("Checking if already logged in...")
            self.driver.get("https://www.linkedin.com/feed")
            self._mask_automation_properties()
            time.sleep(3)
            
            # Check if we're already logged in (no sign-in prompts on feed)
            if self._is_logged_in():
                print("✅ Already logged in! No authentication needed.")
                return True
            
            # Not logged in, proceed with authentication flow
            print("Not logged in. Starting authentication process...")
            
            # Step 1: Try to inject cookies first
            success = self._try_cookie_authentication()
            if success:
                print("✅ Cookie authentication successful!")
                return True
            
            # Step 2: If cookies didn't work, try fresh login flow
            print("Cookie authentication failed. Attempting fresh login...")
            success = self._try_fresh_login()
            if success:
                print("✅ Fresh login successful!")
                return True
                
            print("❌ All authentication methods failed.")
            return False
            
        except Exception as e:
            print(f"❌ Error during proactive authentication: {e}")
            return False
    
    def _is_logged_in(self) -> bool:
        """
        Check if we're currently logged in to LinkedIn.
        Returns True if logged in, False otherwise.
        """
        try:
            # Check for multiple indicators of being logged in
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()
            
            # Look for login indicators - if we see these, we're NOT logged in
            login_indicators = [
                "sign in",
                "log in", 
                "session_key",
                "session_password",
                "join now",
                "welcome back"
            ]
            
            # Look for logged-in indicators
            logged_in_indicators = [
                "global-nav-search",  # Search bar in nav
                "messaging-", # LinkedIn messaging features
                "artdeco-button--premium",  # Premium button
                "profile-photo-edit", # Profile photo edit
                "feed-nav-item", # Feed navigation
                '"me":', # JSON data indicating profile
                "global-nav__primary-item" # Primary navigation items
            ]
            
            # Check URL patterns that indicate login status
            if any(pattern in current_url.lower() for pattern in ["login", "checkpoint", "challenge", "uas/login"]):
                print("❌ On login/challenge page - not logged in")
                return False
            
            if any(pattern in current_url.lower() for pattern in ["feed", "in/", "mynetwork", "jobs", "me/"]):
                # On a logged-in page, but double-check content
                logged_in_content_found = any(indicator in page_source for indicator in logged_in_indicators)
                login_content_found = any(indicator in page_source for indicator in login_indicators)
                
                if logged_in_content_found and not login_content_found:
                    print("✅ Confirmed logged in based on URL and page content")
                    return True
                elif login_content_found:
                    print("❌ Login forms detected - not properly logged in")
                    return False
            
            # Fallback: Look for navigation elements that only appear when logged in
            try:
                # Try to find the main LinkedIn navigation - this only appears when logged in
                nav_elements = self.driver.find_elements(By.CSS_SELECTOR, ".global-nav__primary-items, .global-nav__nav, [data-control-name='nav.homepage']")
                if nav_elements and any(elem.is_displayed() for elem in nav_elements):
                    print("✅ Found navigation elements - likely logged in")
                    return True
            except Exception:
                pass
            
            print("❌ Could not confirm login status - assuming not logged in")
            return False
            
        except Exception as e:
            print(f"Error checking login status: {e}")
            return False
    
    def _try_cookie_authentication(self) -> bool:
        """
        Try to authenticate using saved cookies.
        Returns True if successful, False otherwise.
        """
        try:
            print("Attempting cookie authentication...")
            
            # Navigate to login page to inject cookies
            self.driver.get("https://www.linkedin.com/login")
            self._reapply_stealth_javascript()
            time.sleep(2)
            
            # Load and inject cookies
            try:
                with open(self.cookies_path, "r") as f:
                    cookies = json.load(f)
                
                print(f"Loading {len(cookies)} cookies...")
                for cookie in cookies:
                    # Sanitize the 'sameSite' attribute if it's invalid
                    if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                        del cookie['sameSite']
                    self.driver.add_cookie(cookie)
                
                print("Cookies loaded. Refreshing page...")
                self.driver.refresh()
                time.sleep(3)
                
                # Check if we're now on welcome back screen or logged in
                if self._check_for_welcome_back_screen():
                    print("Welcome back screen detected. Completing password login...")
                    return self._complete_password_login()
                elif self._is_logged_in():
                    print("Cookies successful - already logged in!")
                    return True
                else:
                    print("Cookies loaded but still not logged in")
                    return False
                    
            except FileNotFoundError:
                print(f"Cookie file not found at '{self.cookies_path}'")
                return False
            except json.JSONDecodeError:
                print("Invalid JSON in cookie file")
                return False
                
        except Exception as e:
            print(f"Error during cookie authentication: {e}")
            return False
    
    def _try_fresh_login(self) -> bool:
        """
        Try fresh login with email and password.
        Handles both welcome back screen and fresh email entry.
        Returns True if successful, False otherwise.
        """
        try:
            if not self.linkedin_email or not self.linkedin_password:
                print("❌ Email or password not provided. Cannot perform fresh login.")
                print(f"Email provided: {bool(self.linkedin_email)}")
                print(f"Password provided: {bool(self.linkedin_password)}")
                return False
            
            print("Attempting fresh login with email and password...")
            
            # Navigate to login page
            self.driver.get("https://www.linkedin.com/login")
            self._reapply_stealth_javascript()
            time.sleep(2)
            
            # Check what type of login screen we're on
            if self._check_for_welcome_back_screen():
                print("On welcome back screen - entering password only...")
                return self._complete_password_login()
            else:
                print("On fresh login screen - entering email and password...")
                return self._complete_fresh_login()
                
        except Exception as e:
            print(f"Error during fresh login: {e}")
            return False
    
    def _complete_fresh_login(self) -> bool:
        """
        Complete fresh login by entering email and password.
        Returns True if successful, False otherwise.
        """
        try:
            # Find and fill email field
            email_selectors = [
                "input[name='session_key']",
                "input[id='username']", 
                "input[type='email']",
                "input[autocomplete='username']"
            ]
            
            email_field = None
            for selector in email_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            email_field = element
                            break
                    if email_field:
                        break
                except Exception:
                    continue
            
            if not email_field:
                print("❌ Could not find email field")
                return False
            
            print("Found email field. Entering email...")
            email_field.clear()
            email_field.send_keys(self.linkedin_email)
            time.sleep(1)
            
            # Find and fill password field
            password_selectors = [
                "input[name='session_password']",
                "input[id='password']",
                "input[type='password']"
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
                print("❌ Could not find password field")
                return False
            
            print("Found password field. Entering password...")
            password_field.clear()
            password_field.send_keys(self.linkedin_password)
            time.sleep(1)
            
            # Find and click sign in button
            signin_selectors = [
                "button[data-litms-control-urn='login-submit']",
                "button[type='submit']",
                ".login__form_action_container button",
                "input[type='submit']",
                "button:contains('Sign in')"
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
                print("❌ Could not find sign in button")
                return False
            
            print("Found sign in button. Clicking to login...")
            signin_button.click()
            time.sleep(5)  # Wait longer for login processing
            
            # Check if login was successful
            if self._is_logged_in():
                print("✅ Fresh login successful!")
                return True
            else:
                current_url = self.driver.current_url
                if "challenge" in current_url or "checkpoint" in current_url:
                    print("⚠️ Login requires additional verification (CAPTCHA/2FA)")
                    return False
                else:
                    print("❌ Fresh login failed - still not logged in")
                    return False
                    
        except Exception as e:
            print(f"Error completing fresh login: {e}")
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
        # Perform proactive authentication before starting to scrape
        print("🔐 Performing proactive authentication before scraping...")
        auth_success = self.authenticate_proactively()
        if not auth_success:
            print("❌ Proactive authentication failed. Cannot proceed with job scraping.")
            self._send_auth_failure_notification("Proactive authentication failed")
            return
        
        print(f"Navigating to search URL: {search_url}")
        self.driver.get(search_url)
        
        # Apply JavaScript masking for this page
        self._mask_automation_properties()
        
        # Verify we're still authenticated after visiting the search URL
        print("🔍 Verifying authentication after visiting search URL...")
        time.sleep(2)  # Give page time to load
        
        # Check for sign-in modal - if detected, try to authenticate again
        if self._check_for_signin_modal():
            print("⚠️ Sign-in modal detected after visiting search URL. Attempting re-authentication...")
            
            # Try authentication one more time
            success = self._attempt_login()
            if not success:
                print("❌ Re-authentication failed. Cannot proceed with job scraping.")
                self._send_auth_failure_notification("Re-authentication after visiting search URL failed")
                return
            
            # Navigate back to search URL after successful re-authentication
            print("✅ Re-authentication successful. Returning to search page...")
            self.driver.get(search_url)
            self._reapply_stealth_javascript()
            
            # Final check for sign-in modal
            if self._check_for_signin_modal():
                print("❌ Still seeing sign-in modal after re-authentication. Login may have failed.")
                self._send_auth_failure_notification("Sign-in modal still present after re-authentication")
                return
        else:
            print("✅ No sign-in modal detected. Authentication verified.")

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