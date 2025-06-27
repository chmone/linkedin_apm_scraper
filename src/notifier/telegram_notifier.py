# This file will contain the Telegram Notifier.
# It will use the Adapter pattern to send notifications.
import asyncio
import telegram

class TelegramNotifier:
    """A class to handle sending messages via Telegram."""

    def __init__(self, config):
        """
        Initializes the notifier with the Telegram bot token and chat ID.
        
        Args:
            config: The application configuration object.
        """
        self.bot_token = config.telegram_bot_token
        self.chat_id = config.telegram_chat_id
        if self.bot_token:
            self.bot = telegram.Bot(token=self.bot_token)
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:  # 'get_running_loop' fails if no loop is running
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
        else:
            self.bot = None
            self.loop = None
            print("Warning: TelegramNotifier initialized without a bot token.")

    async def send_message_async(self, message: str):
        """
        Sends a message to the configured Telegram chat.

        Args:
            message: The message string to send.
        """
        if not self.bot or not self.chat_id:
            print("Cannot send message: Telegram bot not configured.")
            print(f"--- MOCKED TELEGRAM MESSAGE ---\n{message}\n--------------------")
            return

        try:
            # Telegram's MarkdownV2 requires certain characters to be escaped.
            # This is a basic set of characters.
            escape_chars = '_*[]()~`>#+-=|{}.!'
            for char in escape_chars:
                message = message.replace(char, f'\\{char}')

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='MarkdownV2'
            )
            print(f"Successfully sent message to Telegram chat ID {self.chat_id}")
        except Exception as e:
            print(f"Failed to send message to Telegram: {e}")

    def send_message(self, message: str):
        """
        Synchronous wrapper for the async send_message_async method.
        """
        if self.loop:
            self.loop.run_until_complete(self.send_message_async(message))
        else:
            # Fallback for when no bot is configured
            asyncio.run(self.send_message_async(message))


def get_notifier(config):
    """
    Factory function to get a notifier instance.
    """
    return TelegramNotifier(config) 