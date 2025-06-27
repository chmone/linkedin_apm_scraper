from abc import ABC, abstractmethod
from typing import List
# We will define the Job data structure in a separate file
# from .models import Job 

class Scraper(ABC):
    """
    Abstract base class for all scrapers.
    Defines the common interface for scraping job data.
    """

    @abstractmethod
    def scrape(self) -> List: # List[Job]
        """
        The core method to perform the scraping.
        This should be implemented by all concrete scraper classes.

        Returns:
            A list of Job data objects.
        """
        pass 