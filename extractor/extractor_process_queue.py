"""
Extractor Queue Processor - Continuously processes documents from the extraction queue.

This script monitors the extraction queue and processes documents as they become available.
It can be run as a standalone service to handle document extraction operations.

Usage:
    python extractor_process_queue.py                    # Run with default settings
    python extractor_process_queue.py --poll-interval 10 # Check queue every 10 seconds
    python extractor_process_queue.py --clear-queue      # Clear queue before processing
    python extractor_process_queue.py --status           # Show queue status and exit
    python extractor_process_queue.py --verbose          # Enable verbose logging

Environment Variables:
    MONGODB_URL: MongoDB connection string (required)
    QUEUE_POLL_INTERVAL: Default poll interval in seconds (optional, default: 5)

Features:
    - Continuous monitoring and processing of the extraction queue
    - Graceful shutdown on SIGINT/SIGTERM signals
    - Error handling with automatic retry
    - Queue status reporting
    - Queue clearing functionality
    - Configurable poll intervals
"""

import logging
import os
import sys
import time
import signal
import argparse
from typing import Optional
from pymongo import MongoClient
from dotenv import load_dotenv

from entry_queue.entry_queue_manager import EntryQueueManager
from extractor.document_extractor import DocumentExtractor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class QueueProcessor:
    """Handles continuous processing of the extraction queue."""

    def __init__(self, mongodb_uri: str, poll_interval: int = 5):
        """
        Initialize the queue processor.

        Args:
            mongodb_uri: MongoDB connection string
            poll_interval: Seconds to wait between queue checks
        """
        self.mongodb_uri = mongodb_uri
        self.poll_interval = poll_interval
        self.running = False
        self.mongo_client: Optional[MongoClient] = None
        self.queue_manager: Optional[EntryQueueManager] = None
        self.extractor: Optional[DocumentExtractor] = None

    def start(self):
        """Start the queue processing loop."""
        try:
            # Initialize MongoDB connection
            self.mongo_client = MongoClient(self.mongodb_uri)
            db = self.mongo_client.bookkeeper

            # Initialize components
            self.queue_manager = EntryQueueManager(db.intake_records)
            self.extractor = DocumentExtractor(self.queue_manager, self.mongodb_uri)
            self.extractor.__enter__()

            self.running = True
            logger.info("Queue processor started")

            # Main processing loop
            processed_count = 0
            while self.running:
                try:
                    # Check queue status
                    queue_items = self.queue_manager.get_extraction_queue()
                    if queue_items:
                        logger.info(f"Found {len(queue_items)} items in queue")
                    else:
                        # No documents to process, wait before checking again
                        logger.debug(
                            f"No documents in queue, waiting {self.poll_interval} seconds..."
                        )
                        self.stop()
                        time.sleep(self.poll_interval)
                        continue

                    # Process next document
                    extracted_data = self.extractor.process_next_document()

                    if extracted_data is None:
                        continue

                    processed_count += 1
                    logger.info(
                        f"Processed document #{processed_count}: "
                        f"Type={extracted_data.document_type.value}"
                    )

                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, stopping...")
                    break
                except Exception as e:
                    logger.error(f"Error processing document: {e}")
                    # Continue processing after error
                    time.sleep(self.poll_interval)

            logger.info(f"Queue processor stopped. Total processed: {processed_count}")

        except Exception as e:
            logger.error(f"Fatal error in queue processor: {e}")
            raise
        finally:
            self.stop()

    def stop(self):
        """Stop the queue processor and cleanup resources."""
        self.running = False

        if self.extractor:
            try:
                self.extractor.__exit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing extractor: {e}")

        if self.mongo_client:
            try:
                self.mongo_client.close()
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {e}")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    global processor
    if processor:
        processor.stop()


def main():
    """Main entry point for the queue processor."""
    global processor
    processor = None

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Process documents from the extraction queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with default settings
  %(prog)s --poll-interval 10       # Check queue every 10 seconds
  %(prog)s --clear-queue             # Clear queue before processing
  %(prog)s --status                  # Show queue status and exit
        """,
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Seconds to wait between queue checks (default: 5)",
    )
    parser.add_argument(
        "--clear-queue",
        action="store_true",
        help="Clear the extraction queue before processing",
    )
    parser.add_argument(
        "--status", action="store_true", help="Show queue status and exit"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Get MongoDB URI from environment
        mongodb_uri = os.getenv("MONGODB_URL")
        if not mongodb_uri:
            logger.error("MONGODB_URL environment variable not set")
            sys.exit(1)

        # Initialize MongoDB connection for status/clear operations
        if args.status or args.clear_queue:
            mongo_client = MongoClient(mongodb_uri)
            db = mongo_client.bookkeeper
            queue_manager = EntryQueueManager(db.intake_records)

            if args.status:
                queue_items = queue_manager.get_extraction_queue()
                print(f"Queue status:")
                print(f"  Pending extraction: {len(queue_items)} items")

                if queue_items:
                    print(f"\nNext {min(5, len(queue_items))} items for extraction:")
                    for i, item in enumerate(queue_items[:5], 1):
                        print(
                            f"  {i}. {item['file_id']} ({item['source']}) - {item['queued_at']}"
                        )

                mongo_client.close()
                return

            if args.clear_queue:
                queue_manager.clear_extraction_queue()
                print("Extraction queue cleared")
                mongo_client.close()
                return

        # Get poll interval from args or environment
        poll_interval = args.poll_interval or int(os.getenv("QUEUE_POLL_INTERVAL", "5"))

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Create and start processor
        processor = QueueProcessor(mongodb_uri, poll_interval)
        logger.info(f"Starting queue processor with {poll_interval}s poll interval")
        processor.start()

    except Exception as e:
        logger.error(f"Failed to start queue processor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
