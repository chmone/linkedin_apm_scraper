from abc import ABC, abstractmethod
from typing import List, Iterator
# We will define the Job data structure in a separate file
from .models import Job 

class BaseScraper(ABC):
    """
    Abstract base class for all scrapers.
    Defines the common interface for scraping job data.
    """
    def __init__(self, driver):
        self.driver = driver

    @abstractmethod
    def scrape(self, url: str) -> Iterator[Job]:
        """
        The core method to perform the scraping.
        This should be implemented by all concrete scraper classes.

        Args:
            url: The URL to scrape.

        Returns:
            An iterator of Job data objects.
        """
        pass 