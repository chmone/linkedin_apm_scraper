# This is the main orchestrator for the AI-Powered Job Scraper.

import time
import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from config.config import load_config
from scraper.factory import ScraperFactory
from agents.workflow import run_workflow
from notifier.telegram_notifier import TelegramNotifier

def setup_chrome_driver(headless: bool = True) -> webdriver.Chrome:
    """
    Set up and return a configured Chrome WebDriver instance.
    Optimized for Docker/container environments without user-data-dir conflicts.
    """
    
    # Clean up any existing chrome processes  
    try:
        import subprocess
        subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, text=True)
        subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True, text=True)
    except Exception:
        pass

    chrome_options = Options()
    
    # Check for minimal configuration mode
    use_minimal = os.getenv('CHROME_MINIMAL_CONFIG', 'false').lower() == 'true'
    
    if use_minimal:
        # Minimal configuration for Docker/container environments
        chrome_options.add_argument("--headless=new") if headless else None
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        # No user-data-dir to avoid Docker conflicts - let Chrome manage its own profile
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--disable-default-apps")
    else:
        # Full configuration for production use
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
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-background-downloads")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        # No user-data-dir to avoid Docker conflicts - let Chrome manage its own profile
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-service-autorun")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--password-store=basic")
        chrome_options.add_argument("--use-mock-keychain")
        chrome_options.add_argument("--disable-component-update")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-sync")
        
        # Performance and stability options
        chrome_options.add_argument("--max_old_space_size=4096")
        chrome_options.add_argument("--disable-impl-side-painting")
        chrome_options.add_argument("--disable-skia-runtime-opts")
        chrome_options.add_argument("--disable-accelerated-2d-canvas")
        chrome_options.add_argument("--disable-accelerated-jpeg-decoding")
        chrome_options.add_argument("--disable-accelerated-mjpeg-decode")
        chrome_options.add_argument("--disable-accelerated-video-decode")
        chrome_options.add_argument("--disable-accelerated-video-encode")

    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        return driver
        
    except Exception as e:
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
    import os
    
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
            driver.quit()


if __name__ == '__main__':
    main() 