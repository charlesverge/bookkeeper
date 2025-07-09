"""
Test script for DocumentExtractor functionality.

This script tests the document extraction capabilities with sample files.
"""

import logging
import os
import sys
from datetime import datetime
from pymongo import MongoClient
from entry_queue.entry_queue_manager import EntryQueueManager, FileInfo
from extractor.document_extractor import DocumentExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def test_with_sample_files():
    """Test extractor with sample files from data directory."""
    try:
        # Check if sample files exist
        data_dir = "data"
        test_files = []

        if os.path.exists(os.path.join(data_dir, "invoice-test.txt")):
            test_files.append(os.path.join(data_dir, "invoice-test.txt"))
        if os.path.exists(os.path.join(data_dir, "receipt-test.txt")):
            test_files.append(os.path.join(data_dir, "receipt-test.txt"))

        if not test_files:
            logger.warning("No test files found in data directory")
            return

        # Initialize MongoDB connection
        mongodb_uri = os.getenv("MONGODB_URL", "")
        mongo_client = MongoClient(mongodb_uri)
        db = mongo_client.bookkeeper

        # Initialize entry queue manager
        queue_manager = EntryQueueManager(db.intake_records)

        # Add test files to queue
        for test_file in test_files:
            file_info = FileInfo(
                file_location=test_file,
                file_id=f"test_{os.path.basename(test_file)}",
                source="test",
                date=datetime.now(),
            )

            result = queue_manager.process_file_request(file_info)
            logger.info(f"Added {test_file} to queue: {result}")

        # Process documents with extractor
        with DocumentExtractor(queue_manager, mongodb_uri) as extractor:
            logger.info("Testing document extraction...")

            processed_count = 0
            while True:
                extracted_data = extractor.process_next_document()

                if extracted_data is None:
                    break

                processed_count += 1
                logger.info(
                    f"Test #{processed_count}: "
                    f"Type={extracted_data.document_type.value}, "
                    f"Raw text length={len(extracted_data.raw_text)}"
                )

                # Print first 200 characters of raw text for debugging
                logger.debug(f"Raw text preview: {extracted_data.raw_text[:200]}...")

            logger.info(f"Test complete. Processed {processed_count} documents.")

    except Exception as e:
        logger.error(f"Error in test: {e}")
        raise
    finally:
        if "mongo_client" in locals():
            mongo_client.close()


def test_individual_methods():
    """Test individual extractor methods without full pipeline."""
    try:
        # Initialize MongoDB connection
        mongodb_uri = os.getenv("MONGODB_URL", "")
        mongo_client = MongoClient(mongodb_uri)
        db = mongo_client.bookkeeper

        # Initialize entry queue manager
        queue_manager = EntryQueueManager(db.intake_records)

        # Create extractor
        with DocumentExtractor(queue_manager, mongodb_uri) as extractor:
            logger.info("Testing individual extractor methods...")

            # Test text extraction
            test_file = "data/invoice-test.txt"
            if os.path.exists(test_file):
                text = extractor._extract_text_from_document(test_file)
                logger.info(f"Extracted text length: {len(text)}")

                # Test classification
                doc_type = extractor._classify_document(text)
                logger.info(f"Classified as: {doc_type}")

                # Test structured extraction
                structured_data = extractor._extract_structured_data(text, doc_type)
                logger.info(
                    f"Structured extraction complete: {structured_data.document_type}"
                )

            else:
                logger.warning(f"Test file not found: {test_file}")

    except Exception as e:
        logger.error(f"Error in individual method test: {e}")
        raise
    finally:
        if "mongo_client" in locals():
            mongo_client.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--methods":
        test_individual_methods()
    else:
        test_with_sample_files()
