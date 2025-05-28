from django.core.cache import cache
from .tasks import send_email_confirm_code
from django.conf import settings

import random
import string


def generate_confirmation_code(length: int = 6) -> str:
    """
    Generates a random confirmation code consisting of digits.

    The default length of the code is 6 digits. You can specify a different length if needed.

    Args:
        length (int): The length of the confirmation code. Defaults to 6.

    Returns:
        str: A string representing the randomly generated confirmation code.
    """
    return ''.join(random.choices(string.digits, k=length))


def save_and_send_confirmation_code(email: str) -> None:
    """
    Saves a confirmation code to cache and sends it to the specified email address.

    Generates a confirmation code, stores it in the cache with a timeout of 3600 seconds,
    and sends it to the user via email using an asynchronous task.

    Args:
        email (str): The email address to which the confirmation code will be sent.
    """
    confirmation_code = generate_confirmation_code()
    cache_key = f"code_{email}"
    cache.set(cache_key, confirmation_code, timeout=settings.TIME_LIFE_OTP_CODE)

    send_email_confirm_code.delay(email, confirmation_code, int(settings.TIME_LIFE_OTP_CODE / 60))
