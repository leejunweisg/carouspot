import logging

from pymongo import MongoClient
from pymongo.errors import OperationFailure

# logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self, mongo_url: str):
        # create MongoDB connection
        try:
            cluster = MongoClient(mongo_url)
            db = cluster["carouspot-db"]

            self._chats = db["chats"]
            self._items = db["items"]

            logger.info("Connected to MongoDB!")
        except OperationFailure as e:
            logger.error("Unable to connect to MongoDB :-(")
            exit()

    @property
    def chats(self):
        return self._chats

    @property
    def items(self):
        return self._items
