import os
import json
import pytest
from unittest.mock import MagicMock, patch

from src.scraper.models import Job
from src.main import main
from src.config.config import Config
# We no longer need to import the real scraper
# from src.scraper.linkedin_scraper import LinkedInScraper 

@pytest.fixture
def test_config(tmp_path, monkeypatch):
    """
    Creates a temporary configuration for testing purposes.
    """
    # Create dummy config files
    (tmp_path / "search_urls.txt").write_text("dummy_url")
    (tmp_path / "cookies.json").write_text(json.dumps([{"name": "li_at", "value": "dummy"}]))
    (tmp_path / "resume.json").write_text(json.dumps({"experience": "Product Manager"}))
    (tmp_path / "ideal_job_profile.txt").write_text("An ideal job.")
    (tmp_path / "writing_style_samples").mkdir()
    (tmp_path / "writing_style_samples/sample1.txt").write_text("This is my writing style.")

    # Mock environment variables
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    # The Config class reads from the CWD, so we change it for the test.
    monkeypatch.chdir(tmp_path)

    # Since main() creates its own Config instance, we don't need to return one.
    # We just need the environment to be set up correctly.

def test_full_pipeline_with_mocks(test_config):
    """
    Tests the full pipeline from the main() entrypoint with mocked external services.
    - Mocks the LinkedInScraper to avoid network calls.
    - Mocks the generative AI models to avoid API calls and control output.
    - Mocks the TelegramNotifier to prevent sending actual messages.
    """
    # 1. Define mock data and return values
    mock_job_1 = Job(title="Associate Product Manager", company="Company A", url="http://example.com/1", description="Desc 1", location="Remote", platform="linkedin")
    mock_job_2 = Job(title="Product Manager", company="Company B", url="http://example.com/2", description="Desc 2", location="New York, NY", platform="linkedin")
    mock_jobs = [mock_job_1, mock_job_2]

    # 2. Set up patches for all external services
    with patch('src.scraper.factory.ScraperFactory.create_scraper') as MockScraperFactory, \
         patch('src.scraper.factory.ScraperFactory.validate_url_for_platform') as MockUrlValidator, \
         patch('src.agents.validation_agent.OpenAI') as MockValidatorClient, \
         patch('src.agents.generation_agent.OpenAI') as MockGeneratorClient, \
         patch('src.agents.review_agent.OpenAI') as MockReviewerClient, \
         patch('src.main.TelegramNotifier') as MockNotifier:

        # Configure the return values for each mock
        mock_scraper_instance = MagicMock()
        mock_scraper_instance.scrape.return_value = mock_jobs
        mock_scraper_instance.validate_url.return_value = True  # Always validate URLs
        MockScraperFactory.return_value = mock_scraper_instance
        MockUrlValidator.return_value = True  # Always validate URLs in factory too
        
        # Mock validation client to approve the first job and reject the second
        mock_validator_client = MockValidatorClient.return_value
        mock_validator_response1 = MagicMock()
        mock_validator_response1.choices[0].message.content = "YES"
        mock_validator_response2 = MagicMock()
        mock_validator_response2.choices[0].message.content = "NO"
        mock_validator_client.chat.completions.create.side_effect = [
            mock_validator_response1,
            mock_validator_response2
        ]

        # Mock generation client to return content for the approved job
        mock_generator_client = MockGeneratorClient.return_value
        mock_generator_response = MagicMock()
        mock_generator_response.choices[0].message.content = "Resume points---SPLIT---Cover letter"
        mock_generator_client.chat.completions.create.return_value = mock_generator_response

        # Mock review client to approve the generated content
        mock_reviewer_client = MockReviewerClient.return_value
        mock_reviewer_response = MagicMock()
        mock_reviewer_response.choices[0].message.content = "YES"
        mock_reviewer_client.chat.completions.create.return_value = mock_reviewer_response

        # Get a reference to the notifier instance for assertion
        notifier_instance = MockNotifier.return_value

        # 3. Run the main function
        main()

        # 4. Assert that the external services were called correctly
        mock_scraper_instance.scrape.assert_called()
        
        # Validator should be called for both jobs
        assert mock_validator_client.chat.completions.create.call_count == 2

        # Generator and Reviewer should only be called once for the approved job
        mock_generator_client.chat.completions.create.assert_called_once()
        mock_reviewer_client.chat.completions.create.assert_called_once()

        # Notifier should only be called once with the final message for the approved job
        notifier_instance.send_message.assert_called_once()
        
        # Optional: Check the content of the message sent
        sent_message = notifier_instance.send_message.call_args[0][0]
        assert "Associate Product Manager" in sent_message
        assert "Product Manager" not in sent_message 