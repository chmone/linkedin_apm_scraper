from dataclasses import dataclass, field

@dataclass
class Job:
    """
    A data class to hold structured information about a job posting.
    """
    title: str
    company: str
    url: str
    description: str
    location: str = ""
    is_remote: bool = False 