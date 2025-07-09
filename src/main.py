# This is the main orchestrator for the AI-Powered Job Scraper.

import logging
import time
import uuid

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
    chrome_options = Options()
    
    # Essential Chrome options for containerized environment
    chrome_options.add_argument("--headless") if headless else None
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--log-level=3")
    
    # Create Chrome driver directly
    return webdriver.Chrome(options=chrome_options)


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
        driver.quit()


if __name__ == '__main__':
    main() 