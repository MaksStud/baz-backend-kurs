import logging
from datetime import timedelta
import boto3

import Levenshtein
import redis
import requests
from rest_framework.exceptions import ValidationError

from backend import settings

logger = logging.getLogger(__name__)


class CurrencyService:
    url: str = "https://open.er-api.com/v6/latest/{currency}"

    def get_exchange_rates(self, base_currency='USD') -> dict:
        """
        Get exchange rates from open.er-api.
        
        :param base_currency: currency.

        :return: dict of objects with exchange rates.
        """
        logger.info("Fetching exchange rates for base currency: %s", base_currency)

        response: requests.Response = requests.get(self.url.format(currency=base_currency))

        if response.status_code == 200:
            logger.info("Successfully fetched exchange rates for %s with status code: %d", base_currency,
                         response.status_code)
            data = response.json()
            return data.get('rates', {})
        else:
            logger.error("Failed to fetch exchange rates for %s with status code: %d", base_currency,
                          response.status_code)
            raise ValidationError('Failed to fetch exchange rates')


class PopularRequestService:
    """
    A service to manage popular request queries using Redis for storage.

    This service allows storing, retrieving, and processing popular query requests.
    It utilizes a Redis backend to track the frequency of each query and to manage
    the expiration of query records.
    """

    def __init__(self):
        self.__redis_client = redis.StrictRedis.from_url(settings.REDIS_CONNECTION_STRING % settings.RedisDatabases.DEFAULT)

    def set(self, query):
        """
        Increments the count of a given query in Redis.

        If the query does not exist, it initializes it with a count of zero and
        sets an expiration time of 7 days.

        :param query (str): The query string to be saved.
        :raises ValueError: If the query is an empty string.
        """
        redis_key = f"query:{query}"

        logger.info('Saving data for key %s', redis_key)

        if not self.__redis_client.exists(redis_key):
            self.__redis_client.set(redis_key, 0)

        self.__redis_client.incr(redis_key)
        self.__redis_client.expire(redis_key, int(timedelta(days=7).total_seconds()))

    def get(self, query=None):
        """
        Retrieves popular queries or queries similar to the given query.

        If no query is provided, returns the top 5 most popular queries.
        If a query is provided, returns up to 5 similar queries based on
        Levenshtein distance.

        :param query (str, optional): The query string to find similar queries.
        :return: A list of dictionaries containing 'query' and 'count' keys.
        """
        keys = self.__redis_client.keys("query:*")
        queries_data = [{'query': key.decode().split(':')[1], 'count': int(self.__redis_client.get(key))} for key in
                        keys]

        if not query:
            logger.info("Retrieving top 5 popular queries.")
            popular_queries = sorted(queries_data, key=lambda x: x['count'], reverse=True)
            return popular_queries[:5] if popular_queries else []
        else:
            logger.info("Finding queries similar to: %s", query)
            similar_queries = self.__matching_check(queries_data, query)
            similar_queries = sorted(similar_queries, key=lambda x: Levenshtein.distance(query, x['query']))

            if similar_queries:
                logger.info("Found %d similar queries to '%s'", len(similar_queries), query)
            else:
                logger.warning("No similar queries found for '%s'", query)

            return similar_queries[:5]

    def __matching_check(self, query_list: list, query: str) -> list:
        """
        Checks for queries in the provided list that are similar to the given query.

        This method calculates the similarity ratio based on the Levenshtein distance
        and filters out queries below a threshold of 0.6. Returns a list of similar
        queries sorted by their Levenshtein distance.

        :param query_list: The list of query data to search for similar queries.
        :param query (str): The query string to compare against.
        :return: A list of similar queries sorted by Levenshtein distance.
        """

        threshold = 0.6
        similar_queries = []

        for item in query_list:
            distance = Levenshtein.distance(query, item['query'])
            max_length = max(len(query), len(item['query']))
            similarity_ratio = (max_length - distance) / max_length

            logger.info("Query: '%s', Compared Query: '%s', Distance: %d, Similarity Ratio: %.2f",
                          query, item['query'], distance, similarity_ratio)

            if similarity_ratio >= threshold:
                logger.info("Query '%s' is similar to '%s' with similarity ratio %.2f",
                              query, item['query'], similarity_ratio)
                similar_queries.append(item)

        sorted_queries = sorted(similar_queries, key=lambda x: Levenshtein.distance(query, x['query']))
        logger.info("Total similar queries found: %d", len(sorted_queries))

        return sorted_queries


class ValidateVisibilityServices:
    """Checks photos, videos, text for approvals"""
    def __init__(self):
        self.keys = settings.SIGHTENGINE_VALIDATE_FIELDS
        self.params = {
            'models': settings.SIGHTENGINE_VALIDATE_MODEL,
            'api_user': settings.SIGHTENGINE_API_USER,
            'api_secret': settings.SIGHTENGINE_API_SECRET}
        self.threshold = settings.VALIDATE_THRESHOLD

    def __validate_file(self, url: str, file):
        """
        Sends the file for verification and returns the result.
        If content is allowed return True, otherwise False.
        :param file: file.
        """
        logger.info("Sending file for validation to URL: %s", url)

        media = {'media': file}
        response = requests.post(url, files=media, data=self.params).json()
        logger.info("Received response: %s", response)

        return self.__check_threshold(response, self.threshold)

    def photo(self, file) -> bool:
        """
        Return photo validation result.
        :param file: file.
        """
        logger.info("Validating photo file: %s", file.name)
        return self.__validate_file(settings.SIGHTENGINE_PHOTO_LINK, file)

    def video(self, file) -> bool:
        """
        Return video validation result.
        :param file: file.
        """
        logger.info("Validating photo file: %s", file.name)
        return self.__validate_file(settings.SIGHTENGINE_VIDEO_LINK, file)

    def __check_threshold(self, check_info: dict, threshold: float = 0.5) -> bool:
        """
        Checks if at least one value is not greater than the threshold.
        :param check_info: Dictionary to check.
        :param threshold: Threshold value for comparison.
        :return: True if all values are within the threshold; otherwise, False.
        """
        keys_to_check = self.keys
        conclusion = True

        for key, value in check_info.items():
            if isinstance(value, dict):
                if not self.__check_threshold(value, threshold):
                    conclusion = False
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, (int, float)) and key in keys_to_check:
                        if item > threshold:
                            conclusion = False
            elif isinstance(value, (int, float)):
                if key in keys_to_check:
                    if value > threshold:
                        conclusion = False
        logger.info(f"Check validate status: {conclusion}, threshold: {threshold}")

        return conclusion


class MediaConvertService:
    """AWS Media Convert Service."""
    def __init__(self):
        self.client = boto3.client(
            'mediaconvert',
            region_name=settings.AWS_S3_REGION_NAME,
            endpoint_url=settings.AWS_MEDIA_CONVERT_ENDPOINT,
        )
        self.aws_media_convert_role=settings.AWS_MEDIA_CONVERT_ROLE

    def create_job(self, video_url: str, start_time: int, end_time: int, output_file_name: str) -> str:
        """
        Creates a Media Convert job.
        Trims the video at specified points where the start_time point is closer to the beginning and the end_time point is closer to the end.
        The output video is what will be in between.

        :param video_url: URL to video on AWS S3 bucket.
        :param start_time: Starting point in seconds.
        :param end_time: END point in seconds.
        :param output_file_name: The name the output file will have after cropping.
        :return: Job id.
        """
        output_path = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/ability_media/{output_file_name}"

        job_settings = {
            "Inputs": [
                {
                    "FileInput": video_url,
                    "InputClippings": [
                        {
                            "StartTimecode": self.seconds_to_timecode(start_time),
                            "EndTimecode": self.seconds_to_timecode(end_time),
                        }
                    ],
                    "TimecodeSource": "ZEROBASED",
                    "VideoSelector": {
                        "Rotate": "AUTO"
                    },
                    "AudioSelectors": {
                        "Audio 1": {
                            "SelectorType": "TRACK",
                            "Tracks": [1]
                        }
                    }
                }
            ],
            "OutputGroups": [
                {
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": output_path
                        }
                    },
                    "Outputs": [
                        {
                            "ContainerSettings": {
                                "Container": "MP4"
                            },
                            "VideoDescription": {
                                "CodecSettings": {
                                    "Codec": "H_264",
                                    "H264Settings": {
                                        "RateControlMode": "CBR",
                                        "Bitrate": 5000000,
                                        "GopSize": 60,
                                        "GopSizeUnits": "FRAMES",
                                        "GopClosedCadence": 1,
                                        "InterlaceMode": "PROGRESSIVE",
                                        "NumberBFramesBetweenReferenceFrames": 2,
                                        "AdaptiveQuantization": "HIGH",
                                        "SceneChangeDetect": "ENABLED"
                                    }
                                }
                            },
                            "AudioDescriptions": [
                                {
                                    "CodecSettings": {
                                        "AacSettings": {
                                            "Bitrate": 64000,
                                            "CodingMode": "CODING_MODE_2_0",
                                            "SampleRate": 48000
                                        },
                                        "Codec": "AAC"
                                    },
                                    "AudioSourceName": "Audio 1",
                                    "AudioType": 1
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        logger.info('Start Media Convert job.')
        response = self.client.create_job(Settings=job_settings, Role=self.aws_media_convert_role)
        logger.info(f'Media Convert job result: {response}')
        return str(response["Job"]["Id"])

    def seconds_to_timecode(self, seconds: int) -> str:
        """
        Converts the time in seconds to a string.
        :param seconds: Hour in seconds, type int.
        :return: String divided by the hours of the seconds.
        """
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02};00"

    def get_output_url(self, job_id: str):
        """
        Returns the name and a link to the file on s3 that resulted from the cropping operation.
        :param job_id: Job id media convert.
        """
        response = self.client.get_job(Id=job_id)
        logger.info(f'Get data about job: {response}')
        output_s3_url = response['Job']['Settings']['OutputGroups'][0]['OutputGroupSettings']['FileGroupSettings']['Destination']
        output_s3_key = output_s3_url.replace(f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/", "") + ".mp4"

        file_name = output_s3_key.split("/")[-1]
        return file_name, output_s3_key
