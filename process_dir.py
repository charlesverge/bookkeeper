"""
Directory Processing Script - Crawls directory and adds files to intake queue.

This script recursively walks through a directory, processes each file,
and adds them to the intake queue for document extraction.
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import logging
from pymongo.collection import Collection

from entry_queue.entry_queue_manager import EntryQueueManager, FileInfo
from db.connection import get_mongodb_collection

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DirectoryProcessor:
    """Processes files in a directory and adds them to the intake queue."""

    def __init__(self, intake_records_collection: Collection):
        self.queue_manager = EntryQueueManager(intake_records_collection)
        self.processed_count = 0
        self.duplicate_count = 0
        self.error_count = 0

    def process_directory(
        self, directory_path: str, source: str = "directory_crawl"
    ) -> dict:
        """
        Process all files in the specified directory.

        Args:
            directory_path: Path to directory to process
            source: Source identifier for tracking

        Returns:
            Dict with processing statistics
        """
        directory = Path(directory_path)

        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory_path}")

        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")

        logger.info(f"Starting directory processing: {directory_path}")

        for file_path in directory.rglob("*"):
            if file_path.is_file():
                self._process_file(file_path, source)

        stats = {
            "processed": self.processed_count,
            "duplicates": self.duplicate_count,
            "errors": self.error_count,
            "total_files": self.processed_count
            + self.duplicate_count
            + self.error_count,
        }

        logger.info(f"Directory processing complete: {stats}")
        return stats

    def _process_file(self, file_path: Path, source: str):
        """Process individual file and add to intake queue."""
        try:
            file_info = self._create_file_info(file_path, source)
            result = self.queue_manager.process_file_request(file_info)

            if result["status"] == "success":
                self.processed_count += 1
                logger.info(f"Processed: {file_path}")
            elif result["status"] == "duplicate":
                self.duplicate_count += 1
                logger.info(f"Duplicate: {file_path}")
            else:
                self.error_count += 1
                logger.error(
                    f"Error processing {file_path}: {result.get('message', 'Unknown error')}"
                )

        except Exception as e:
            self.error_count += 1
            logger.error(f"Exception processing {file_path}: {e}")

    def _create_file_info(self, file_path: Path, source: str) -> FileInfo:
        """Create FileInfo object from file path."""
        stat = file_path.stat()

        return FileInfo(
            file_location=str(file_path.absolute()),
            file_id=f"{file_path.name}_{stat.st_size}_{int(stat.st_mtime)}",
            source=source,
            date=datetime.fromtimestamp(stat.st_mtime),
        )


def main():
    """Main entry point for directory processing."""
    parser = argparse.ArgumentParser(
        description="Process directory files and add to intake queue"
    )
    parser.add_argument("directory", help="Directory path to process")
    parser.add_argument(
        "--source", default="directory_crawl", help="Source identifier for tracking"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        collection = get_mongodb_collection()
        processor = DirectoryProcessor(collection)
        stats = processor.process_directory(args.directory, args.source)

        print(f"\nProcessing Summary:")
        print(f"  Total files found: {stats['total_files']}")
        print(f"  Successfully processed: {stats['processed']}")
        print(f"  Duplicates skipped: {stats['duplicates']}")
        print(f"  Errors encountered: {stats['errors']}")

        return 0 if stats["errors"] == 0 else 1

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
