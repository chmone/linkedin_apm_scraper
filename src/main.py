# This is the main orchestrator for the AI Job Scraper.

import logging
import time

from config.config import Config
from scraper.linkedin_scraper import LinkedInScraper
from agents.workflow import run_workflow
from notifier.telegram_notifier import TelegramNotifier

def main():
    """
    Main function to run the job scraping and processing workflow.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        # Get configuration
        config = Config.get_instance()

        # 1. Scrape Jobs
        logging.info("Starting job scraping...")
        print("Initializing scraper...")
        scraper = LinkedInScraper(config.search_urls, config.cookies_file)
        print("Scraping jobs from LinkedIn...")
        scraped_jobs = scraper.scrape()
        print(f"Found {len(scraped_jobs)} jobs.")

        if not scraped_jobs:
            logging.info("No new jobs found. Exiting.")
            return

        # 2. Run Agentic Workflow
        logging.info(f"Passing {len(scraped_jobs)} jobs to the agent workflow...")
        final_messages = run_workflow(scraped_jobs, config)

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

if __name__ == "__main__":
    main() 