import os
import requests


def send_telegram_alert(message: str):
    """
    Send message to telegram chat.

    :param message: Message text.

    :return: response json.
    """
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
    payload = {
        "chat_id": os.getenv('TELEGRAM_CHAT_ID'),
        "text": message,
        "parse_mode": "Markdown",
        "message_thread_id": os.getenv('TELEGRAM_MESSAGE_THREAD_ID')
    }
    response = requests.post(url, json=payload)
    return response.json()


