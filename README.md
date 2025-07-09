# AI-Powered Job Scraper

An intelligent job scraping system that supports multiple job platforms and provides AI-powered content generation for job applications. The system can scrape job listings from various platforms, validate job fit using AI, and generate personalized resume suggestions and cover letters.

## Features

- **Multi-Platform Support**: Extensible architecture supporting LinkedIn (implemented) with easy addition of Indeed, Glassdoor, and other platforms
- **AI-Powered Validation**: Automatically validates job fit against your ideal job profile
- **Intelligent Content Generation**: Creates personalized resume suggestions and cover letters using AI
- **Automated Notifications**: Sends results via Telegram
- **Configurable**: Platform-specific settings for authentication, rate limiting, and scraping behavior
- **Docker Support**: Ready for deployment with Docker and GitHub Actions
- **Extensible**: Factory pattern for easy addition of new job platforms

## Architecture

```
src/
├── main.py                 # Main orchestrator
├── config/
│   └── config.py          # Configuration management with multi-platform support
├── scraper/
│   ├── base.py           # Abstract base scraper interface
│   ├── factory.py        # Scraper factory for dynamic platform selection
│   ├── linkedin_scraper.py  # LinkedIn-specific implementation
│   └── models.py         # Job data models
├── agents/
│   ├── workflow.py       # AI agent orchestration
│   ├── validation_agent.py   # Job fit validation
│   ├── generation_agent.py   # Content generation
│   └── review_agent.py   # Content quality review
└── notifier/
    └── telegram_notifier.py  # Notification service
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ai-powered-job-scraper
pip install -r requirements.txt
```

### 2. Configuration

#### Environment Variables
Create a `.env` file:

```env
# AI and Notifications
OPENROUTER_API_KEY=your_openrouter_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# LinkedIn Authentication (if using LinkedIn)
LINKEDIN_PASSWORD=your_linkedin_password

# General Settings
HEADLESS=true
```

#### Platform Configuration
Choose one of these methods:

**Option A: Use existing search_urls.txt (LinkedIn only)**
```
https://www.linkedin.com/jobs/search/?keywords=product%20manager&location=United%20States
```

**Option B: Use platforms.json (Multi-platform)**
```bash
cp platforms.json.example platforms.json
# Edit platforms.json to configure multiple platforms
```

### 3. Required Files

- `resume.json` - Your resume data in JSON format
- `ideal_job_profile.txt` - Description of your ideal job
- `writing_style_samples/` - Directory with writing samples for AI style matching
- `cookies.json` - Browser cookies for LinkedIn authentication (if using LinkedIn)

### 4. Run

```bash
# Local execution
python src/main.py

# Docker execution
docker compose up --build
```

## Platform Configuration

### Adding New Platforms

1. **Create a new scraper class** extending `BaseScraper`:

```python
from scraper.base import BaseScraper
from scraper.models import Job

class IndeedScraper(BaseScraper):
    def authenticate(self) -> bool:
        # Implement platform-specific authentication
        pass
        
    def scrape(self, url: str) -> Iterator[Job]:
        # Implement platform-specific scraping
        pass
        
    def validate_url(self, url: str) -> bool:
        return "indeed.com" in url
```

2. **Register the scraper** in `factory.py`:

```python
from scraper.factory import ScraperFactory
ScraperFactory.register_scraper('indeed', IndeedScraper)
ScraperFactory.register_url_pattern('indeed.com', 'indeed')
```

3. **Add platform configuration** to `platforms.json`:

```json
{
  "indeed": {
    "enabled": true,
    "search_urls": ["https://www.indeed.com/jobs?q=..."],
    "auth": {...},
    "scraper_settings": {...},
    "rate_limits": {...}
  }
}
```

### Platform Configuration Options

Each platform in `platforms.json` supports:

- `enabled` - Whether to scrape this platform
- `search_urls` - List of search URLs for this platform
- `auth` - Authentication settings (cookies, passwords, etc.)
- `scraper_settings` - Platform-specific scraper behavior
- `rate_limits` - Delays between requests and pages

## Job Data Model

The enhanced `Job` model supports:

```python
@dataclass
class Job:
    # Core fields (required)
    title: str
    company: str
    location: str
    description: str
    url: str
    
    # Metadata
    platform: str = ""
    search_url: str = ""
    scraped_at: datetime = field(default_factory=datetime.now)
    
    # Optional fields
    salary_range: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    # ... more optional fields
    
    # Platform-specific data
    platform_data: Dict[str, Any] = field(default_factory=dict)
```

## AI Workflow

1. **Job Validation**: AI determines if job matches your ideal profile
2. **Content Generation**: Creates tailored resume suggestions and cover letter
3. **Content Review**: AI reviews and refines generated content
4. **Notification**: Sends results via Telegram

## Docker Deployment

### Local Docker Deployment

```bash
# Create .env file with required variables
cp .env.example .env  # Edit with your values

# Run with Docker Compose
docker compose up --build
```

### GitHub Actions Deployment

The project includes automated deployment via GitHub Actions that runs every 3 hours.

**Required GitHub Secrets:**
- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token  
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID
- `LINKEDIN_PASSWORD` - Your LinkedIn password
- `COOKIES_JSON` - Your LinkedIn cookies (JSON format)

**Manual trigger:** Go to Actions tab → "LinkedIn Job Scraper" → "Run workflow"

The workflow:
- ✅ Runs in headless Chrome (no GUI)
- ✅ 30-minute timeout for reliability
- ✅ Automatic cleanup after execution
- ✅ Runs every 3 hours automatically

## Backward Compatibility

The refactored system maintains full backward compatibility:

- Existing `search_urls.txt` files continue to work
- LinkedIn-specific environment variables are still supported  
- All existing configuration methods work unchanged

## Contributing

1. Fork the repository
2. Create a feature branch for new platform support
3. Follow the platform integration pattern
4. Add tests for new scrapers
5. Update documentation

## License

[Add your license information here]

## Troubleshooting

### Common Issues

- **Authentication failures**: Update cookies.json or check credentials
- **No jobs found**: Verify search URLs and platform configuration
- **Rate limiting**: Adjust rate_limits in platform configuration
- **AI errors**: Check OPENROUTER_API_KEY and quota

### Debugging

Enable detailed logging by setting log level to DEBUG in main.py. 