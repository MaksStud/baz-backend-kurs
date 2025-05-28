import requests
from requests import Session


class RequestsSessionSingleton:
    """Singleton class for Requests Session."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RequestsSessionSingleton, cls).__new__(cls)
            cls._instance.session = requests.Session()
            cls._instance.session.headers.update(
                {
                    "accept": "application/json",
                    "accept-encoding": "gzip, deflate",
                    "content-type": "application/json",
                }
            )
        return cls._instance

    @classmethod
    def get_session(cls) -> Session:
        """Return session."""
        return cls().session
