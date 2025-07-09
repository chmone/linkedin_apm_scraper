# This is the main orchestrator for the AI-Powered Job Scraper.

import logging
import time

from config.config import load_config
from scraper.factory import ScraperFactory
from agents.workflow import run_workflow
from notifier.telegram_notifier import TelegramNotifier

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def setup_chrome_driver(headless: bool = True) -> webdriver.Chrome:
    """
    Set up and configure a Chrome WebDriver.

    Args:
        headless: Whether to run in headless mode.

    Returns:
        Configured Chrome WebDriver instance.
    """
    import os
    import tempfile
    import shutil
    
    # Create a unique temporary directory for this Chrome instance
    temp_dir = tempfile.mkdtemp(prefix='chrome_')
    
    # Ensure clean environment by killing any existing Chrome processes
    os.system("pkill -f chrome || true")
    os.system("pkill -f chromium || true")
    
    chrome_options = Options()
    
    # Essential Chrome options for containerized environment
    chrome_options.add_argument("--headless") if headless else None
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-crash-reporter")
    chrome_options.add_argument("--disable-oopr-debug-crash-dump")
    chrome_options.add_argument("--no-crash-upload")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-low-res-tiling")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--silent")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Explicitly set user data directory to our temp directory
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    chrome_options.add_argument(f"--data-path={temp_dir}")
    chrome_options.add_argument(f"--disk-cache-dir={temp_dir}/cache")
    
    # Additional stability options
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-service-autorun")
    chrome_options.add_argument("--password-store=basic")
    chrome_options.add_argument("--use-mock-keychain")
    chrome_options.add_argument("--disable-component-update")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--no-default-browser-check")
    
    # Stealth options
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    try:
        # Check Chrome and ChromeDriver versions for debugging
        import subprocess
        import os
        
        # Get Chrome version
        try:
            chrome_version = subprocess.check_output(['google-chrome', '--version'], text=True).strip()
            print(f"Chrome version: {chrome_version}")
        except Exception as e:
            print(f"Could not get Chrome version: {e}")
        
        # Check if our installed ChromeDriver exists and get its version
        chromedriver_path = '/usr/local/bin/chromedriver'
        if os.path.exists(chromedriver_path):
            try:
                chromedriver_version = subprocess.check_output([chromedriver_path, '--version'], text=True).strip()
                print(f"ChromeDriver version: {chromedriver_version}")
                service = Service(executable_path=chromedriver_path)
            except Exception as e:
                print(f"Could not get ChromeDriver version: {e}")
                service = Service()  # Fall back to Selenium Manager
        else:
            print("No ChromeDriver at /usr/local/bin/chromedriver, using Selenium Manager")
            service = Service()
        
        # Disable telemetry
        os.environ['SE_AVOID_STATS'] = 'true'
        
        print(f"Creating Chrome driver for temp directory: {temp_dir}")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Store temp directory for cleanup later
        driver._temp_dir = temp_dir
        
        return driver
    except Exception as e:
        # Clean up temp directory if driver creation fails
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise e


def scrape_platform_jobs(driver: webdriver.Chrome, platform_name: str, urls: list[str], config, notifier) -> list:
    """
    Scrape jobs from a specific platform using the appropriate scraper.
    
    Args:
        driver: WebDriver instance
        platform_name: Name of the platform to scrape
        urls: List of URLs to scrape from this platform
        config: Configuration object
        notifier: Notification service
        
    Returns:
        List of scraped jobs
    """
    all_jobs = []
    
    # Get platform configuration
    platform_config = config.get_platform_config(platform_name)
    if not platform_config:
        logging.warning(f"No configuration found for platform: {platform_name}")
        return all_jobs
    
    # Create platform-specific scraper using factory
    scraper_kwargs = {}
    if platform_name == 'linkedin':
        # LinkedIn-specific arguments for backward compatibility
        scraper_kwargs.update({
            'cookies_path': platform_config.get_auth_setting('cookies_path', 'cookies.json'),
            'linkedin_password': platform_config.get_auth_setting('password'),
            'notifier': notifier
        })
    
    scraper = ScraperFactory.create_scraper(
        driver=driver,
        platform_name=platform_name,
        config=config,
        **scraper_kwargs
    )
    
    if not scraper:
        logging.error(f"Failed to create scraper for platform: {platform_name}")
        return all_jobs
    
    logging.info(f"Starting to scrape {len(urls)} URLs from {platform_name}")
    
    # Scrape jobs from each URL for this platform
    for url in urls:
        logging.info(f"Scraping jobs from {platform_name} URL: {url}")
        try:
            # Validate URL for this platform
            if not scraper.validate_url(url):
                logging.warning(f"URL {url} is not valid for platform {platform_name}")
                continue
                
            jobs_from_url = list(scraper.scrape(url))
            all_jobs.extend(jobs_from_url)
            
            logging.info(f"Found {len(jobs_from_url)} jobs from {url}")
            
            # Add delay between URLs to avoid rate limiting
            if len(urls) > 1:
                delay = platform_config.rate_limit_config.get('page_delay', 5)
                time.sleep(delay)
                
        except Exception as e:
            logging.error(f"Failed to scrape from {url}: {e}", exc_info=True)
    
    logging.info(f"Completed scraping {platform_name}. Found {len(all_jobs)} total jobs.")
    return all_jobs


def main():
    """
    The main function to run the AI-Powered Job Scraper with multi-platform support.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config()
    
    # Set up WebDriver
    driver = setup_chrome_driver(headless=config.headless)
    
    try:
        # Set up notification service
        notifier = TelegramNotifier(config)
        
        # Get all URLs grouped by platform
        all_urls = config.get_all_search_urls()
        if not all_urls:
            logging.warning("No search URLs configured. Please check your configuration.")
            return
        
        # Group URLs by platform
        platform_urls = {}
        for url, platform_name in all_urls:
            if platform_name not in platform_urls:
                platform_urls[platform_name] = []
            platform_urls[platform_name].append(url)
        
        logging.info(f"Starting job scraping across {len(platform_urls)} platforms...")
        
        # Scrape jobs from each platform
        all_jobs = []
        for platform_name, urls in platform_urls.items():
            logging.info(f"Processing platform: {platform_name}")
            
            platform_jobs = scrape_platform_jobs(driver, platform_name, urls, config, notifier)
            all_jobs.extend(platform_jobs)
            
            # Add delay between platforms to avoid overwhelming any single platform
            if len(platform_urls) > 1:
                time.sleep(5)

        if not all_jobs:
            logging.info("No new jobs were scraped from any platform.")
        else:
            logging.info(f"Scraped a total of {len(all_jobs)} jobs across all platforms. Starting AI workflow...")
            
            # Process each job through the AI workflow
            for job in all_jobs:
                logging.info(f"Processing job: {job.title} at {job.company} ({job.platform})")
                
                message_groups = run_workflow(job, config)
                if message_groups:
                    for group in message_groups:
                        for message in group:
                            notifier.send_message(message)
                            time.sleep(1)  # Small delay between parts of the message
                        # Add a delay between notifications to avoid rate limiting
                        time.sleep(5)

        print("AI-Powered Job Scraper finished successfully.")
        
    except Exception as e:
        logging.error(f"An error occurred in the main workflow: {e}", exc_info=True)
    finally:
        logging.info("Closing the WebDriver.")
        if driver:
            # Clean up temporary directory if it exists
            if hasattr(driver, '_temp_dir'):
                import shutil
                temp_dir = driver._temp_dir
                driver.quit()
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logging.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logging.warning(f"Failed to cleanup temp directory: {e}")
            else:
                driver.quit()


if __name__ == '__main__':
    main() 