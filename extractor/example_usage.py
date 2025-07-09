"""
Example usage of the DocumentExtractor class.

This script demonstrates how to use the DocumentExtractor to process documents
from the entry queue and save the extracted data to MongoDB.
"""

import logging
import os
from pymongo import MongoClient
from entry_queue.entry_queue_manager import EntryQueueManager
from extractor.document_extractor import DocumentExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Main function to demonstrate DocumentExtractor usage."""
    try:
        # Initialize MongoDB connection
        mongodb_uri = os.getenv("MONGODB_URL", "")
        mongo_client = MongoClient(mongodb_uri)
        db = mongo_client.bookkeeper

        # Initialize entry queue manager
        queue_manager = EntryQueueManager(db.intake_records)

        # Initialize document extractor with context manager
        with DocumentExtractor(queue_manager, mongodb_uri) as extractor:
            logger.info("Starting document extraction process...")

            # Process documents until queue is empty
            processed_count = 0
            while True:
                # Process next document in queue
                extracted_data = extractor.process_next_document()

                if extracted_data is None:
                    logger.info("No more documents in queue")
                    break

                processed_count += 1
                logger.info(
                    f"Processed document #{processed_count}: "
                    f"Type={extracted_data.document_type.value}, "
                    f"Total={extracted_data.total_amount}, "
                    f"Currency={extracted_data.currency}"
                )

                # Optional: Process only a limited number for testing
                if processed_count >= 10:
                    logger.info("Processed 10 documents, stopping for demo")
                    break

            logger.info(f"Extraction complete. Processed {processed_count} documents.")

    except Exception as e:
        logger.error(f"Error in main extraction process: {e}")
        raise
    finally:
        # Close MongoDB connection
        if "mongo_client" in locals():
            mongo_client.close()


if __name__ == "__main__":
    main()
