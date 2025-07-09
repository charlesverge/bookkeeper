"""
Database connection utilities for bookkeeper application.

This module provides common database connection functions and utilities
used across the bookkeeper application.
"""

import logging
from pymongo import MongoClient
from pymongo.collection import Collection

logger = logging.getLogger(__name__)


def get_mongodb_collection(
    connection_string: str = "mongodb://localhost:27017/",
    database_name: str = "bookkeeper",
    collection_name: str = "intake_records",
) -> Collection:
    """
    Get MongoDB collection for the specified database and collection.

    Args:
        connection_string: MongoDB connection string
        database_name: Name of the database
        collection_name: Name of the collection

    Returns:
        MongoDB collection object

    Raises:
        Exception: If connection to MongoDB fails
    """
    try:
        client = MongoClient(connection_string)
        db = client[database_name]
        return db[collection_name]
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
