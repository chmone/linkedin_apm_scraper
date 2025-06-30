from dataclasses import dataclass

@dataclass
class Job:
    """
    A data class to hold structured information about a job posting.
    """
    title: str
    company: str
    location: str
    description: str
    url: str
    search_url: str