#!/usr/bin/env python3
"""
Main script to test the Entry Queue Manager with sample documents.

This script demonstrates how to use the Entry Queue Manager to process
invoice and receipt documents using PyMongo.
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv()

from entry_queue.entry_queue_manager import (
    EntryQueueManager,
    FileInfo,
    ProcessingStatus,
)


def setup_mongodb():
    """Setup MongoDB connection and collection."""
    try:
        # Connect to MongoDB (default localhost:27017)
        client = MongoClient(
            os.getenv("MONGODB_URL", "mongodb://localhost:27017/"),
            serverSelectionTimeoutMS=5000,
        )

        # Test the connection
        client.admin.command("ping")
        print("✓ Connected to MongoDB")

        # Get database and collection
        db = client["bookkeeper"]
        collection = db["intake_records"]

        return db, collection

    except ConnectionFailure:
        print("✗ Failed to connect to MongoDB")
        print("Please ensure MongoDB is running on localhost:27017")
        sys.exit(1)


def main():
    """Main function to test entry queue manager."""

    print("=== Entry Queue Manager Test ===\n")

    # Setup MongoDB collection
    db, collection = setup_mongodb()

    # Initialize Entry Queue Manager
    entry_queue_manager = EntryQueueManager(collection)

    # Test files to process
    test_files = [
        {
            "file_location": "data/invoice-test.txt",
            "file_id": "data/invoice-test.txt",
            "source": "file_upload",
            "description": "Test Invoice",
        },
        {
            "file_location": "data/receipt-test.txt",
            "file_id": "data/receipt-test.txt",
            "source": "file_upload",
            "description": "Test Receipt",
        },
    ]

    processed_intake_ids = []

    # Process each test file
    for i, file_data in enumerate(test_files, 1):
        print(f"{i}. Processing {file_data['description']}:")
        print(f"   File: {os.path.basename(file_data['file_location'])}")

        # Check if file exists
        if not os.path.exists(file_data["file_location"]):
            print(f"   ✗ File not found: {file_data['file_location']}")
            continue

        # Create FileInfo object
        file_info = FileInfo(
            file_location=file_data["file_location"],
            file_id=file_data["file_id"],
            source=file_data["source"],
            date=datetime(2025, 1, 1),
        )

        # Process the file
        result = entry_queue_manager.process_file_request(file_info)

        if result["status"] == "success":
            print(f"   ✓ Success: {result['intake_id']}")
            print(f"   Status: {result['processing_status']}")
            processed_intake_ids.append(result["intake_id"])
        elif result["status"] == "duplicate":
            print(f"   ⚠ Duplicate: {result['message']}")
            print(f"   Existing ID: {result['existing_id']}")
        else:
            print(f"   ✗ Error: {result['message']}")

        print()

    # Test duplicate detection by processing the same invoice again
    print("3. Testing duplicate detection (processing invoice again):")
    duplicate_file_info = FileInfo(
        file_location="data/invoice-test.txt",
        file_id="data/invoice-test.txt",
        source="file_upload",
        date=datetime(2025, 1, 1),
    )

    result = entry_queue_manager.process_file_request(duplicate_file_info)
    if result["status"] == "duplicate":
        print(f"   ✓ Duplicate correctly detected: {result['message']}")
    else:
        print(f"   ✗ Duplicate detection failed: {result}")
    print()

    # Test status updates
    if processed_intake_ids:
        print("4. Testing status updates:")
        for intake_id in processed_intake_ids:
            # Update status to processing
            success = entry_queue_manager.update_intake_status(
                intake_id,
                ProcessingStatus.PROCESSING.value,
                {"extractor_started_at": datetime.now().isoformat()},
            )

            if success:
                print(f"   ✓ Updated {intake_id} to PROCESSING")

                # Retrieve and display updated record
                record = entry_queue_manager.get_intake_record(intake_id)
                if record:
                    print(f"   Status: {record.processing_status}")
                    print(f"   Details: {record.status_details}")
            else:
                print(f"   ✗ Failed to update {intake_id}")
        print()

    # Display queue status
    print("5. Queue Status:")
    extraction_queue = entry_queue_manager.get_extraction_queue()
    print(f"   Items in queue: {len(extraction_queue)}")
    for item in extraction_queue:
        print(f"   - {item['intake_id']}: {os.path.basename(item['file_location'])}")
    print()

    # Display MongoDB collection stats
    print("6. Database Status:")
    record_count = collection.count_documents({})
    print(f"   Total intake records: {record_count}")

    # Show recent records
    recent_records = collection.find().sort("created_at", -1).limit(5)
    print("   Recent records:")
    for record in recent_records:
        print(
            f"   - {record['intake_id']}: {record['file_id']} ({record['processing_status']})"
        )

    print("\n=== Test completed ===")


if __name__ == "__main__":
    main()
