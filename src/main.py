# This is the main orchestrator for the AI Job Scraper.

import logging
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

from config.config import Config
from scraper.linkedin_scraper import LinkedInScraper
from agents.workflow import run_workflow
from notifier.telegram_notifier import TelegramNotifier

def main():
    """
    Main function to run the job scraping and processing workflow.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    driver = None  # Initialize driver to None
    try:
        # Get configuration
        config = Config.get_instance()

        # Initialize WebDriver
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=chrome_options)

        # 1. Scrape Jobs
        logging.info("Starting job scraping...")
        scraper = LinkedInScraper(driver=driver, cookies_path=config.cookies_file)
        
        all_scraped_jobs = []
        for url in config.search_urls:
            if not url or not url.strip().startswith('http'):
                logging.warning(f"Skipping invalid or empty URL: {url}")
                continue
            
            logging.info(f"Scraping jobs from LinkedIn URL: {url}")
            # The scrape method is a generator, so we extend the list with its results
            scraped_jobs_iterator = scraper.scrape(url)
            all_scraped_jobs.extend(list(scraped_jobs_iterator))

        logging.info(f"Found a total of {len(all_scraped_jobs)} jobs.")

        if not all_scraped_jobs:
            logging.info("No new jobs found across all URLs. Exiting.")
            return

        # 2. Run Agentic Workflow
        logging.info(f"Passing {len(all_scraped_jobs)} jobs to the agent workflow...")
        final_messages = run_workflow(all_scraped_jobs, config)

        # 3. Send Notifications
        if final_messages:
            logging.info(f"Sending {len(final_messages)} new job notifications to Telegram...")
            notifier = TelegramNotifier(config)
            for message_group in final_messages:
                for message_part in message_group:
                    notifier.send_message(message_part)
                    time.sleep(1) # Small delay between parts of a single notification
        else:
            logging.info("No jobs passed the initial validation.")

        print("AI Job Scraper finished successfully.")
    except Exception as e:
        logging.error(f"An error occurred in the main workflow: {e}", exc_info=True)
    finally:
        if driver:
            logging.info("Closing the WebDriver.")
            driver.quit()

if __name__ == "__main__":
    main() 