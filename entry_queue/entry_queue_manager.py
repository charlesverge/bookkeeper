"""
Entry Queue Manager - Central coordination point for document intake operations.

This module handles duplicate detection, queue management, and status tracking
for documents received from file and email handlers.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from pymongo.collection import Collection
from bson import ObjectId

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Status values for intake records."""

    QUEUED_FOR_EXTRACTION = "queued_for_extraction"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


@dataclass
class FileInfo:
    """File information provided by handlers."""

    file_location: str
    file_id: str
    source: str
    date: datetime


@dataclass
class DuplicateResult:
    """Result of duplicate detection check."""

    is_duplicate: bool
    existing_id: Optional[ObjectId] = None
    message: Optional[str] = None


@dataclass
class IntakeRecord:
    """Data structure for tracking intake operations."""

    _id: ObjectId
    file_location: str
    file_id: str
    source: str
    date: datetime
    processing_status: str
    created_at: datetime
    updated_at: datetime
    status_details: Optional[Dict[str, Any]] = None


class DatabaseError(Exception):
    """Database operation errors."""

    pass


class QueueError(Exception):
    """Queue operation errors."""

    pass


class ValidationError(Exception):
    """File info validation errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class DuplicateChecker:
    """Handles duplicate detection operations."""

    def __init__(self, intake_records_collection: Collection):
        self.intake_records_collection = intake_records_collection

    def check_duplicate(
        self, file_location: str, file_id: str, source: str, date: datetime
    ) -> DuplicateResult:
        """
        Check if this combination has been processed before:
        - file_location: Path or identifier of the file
        - file_id: Unique identifier for the file
        - source: Source system/method (email, upload, etc.)
        - date: Date of the file/processing
        """
        try:
            # Check for exact match of location, id, source, and date combination
            existing_record = self.intake_records_collection.find_one(
                {
                    "file_location": file_location,
                    "file_id": file_id,
                    "source": source,
                    "date": date,
                }
            )

            if existing_record:
                return DuplicateResult(
                    is_duplicate=True,
                    existing_id=existing_record["_id"],
                    message=f"Already processed: {existing_record['processing_status']}",
                )

            return DuplicateResult(is_duplicate=False)

        except Exception as e:
            logger.error(f"Error checking duplicates: {e}")
            raise DatabaseError(f"Failed to check duplicates: {str(e)}")


class EntryQueueManager:
    """Central orchestrator for all intake operations."""

    def __init__(self, intake_records_collection: Collection):
        self.intake_records_collection = intake_records_collection
        self.duplicate_checker = DuplicateChecker(intake_records_collection)

    def process_file_request(self, file_info: FileInfo) -> Dict[str, Any]:
        """
        Process file request from file handler.

        Args:
            file_info: File information provided by file handler

        Returns:
            Dict containing processing result
        """
        try:
            # Validate file info
            self._validate_file_info(file_info)

            # Check for duplicates
            duplicate_result = self.duplicate_checker.check_duplicate(
                file_info.file_location,
                file_info.file_id,
                file_info.source,
                file_info.date,
            )

            if duplicate_result.is_duplicate:
                logger.info(
                    f"Duplicate detected for {file_info.file_id}: {duplicate_result.message}"
                )
                return {
                    "status": "duplicate",
                    "existing_id": duplicate_result.existing_id,
                    "message": duplicate_result.message,
                }

            # Create intake record
            intake_record = self._create_intake_record(file_info)

            # Queue for extractor
            self._queue_for_extraction(file_info, intake_record._id)

            logger.info(f"Successfully processed file request for {file_info.file_id}")
            return {
                "status": "success",
                "_id": intake_record._id,
                "processing_status": intake_record.processing_status,
            }

        except ValidationError as e:
            return {"status": "error", "message": str(e), "details": e.details}

        except DatabaseError as e:
            return {"status": "error", "message": "Database error occurred"}

        except QueueError as e:
            return {"status": "error", "message": "Queue error occurred"}

        except Exception as e:
            logger.error(f"Unexpected error processing file request: {e}")
            return {"status": "error", "message": "Unexpected error occurred"}

    def process_email_request(self, file_info: FileInfo) -> Dict[str, Any]:
        """
        Process email request from email handler.

        Args:
            file_info: Email attachment information provided by email handler

        Returns:
            Dict containing processing result
        """
        # Email requests use the same logic as file requests
        return self.process_file_request(file_info)

    def update_intake_status(
        self, intake_id: ObjectId, status: str, details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update intake record processing status.

        Args:
            intake_id: ID of the intake record
            status: New processing status
            details: Optional status details

        Returns:
            True if update successful, False otherwise
        """
        try:
            update_data = {"processing_status": status, "updated_at": datetime.now()}

            if details:
                update_data["status_details"] = details

            result = self.intake_records_collection.update_one(
                {"_id": intake_id}, {"$set": update_data}
            )
            logger.info(f"Updated intake status for {intake_id}: {status}")
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Failed to update intake status for {intake_id}: {e}")
            return False

    def get_intake_record(self, intake_id: ObjectId) -> Optional[IntakeRecord]:
        """
        Retrieve intake record by ID.

        Args:
            intake_id: ID of the intake record

        Returns:
            IntakeRecord if found, None otherwise
        """
        try:
            record_data = self.intake_records_collection.find_one({"_id": intake_id})
            if record_data:
                return IntakeRecord(
                    _id=record_data["_id"],
                    file_location=record_data["file_location"],
                    file_id=record_data["file_id"],
                    source=record_data["source"],
                    date=record_data["date"],
                    processing_status=record_data["processing_status"],
                    created_at=record_data["created_at"],
                    updated_at=record_data["updated_at"],
                    status_details=record_data.get("status_details"),
                )
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve intake record {intake_id}: {e}")
            return None

    def _validate_file_info(self, file_info: FileInfo):
        """Validate file information from handlers."""
        errors = {}

        if not file_info.file_location:
            errors["file_location"] = "File location is required"

        if not file_info.file_id:
            errors["file_id"] = "File ID is required"

        if not file_info.source:
            errors["source"] = "Source is required"

        if not file_info.date:
            errors["date"] = "Date is required"

        if errors:
            raise ValidationError("File info validation failed", errors)

    def _create_intake_record(self, file_info: FileInfo) -> IntakeRecord:
        """Create intake record for tracking purposes."""
        try:
            intake_record = IntakeRecord(
                _id=ObjectId(),
                file_location=file_info.file_location,
                file_id=file_info.file_id,
                source=file_info.source,
                date=file_info.date,
                processing_status=ProcessingStatus.QUEUED_FOR_EXTRACTION.value,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            record_dict = asdict(intake_record)
            self.intake_records_collection.insert_one(record_dict)
            logger.info(f"Created intake record {intake_record._id}")
            return intake_record

        except Exception as e:
            logger.error(f"Failed to create intake record: {e}")
            raise DatabaseError(f"Failed to create intake record: {str(e)}")

    def _queue_for_extraction(self, file_info: FileInfo, intake_id: ObjectId):
        """Queue file for extractor processing."""
        # File is already queued via the intake record in MongoDB with status QUEUED_FOR_EXTRACTION
        logger.info(f"Queued {intake_id} for extraction")

    def get_extraction_queue(self) -> list:
        """Get current extraction queue from MongoDB."""
        try:
            queued_records = self.intake_records_collection.find(
                {"processing_status": ProcessingStatus.QUEUED_FOR_EXTRACTION.value}
            ).sort("created_at", 1)

            queue_items = []
            for record in queued_records:
                queue_items.append(
                    {
                        "_id": record["_id"],
                        "file_location": record["file_location"],
                        "file_id": record["file_id"],
                        "source": record["source"],
                        "date": (
                            record["date"].isoformat()
                            if hasattr(record["date"], "isoformat")
                            else str(record["date"])
                        ),
                        "queued_at": (
                            record["created_at"].isoformat()
                            if hasattr(record["created_at"], "isoformat")
                            else str(record["created_at"])
                        ),
                    }
                )
            return queue_items
        except Exception as e:
            logger.error(f"Failed to get extraction queue: {e}")
            return []

    def clear_extraction_queue(self):
        """Clear the extraction queue by updating all queued records to failed status."""
        try:
            result = self.intake_records_collection.update_many(
                {"processing_status": ProcessingStatus.QUEUED_FOR_EXTRACTION.value},
                {
                    "$set": {
                        "processing_status": ProcessingStatus.FAILED.value,
                        "updated_at": datetime.now(),
                        "status_details": {"reason": "Queue cleared"},
                    }
                },
            )
            logger.info(
                f"Cleared extraction queue - updated {result.modified_count} records"
            )
        except Exception as e:
            logger.error(f"Failed to clear extraction queue: {e}")

    def pop_from_extraction_queue(self) -> Optional[Dict[str, Any]]:
        """Pop the next item from extraction queue by updating its status to processing."""
        try:
            queued_record = self.intake_records_collection.find_one(
                {"processing_status": ProcessingStatus.QUEUED_FOR_EXTRACTION.value},
                sort=[("created_at", 1)],
            )

            if queued_record:
                self.intake_records_collection.update_one(
                    {"_id": queued_record["_id"]},
                    {
                        "$set": {
                            "processing_status": ProcessingStatus.PROCESSING.value,
                            "updated_at": datetime.now(),
                        }
                    },
                )

                item = {
                    "_id": queued_record["_id"],
                    "file_location": queued_record["file_location"],
                    "file_id": queued_record["file_id"],
                    "source": queued_record["source"],
                    "date": (
                        queued_record["date"].isoformat()
                        if hasattr(queued_record["date"], "isoformat")
                        else str(queued_record["date"])
                    ),
                    "queued_at": (
                        queued_record["created_at"].isoformat()
                        if hasattr(queued_record["created_at"], "isoformat")
                        else str(queued_record["created_at"])
                    ),
                }
                logger.info(f"Popped {item['_id']} from extraction queue")
                return item
            return None
        except Exception as e:
            logger.error(f"Failed to pop from extraction queue: {e}")
            return None
