import json
import logging
import requests
import random

from bs4 import BeautifulSoup
from rest_framework.serializers import ValidationError
from rest_framework import status

from django.conf import settings
from django.core.cache import cache

from abc import ABC, abstractmethod
import re

from ability.choices import currency_list, olx_currency

logger = logging.getLogger(__name__)


class AbstractSiteParser(ABC):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "uk,uk-UA;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip",
        "Accept-Charset": "utf-8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://google.com",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "DNT": "1",
    })

    def get_product(self, url: str) -> dict[str: str | int | float]:
        """
        Returns product data.

        :param url: Link to the product.

        :return: info about product.
        """
        try:
            cache_product = cache.get(url)

            if cache_product:
                return cache_product

            response = self.get_response(url)

            product = {
                "name": self.get_name(response),
                "price": self.get_price(response),
                "description": self.get_description(response),
                "photo_link": self.get_photo_url(response),
                "currency": self.get_currency(response)
            }

            cache.set(url, product, settings.CACHES_TIME)

            return product

        except Exception as e:
            logger.error(f'Error in get_product: {e}')
            raise ValidationError(detail='Something went wrong, try again.')

    @abstractmethod
    def get_response(self, url: str) -> BeautifulSoup | dict:
        """Returns a response from the site. Must be overridden."""
        raise NotImplementedError()

    @abstractmethod
    def get_name(self, response: BeautifulSoup | dict) -> str | None:
        """Returns name from the site response. Must be overridden."""
        raise NotImplementedError()

    @abstractmethod
    def get_price(self, response: BeautifulSoup | dict) -> float | None:
        """Returns price from the site response. Must be overridden."""
        raise NotImplementedError()

    @abstractmethod
    def get_description(self, response: BeautifulSoup | dict) -> str | None:
        """Returns description from the site response. Must be overridden."""
        raise NotImplementedError()

    @abstractmethod
    def get_photo_url(self, response: BeautifulSoup | dict) -> str | None:
        """Returns photo from the site response. Must be overridden."""
        raise NotImplementedError()

    @abstractmethod
    def get_currency(self, response: BeautifulSoup | dict) -> str | None:
        """Returns currency from the site response. Must be overridden."""
        raise NotImplementedError()

    def extract_digits(self, number: str) -> float | None:
        """
        Converts the returned value to a number, removing anything after a dot.

        :param number: number in string.

        :return: float or None
        """
        if not number:
            return None

        number = re.sub(r'\..*', '', str(number))
        digits = re.sub(r'[^\d]', '', number)

        return int(digits) if digits else None

    def validate_currency(self, currency: str):
        logger.info("Validate currency.")
        return currency if currency in currency_list else 'UAH'


class OpenAiSiteParser(AbstractSiteParser):
    """Parser for any website."""
    def __init__(self):
        self.headers_to_gpt = {
            "Content-Type": 'application/json',
            "Authorization": 'Bearer ' + settings.GPT_API_KEY
        }

    def get_response(self, url: str) -> dict[str, str | int]:
        """
        Receives a response from AI to information from the website.

        :param url: Url of the site that needs to get information.

        :return: Dictionary with the data.
        """
        try:

            logger.info(f'Sending a request to the {url} page.')

            response = self.session.get(url, timeout=60)
            logger.info(f"{response=}")

            if response.status_code == 200:
                response.encoding = response.headers.get("Content-Encoding", 'utf-8')
                logger.info(f"Detected encoding: {response.encoding}")

                soup = BeautifulSoup(response.text, 'html.parser')
                text = soup.get_text(separator='-').lower().replace('\n', '').replace(' ', '')
                photo_links = ', '.join([img.get('src') for img in soup.find_all('img') if img.get('src')])

                text = self.trim_text(text)
                photo_links = self.trim_text(photo_links)

                information = self.response_to_gpt(text, photo_links)
            elif response.status_code in [status.HTTP_403_FORBIDDEN]:
                information = self.alternative_method(url)
            else:
                logger.error(f'Error receiving information code {response.status_code}.')
                raise ValidationError(detail='Url is incorrect.')

            cache.set(url, information, settings.CACHES_TIME)
            return information

        except Exception as e:
            cache.delete(url)
            logger.error(f'Error in get_response: {e}')
            raise ValidationError(detail='Something went wrong, try again.')

    def trim_text(self, text: str):
        """Trim the video if it's too long."""
        if len(text) >= 16385:
            return text[:16384]
        return text

    def response_to_gpt(self, text: str, photo_links: str) -> dict:
        """
        Sending a request to the gpt api.

        :param text: The information is obtained from the file.
        :param photo_links: url list.

        :return: A dictionary with the value returned by the api.
        """
        logger.info('Головний метод.')
        product_info = {}
        try:
            product = ('Using the provided data, generate a JSON object containing the name, price, description, and currency of an item. '
                       'The JSON should have string keys, like this example format: '
                       '{"name": "Sample Name", "price": "Sample Price", "description": "Sample Description", "currency": "Sample Currency"} '
                       'Ensure that the price value contains only one decimal point to separate the cents (e.g., 12.34 or 100.00). '
                       f'The currency must be one of the following: [{", ".join(currency_list)}]. '
                       'Replace the placeholder values with the actual data I provide. ' + text)

            product_images = ("From the provided links, identify and return the one that represents the product photo. "
                              "Ensure the response includes only the complete URL, prefixed with either 'http' or "
                              "'https' as applicable, without any additional text. Also, explicitly mention only the "
                              "domain of the site in the response. " + photo_links)

            body = self.body_to_openai()

            body['messages'][0]['content'] = product
            logger.info(f'Sending request to gpt api.')
            response = requests.post(settings.GPT_API_MODEL, json=body, headers=self.headers_to_gpt, timeout=60).json()
            logger.info(f'{response=}')
            content = json.loads(response.get('choices')[0].get('message').get('content'))
            logger.info(f'product: {content}')
            product_info = content

            body['messages'][0]['content'] = product_images
            logger.info(f'Sending a second request to gpt api.')
            response = requests.post(settings.GPT_API_MODEL, json=body, headers=self.headers_to_gpt, timeout=60).json()
            logger.info(f'{response=}')
            image_link = response.get('choices')[0].get('message').get('content')
            logger.info(f'photo: {image_link}')

            product_info['price'] = self.extract_digits(content.get('price'))
            
            product_info['photo_link'] = image_link
            return product_info
        except Exception as e:
            logger.error(f'Error in parsing product using OpenAI: {e}')
            return product_info

    def alternative_method(self, url: str) -> dict:
        """
        It uses a different parsing method.

        :param url: Link to the product.

        :return: A dictionary with the results of the work.
        """

        product_data_request: str = (
            f"Using the provided links {url}, generate a JSON object containing the name, price, description, and "
            f"currency of an item, "
            "as well as the URL of the product photo. The JSON should follow this format: "
            '{"name": "Sample Name", "price": "Sample Price", "description": "Sample Description", '
            '"currency": "Sample Currency", "photo_link": "Sample URL"}. '
            "Ensure the price value contains only one decimal point to separate the cents (e.g., 12.34 or 100.00). "
            f"The currency must be one of the following: [{', '.join(currency_list)}]. Replace the placeholder values "
            f"with data from the provided URL. "
            "The name and description should be returned in either Ukrainian or English, based on the content available. "
            "From the provided links, identify the one that represents the product photo. Ensure the response "
            "includes only the complete URL, prefixed with either 'http' or 'https', "
            "and mention only the domain of the site in the response."
        )

        body = self.body_to_openai()
        body['messages'][0]['content'] = product_data_request
        try:
            response = requests.post(settings.GPT_API_MODEL, json=body, headers=self.headers_to_gpt, timeout=60).json()
        except Exception as e:
            raise ValidationError(detail='Something went wrong, try again.')
        logger.info(f'{response=}')
        content = json.loads(response.get('choices')[0].get('message').get('content'))
        logger.info(f'product: {content}')
        return content

    def body_to_openai(self) -> dict:
        """Return body for request to openai api."""
        return {
                "model": settings.GPT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": None
                    }
                ]
            }

    def get_name(self, response: dict) -> str | None:
        """
        Returning the product price.

        :param response: response from gpt api.

        :return: name.
        """
        name = response.get('name')
        logger.info(f'name: {name}, type of: {type(name)}')
        return name

    def get_price(self, response: dict) -> float | None:
        """
        Returning the product price.

        :param response: response from gpt api.

        :return: price.
        """
        price = self.extract_digits(response.get('price'))
        logger.info(f'price: {price}, type of: {type(price)}')
        return price

    def get_description(self, response: dict) -> str | None:
        """
        Returning the product price.

        :param response: response from gpt api.

        :return: description.
        """
        description = response.get('description')
        logger.info(f'description: {description}, type of: {type(description)}')
        return description

    def get_photo_url(self, response: dict) -> str | None:
        """
        Returning the product price.

        :param response: response from gpt api.

        :return: None.
        """
        photo_link = response.get('photo_link')
        logger.info(f'photo_link: {photo_link}, type of: {type(photo_link)}')
        return photo_link

    def get_currency(self, response: dict) -> str | None:
        """
        Returning the product currency.

        :param response: response from gpt api.

        :return: currency.
        """
        currency = response.get('currency')
        logger.info(f'currency: {currency}')
        return self.validate_currency(currency)


class OLXParser(AbstractSiteParser):
    """Parser for olx."""

    def get_response(self, url: str) -> BeautifulSoup:
        """
        Gets a link to a page, returns an object of type BeautifulSoup with page data.

        :param url: Link to the page.

        :return: Returns an object of type BeautifulSoup.
        """
        logger.info(f'Sending a request to {url}.')
        response = self.session.get(url, timeout=60)

        if response.status_code != 200:
            logger.error(f'Error receiving information, code {response.status_code}.')
            raise ValidationError(f"Failed to load page: {response.status_code}")

        return BeautifulSoup(response.text, 'html.parser')

    def get_name(self, soup: BeautifulSoup) -> str | None:
        """
        Returning the product title.

        :param soup: The BeautifulSoup object.

        :return: name.
        """
        name_tag = soup.find("h4", {"class": "css-1kc83jo"})
        logger.info(f'name = {name_tag}')
        return name_tag.get_text(strip=True) if name_tag else None

    def get_price(self, soup: BeautifulSoup) -> float | None:
        """
        Returning the product price.

        :param soup: The BeautifulSoup object.

        :return: price.
        """
        price_tag = soup.find("h3", {"class": "css-90xrc0"})
        logger.info(f'price = {price_tag}')
        return self.extract_digits(price_tag.get_text(strip=True)) if price_tag else None

    def get_description(self, soup: BeautifulSoup) -> str | None:
        """
        Returning the product description.

        :param soup: The BeautifulSoup object.

        :return: description.
        """
        description_tag = soup.find("div", {"class": "css-1o924a9"})
        logger.info(f'description = {description_tag}')
        return description_tag.get_text(strip=True) if description_tag else None

    def get_photo_url(self, soup: BeautifulSoup) -> str | None:
        """
        Returning the product photo.

        :param soup: The BeautifulSoup object.

        :return: photo link.
        """
        img_tag = soup.find("img", class_="css-1bmvjcs")
        return img_tag.get("src") if img_tag else None

    def get_currency(self, soup: BeautifulSoup) -> str | None:
        """
        Returning the product currency.

        :param soup: The BeautifulSoup object.

        :return: currency.
        """
        price_tag = soup.find("h3", {"class": "css-90xrc0"}).get_text(strip=True)
        logger.info(f'olx currency: {price_tag.split(" ")[-1]}')
        return olx_currency.get(price_tag.split(' ')[-1], 'UAH')


parsers = {'olx': OLXParser}
