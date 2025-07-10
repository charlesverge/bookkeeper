"""
Document Extractor - Main extraction orchestrator for financial documents.

This module processes documents from the entry queue, extracts financial information
from invoices and receipts using OCR and AI, and returns structured data.
"""

import os
import io
import logging
import base64
import uuid
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

import PyPDF2
import pytesseract
from PIL import Image
import html2text
from bs4 import BeautifulSoup
import openai
from dotenv import load_dotenv
import pymongo
from pymongo import MongoClient
from pymongo.errors import (
    ConnectionFailure,
    ServerSelectionTimeoutError,
    DuplicateKeyError,
)
from bson import ObjectId

from entry_queue.entry_queue_manager import EntryQueueManager, ProcessingStatus

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class DocumentExtractionError(Exception):
    """Base exception for document extraction errors."""

    pass


class TextExtractionError(DocumentExtractionError):
    """Exception raised when text extraction fails."""

    pass


class ClassificationError(DocumentExtractionError):
    """Exception raised when document classification fails."""

    pass


class StructuredExtractionError(DocumentExtractionError):
    """Exception raised when structured data extraction fails."""

    pass


class DatabaseSaveError(DocumentExtractionError):
    """Exception raised when saving to database fails."""

    pass


class InvalidDocumentError(DocumentExtractionError):
    """Exception raised when document is invalid or corrupted."""

    pass


class DocumentType(Enum):
    """Document type classifications."""

    INVOICE = "invoice"
    RECEIPT = "receipt"
    OTHER = "other"


@dataclass
class CompanyInfo:
    """Company information structure."""

    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    tax_id: Optional[str] = None


@dataclass
class LineItem:
    """Individual line item structure."""

    description: str
    quantity: Optional[int] = None
    unit_price: Optional[int] = None
    total_price: Optional[int] = None


@dataclass
class ExtractedData:
    """Structured extracted document data."""

    document_type: DocumentType
    document_number: Optional[str]
    date: Optional[datetime]
    due_date: Optional[datetime]
    from_company: Optional[CompanyInfo]
    to_company: Optional[CompanyInfo]
    line_items: List[LineItem]
    subtotal: Optional[int]
    tax_amount: Optional[int]
    total_amount: Optional[int]
    payment_method: Optional[str]
    currency: Optional[str]
    raw_text: str


class DocumentExtractor:
    """Main extraction orchestrator for processing financial documents."""

    def __init__(
        self, queue_manager: EntryQueueManager, mongodb_uri: Optional[str] = None
    ):
        """
        Initialize the DocumentExtractor.

        Args:
            queue_manager: Entry queue manager instance
            mongodb_uri: MongoDB connection URI (optional, defaults to env var)

        Raises:
            ValueError: If required configuration is missing
            ConnectionFailure: If MongoDB connection fails
            DocumentExtractionError: If initialization fails
        """
        try:
            # Validate inputs
            if not queue_manager:
                raise ValueError("Queue manager is required")

            self.queue_manager = queue_manager

            # Initialize OpenAI client with error handling
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")

            try:
                self.openai_client = openai.Client(api_key=api_key)
            except openai.AuthenticationError:
                raise ValueError("Invalid OpenAI API key")
            except openai.APIError as e:
                logger.warning(f"OpenAI API test failed, but continuing: {e}")

            # Initialize MongoDB connection
            self.mongodb_uri = mongodb_uri or os.getenv("MONGODB_URL", "")

            self._initialize_mongodb_connection()

            # Initialize HTML to text converter
            try:
                self.html_converter = html2text.HTML2Text()
                self.html_converter.ignore_links = True
                self.html_converter.ignore_images = True
            except Exception as e:
                logger.error(f"Failed to initialize HTML converter: {e}")
                raise DocumentExtractionError(
                    f"HTML converter initialization failed: {e}"
                )

            logger.info("DocumentExtractor initialized successfully")

        except (ValueError, ConnectionFailure) as e:
            logger.error(f"Configuration error during initialization: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize DocumentExtractor: {e}")
            raise DocumentExtractionError(f"Initialization failed: {e}")

    def _initialize_mongodb_connection(self):
        """Initialize MongoDB connection without retry logic."""
        try:
            self.mongo_client = MongoClient(
                self.mongodb_uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=5000,
            )

            # Test the connection
            self.mongo_client.admin.command("ping")

            self.db = self.mongo_client.bookkeeper
            self.invoices_collection = self.db.invoices
            self.receipts_collection = self.db.receipts

            logger.info("MongoDB connection established successfully")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise ConnectionFailure(f"Failed to connect to MongoDB: {e}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            raise

    def process_next_document(self) -> Optional[ExtractedData]:
        """
        Process the next document from the extraction queue.

        Returns:
            ExtractedData if document processed successfully, None if queue is empty
        """
        queue_item = None
        try:
            # Get next item from queue
            queue_item = self.queue_manager.pop_from_extraction_queue()
            if not queue_item:
                logger.info("No documents in extraction queue")
                return None

            intake_id = queue_item.get("_id")
            if not intake_id:
                logger.error("Queue item missing _id")
                return None

            logger.info(f"Processing document: {intake_id}")

            # Validate queue item structure
            if not self._validate_queue_item(queue_item):
                error_msg = f"Invalid queue item structure: {queue_item}"
                self._update_status_to_failed(intake_id, error_msg)
                raise ValueError(error_msg)

            # Extract text from document
            raw_text = self._extract_text_from_document(queue_item["file_location"])

            if not raw_text or not raw_text.strip():
                error_msg = "No text could be extracted from document"
                self._update_status_to_failed(intake_id, error_msg)
                raise TextExtractionError(error_msg)

            # Classify document type
            document_type = self._classify_document(raw_text)

            # Skip structured extraction for "other" document types
            if document_type == DocumentType.OTHER:
                logger.info(
                    f"Document {intake_id} classified as 'other', skipping structured extraction"
                )
                final_status = ProcessingStatus.COMPLETED.value
                completion_details = {
                    "extraction_completed_at": datetime.now(),
                    "document_type": document_type.value,
                    "note": "Structured extraction skipped for 'other' document type",
                }
                is_complete = True  # For logging purposes
                missing_fields = []
                saved_id = None
            else:
                # Extract structured data using AI
                extracted_data = self._extract_structured_data(raw_text, document_type)

                # Validate extracted data for completeness
                is_complete, missing_fields = (
                    self._validate_extracted_data_for_completeness(extracted_data)
                )

                # Save extracted data to appropriate MongoDB collection
                saved_id = None
                if extracted_data.document_type == DocumentType.INVOICE:
                    saved_id = self._save_to_invoices_collection(
                        extracted_data, intake_id, is_complete, missing_fields
                    )
                elif extracted_data.document_type == DocumentType.RECEIPT:
                    saved_id = self._save_to_receipts_collection(
                        extracted_data, intake_id, is_complete, missing_fields
                    )

                # Always mark intake as COMPLETED since extraction finished successfully
                final_status = ProcessingStatus.COMPLETED.value
                completion_details = {
                    "extraction_completed_at": datetime.now(),
                    "document_type": extracted_data.document_type.value,
                    "validation_status": (
                        "complete" if is_complete else "requires_review"
                    ),
                }

                if not is_complete:
                    completion_details.update(
                        {
                            "missing_fields": missing_fields,
                            "review_reason": f"Missing required fields: {', '.join(missing_fields)}",
                        }
                    )

                if saved_id:
                    completion_details["saved_document_id"] = saved_id

            success = self.queue_manager.update_intake_status(
                intake_id,
                final_status,
                completion_details,
            )

            if not success:
                logger.warning(f"Failed to update status for {intake_id}")

            if document_type == DocumentType.OTHER:
                logger.info(f"Successfully processed 'other' document: {intake_id}")
                return None
            else:
                if is_complete:
                    logger.info(
                        f"Successfully processed document: {intake_id}, saved as: {saved_id}, status: COMPLETED"
                    )
                else:
                    logger.info(
                        f"Processed document with missing fields: {intake_id}, saved as: {saved_id}, status: REVIEW, missing: {', '.join(missing_fields)}"
                    )
                return extracted_data

        except Exception as e:
            # Update status to failed with detailed error information
            if queue_item:
                intake_id = queue_item.get("_id")
                error_msg = str(e)
                if intake_id:
                    self._update_status_to_failed(intake_id, error_msg)

            logger.error(
                f"Failed to process document {queue_item.get('_id', 'unknown') if queue_item else 'unknown'}: {e}"
            )
            return None

    def _update_status_to_failed(self, intake_id: ObjectId, error_message: str):
        """
        Update intake record status to failed with error message.

        Args:
            intake_id: The intake record ID
            error_message: The error message to store
        """
        try:
            error_details = {
                "error_message": error_message,
                "error_type": type(Exception).__name__,
                "failed_at": datetime.now().isoformat(),
            }

            success = self.queue_manager.update_intake_status(
                intake_id,
                ProcessingStatus.FAILED.value,
                error_details,
            )

            if not success:
                logger.error(f"Failed to update status to failed for {intake_id}")

        except Exception as e:
            logger.error(f"Error updating status to failed for {intake_id}: {e}")

    def _validate_queue_item(self, queue_item: Dict[str, Any]) -> bool:
        """
        Validate queue item structure.

        Args:
            queue_item: Queue item to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            required_fields = ["_id", "file_location", "file_id", "source"]
            for field in required_fields:
                if field not in queue_item:
                    logger.error(f"Missing required field in queue item: {field}")
                    return False
                if not queue_item[field]:
                    logger.error(f"Empty required field in queue item: {field}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error validating queue item: {e}")
            return False

    def _extract_text_from_document(self, file_location: str) -> str:
        """
        Extract text from various document formats.

        Args:
            file_location: Path to the document file

        Returns:
            Extracted text content

        Raises:
            TextExtractionError: If text extraction fails
            FileNotFoundError: If file doesn't exist
            InvalidDocumentError: If document is corrupted or invalid
        """
        try:
            # Input validation
            if not file_location:
                raise ValueError("File location cannot be empty")

            if not isinstance(file_location, str):
                raise ValueError(
                    f"File location must be a string, got {type(file_location)}"
                )

            if not os.path.exists(file_location):
                raise FileNotFoundError(f"File not found: {file_location}")

            # Check file size (prevent processing extremely large files)
            try:
                file_size = os.path.getsize(file_location)
                max_size = 100 * 1024 * 1024  # 100MB limit
                if file_size > max_size:
                    raise InvalidDocumentError(
                        f"File too large: {file_size} bytes (max: {max_size})"
                    )
                if file_size == 0:
                    raise InvalidDocumentError("File is empty")
            except OSError as e:
                raise TextExtractionError(f"Cannot access file {file_location}: {e}")

            file_extension = os.path.splitext(file_location)[1].lower()

            try:
                if file_extension == ".pdf":
                    return self._extract_text_from_pdf(file_location)
                elif file_extension in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
                    return self._extract_text_from_image(file_location)
                elif file_extension in [".html", ".htm"]:
                    return self._extract_text_from_html(file_location)
                elif file_extension == ".txt":
                    return self._extract_text_from_txt(file_location)
                else:
                    logger.warning(f"Unknown file type {file_extension}, trying OCR")
                    return ""

            except (FileNotFoundError, InvalidDocumentError):
                # Re-raise these without wrapping
                raise
            except Exception as e:
                raise TextExtractionError(
                    f"Failed to extract text from {file_extension} file: {e}"
                )

        except (FileNotFoundError, ValueError, InvalidDocumentError) as e:
            logger.error(f"File access error for {file_location}: {e}")
            raise
        except TextExtractionError:
            # Re-raise without wrapping
            raise
        except Exception as e:
            logger.error(f"Unexpected error extracting text from {file_location}: {e}")
            raise TextExtractionError(f"Unexpected extraction error: {e}")

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF using PyPDF2."""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"PDF file not found: {file_path}")

            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)

                if len(pdf_reader.pages) == 0:
                    logger.warning(f"PDF file {file_path} has no pages")
                    return ""

                text = ""
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        text += page_text + "\n"
                    except Exception as e:
                        logger.warning(
                            f"Failed to extract text from page {page_num} in {file_path}: {e}"
                        )
                        continue

                # If no text extracted, try OCR on each page
                if not text.strip():
                    logger.info("No text found in PDF, attempting OCR")
                    # This would require converting PDF pages to images first
                    # For now, return empty string
                    text = ""

                return text.strip()

        except FileNotFoundError:
            raise
        except Exception as e:
            if "PDF" in str(e) or "pdf" in str(e):
                logger.error(f"PDF read error for {file_path}: {e}")
            else:
                logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise

    def _extract_text_from_image(self, file_path: str) -> str:
        """Extract text from image using OCR (pytesseract)."""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Image file not found: {file_path}")

            image = Image.open(file_path)

            # Verify image is valid
            image.verify()

            # Reopen image for OCR (verify() closes the image)
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text.strip()

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error extracting text from image {file_path}: {e}")
            raise

    def _extract_text_from_html(self, file_path: str) -> str:
        """Extract text from HTML file."""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"HTML file not found: {file_path}")

            with open(file_path, "r", encoding="utf-8") as file:
                html_content = file.read()

            if not html_content.strip():
                logger.warning(f"HTML file {file_path} is empty")
                return ""

            # Use html2text for clean conversion
            text = self.html_converter.handle(html_content)
            return text.strip()

        except FileNotFoundError:
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading HTML file {file_path}: {e}")
            # Try with different encoding
            try:
                with open(file_path, "r", encoding="latin-1") as file:
                    html_content = file.read()
                text = self.html_converter.handle(html_content)
                return text.strip()
            except Exception as fallback_e:
                logger.error(
                    f"Failed to read HTML file with fallback encoding: {fallback_e}"
                )
                raise
        except Exception as e:
            logger.error(f"Error extracting text from HTML {file_path}: {e}")
            raise

    def _extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from plain text file."""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Text file not found: {file_path}")

            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read().strip()

            if not content:
                logger.warning(f"Text file {file_path} is empty")

            return content

        except FileNotFoundError:
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading text file {file_path}: {e}")
            # Try with different encoding
            try:
                with open(file_path, "r", encoding="latin-1") as file:
                    return file.read().strip()
            except Exception as fallback_e:
                logger.error(
                    f"Failed to read text file with fallback encoding: {fallback_e}"
                )
                raise
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            raise

    def _classify_document(self, text: str) -> DocumentType:
        """
        Classify document type using OpenAI API.

        Args:
            text: Extracted text content

        Returns:
            DocumentType classification
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for classification")
                return DocumentType.OTHER

            # Truncate text if too long to avoid API limits
            max_chars = 8000  # Leave room for prompt
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
                logger.info(
                    f"Truncated text to {max_chars} characters for classification"
                )

            prompt = f"""
            Analyze the following document text and determine if it is an invoice, receipt, or other type of document.

            Document text:
            {text}

            Respond with only one word: "invoice", "receipt", or "other"
            
            Guidelines:
            - Invoice: A bill requesting payment, typically has due date, invoice number, "amount due"
            - Receipt: Proof of payment made, typically shows payment method, transaction completed
            - Other: Any document that doesn't fit invoice or receipt categories
            """

            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a document classification expert. Respond with only one word.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=10,
                    temperature=0,
                    timeout=30,  # 30 second timeout
                )

                if not response.choices or not response.choices[0].message.content:
                    logger.error(
                        "Empty response from OpenAI classification API, defaulting to OTHER"
                    )
                    return DocumentType.OTHER

                classification = response.choices[0].message.content.strip().lower()

                # Validate classification response
                valid_classifications = ["invoice", "receipt", "other"]
                if classification not in valid_classifications:
                    logger.warning(
                        f"Invalid classification response: {classification}, defaulting to 'other'"
                    )
                    return DocumentType.OTHER

                if classification == "invoice":
                    return DocumentType.INVOICE
                elif classification == "receipt":
                    return DocumentType.RECEIPT
                else:
                    return DocumentType.OTHER

            except (
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.APIError,
            ) as e:
                logger.error(
                    f"OpenAI API error during classification: {e}, defaulting to OTHER"
                )
                return DocumentType.OTHER

        except Exception as e:
            logger.error(
                f"Unexpected error classifying document: {e}, defaulting to OTHER"
            )
            return DocumentType.OTHER

    def _extract_structured_data(
        self, text: str, document_type: DocumentType
    ) -> ExtractedData:
        """
        Extract structured data from document text using OpenAI API.

        Args:
            text: Raw document text
            document_type: Classified document type

        Returns:
            ExtractedData with structured information
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for structured extraction")
                return self._create_fallback_extracted_data(document_type, text)

            prompt = f"""
            Extract structured information from this {document_type.value} document.
            
            Document text:
            {text}
            
            Please extract and return the following information in JSON format:
            {{
                "document_number": "document/invoice/receipt number",
                "date": "document date (YYYY-MM-DD format)",
                "due_date": "due date if applicable (YYYY-MM-DD format)",
                "from_company": {{
                    "name": "company name issuing the document",
                    "address": "company address",
                    "phone": "phone number",
                    "email": "email address",
                    "tax_id": "tax ID or business number"
                }},
                "to_company": {{
                    "name": "company/person receiving the document",
                    "address": "recipient address",
                    "phone": "phone number",
                    "email": "email address",
                    "tax_id": "tax ID if applicable"
                }},
                "line_items": [
                    {{
                        "description": "item description",
                        "quantity": 1,
                        "unit_price": 10.00,
                        "total_price": 10.00
                    }}
                ],
                "subtotal": 10.00,
                "tax_amount": 1.00,
                "total_amount": 11.00,
                "payment_method": "payment method if specified",
                "currency": "currency code (CAD, USD, EUR, etc.) default is CAD"
            }}
            
            Instructions:
            - Extract all line items with their descriptions, quantities, and prices
            - Include tax amount and total amount
            - Use null for missing information
            - Return only valid JSON
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a document data extraction expert. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0,
            )

            if not response.choices or not response.choices[0].message.content:
                logger.error("Empty response from OpenAI extraction API")
                return self._create_fallback_extracted_data(document_type, text)

            json_response = response.choices[0].message.content.strip()

            # Parse the JSON response
            try:
                if "```json" in json_response:
                    start = json_response.find("```json") + len("```json")
                    end = json_response.rfind("```", start)
                    json_response = json_response[start:end].strip()
                extracted_json = json.loads(json_response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response from OpenAI: {e}")
                logger.debug(f"Raw response: {json_response}")
                return self._create_fallback_extracted_data(document_type, text)

            # Convert to ExtractedData structure
            from_company = None
            if extracted_json.get("from_company"):
                from_info = extracted_json["from_company"]
                from_company = CompanyInfo(
                    name=from_info.get("name"),
                    address=from_info.get("address"),
                    phone=from_info.get("phone"),
                    email=from_info.get("email"),
                    tax_id=from_info.get("tax_id"),
                )

            to_company = None
            if extracted_json.get("to_company"):
                to_info = extracted_json["to_company"]
                to_company = CompanyInfo(
                    name=to_info.get("name"),
                    address=to_info.get("address"),
                    phone=to_info.get("phone"),
                    email=to_info.get("email"),
                    tax_id=to_info.get("tax_id"),
                )

            def parse_date(date_str):
                if not date_str:
                    return None
                try:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except:
                    try:
                        return datetime.strptime(date_str, "%Y-%m-%d")
                    except:
                        return None

            def convert_to_cents(amount):
                if amount is None:
                    return None
                if isinstance(amount, (int, float)):
                    return int(amount * 100)
                return None

            def convert_to_int(value):
                if value is None:
                    return None
                if isinstance(value, (int, float)):
                    return int(value)
                return None

            line_items = []
            for item in extracted_json.get("line_items", []):
                line_items.append(
                    LineItem(
                        description=item.get("description", ""),
                        quantity=convert_to_int(item.get("quantity")),
                        unit_price=convert_to_cents(item.get("unit_price")),
                        total_price=convert_to_cents(item.get("total_price")),
                    )
                )

            return ExtractedData(
                document_type=document_type,
                document_number=extracted_json.get("document_number"),
                date=parse_date(extracted_json.get("date")),
                due_date=parse_date(extracted_json.get("due_date")),
                from_company=from_company,
                to_company=to_company,
                line_items=line_items,
                subtotal=convert_to_cents(extracted_json.get("subtotal")),
                tax_amount=convert_to_cents(extracted_json.get("tax_amount")),
                total_amount=convert_to_cents(extracted_json.get("total_amount")),
                payment_method=extracted_json.get("payment_method"),
                currency=extracted_json.get("currency"),
                raw_text=text,
            )

        except openai.APIError as e:
            logger.error(f"OpenAI API error during structured extraction: {e}")
            return self._create_fallback_extracted_data(document_type, text)
        except Exception as e:
            logger.error(f"Error extracting structured data: {e}")
            return self._create_fallback_extracted_data(document_type, text)

    def _create_fallback_extracted_data(
        self, document_type: DocumentType, text: str
    ) -> ExtractedData:
        """
        Create a fallback ExtractedData structure when extraction fails.

        Args:
            document_type: The classified document type
            text: Raw document text

        Returns:
            Basic ExtractedData structure with raw text
        """
        return ExtractedData(
            document_type=document_type,
            document_number=None,
            date=None,
            due_date=None,
            from_company=None,
            to_company=None,
            line_items=[],
            subtotal=None,
            tax_amount=None,
            total_amount=None,
            payment_method=None,
            currency=None,
            raw_text=text,
        )

    def _save_to_invoices_collection(
        self,
        extracted_data: ExtractedData,
        intake_id: ObjectId,
        is_complete: bool = True,
        missing_fields: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Save invoice data to MongoDB invoices collection.

        Args:
            extracted_data: ExtractedData containing invoice information
            intake_id: Original intake record ID for reference

        Returns:
            String containing the invoice_id of saved record, None if failed
        """
        try:
            # Input validation
            if not extracted_data:
                error_msg = "ExtractedData cannot be None"
                self._update_status_to_failed(intake_id, error_msg)
                raise ValueError(error_msg)
            if not intake_id:
                error_msg = "Intake ID cannot be empty"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate extracted data
            if not self._validate_extracted_data(extracted_data):
                logger.warning(f"Invalid extracted data for invoice {intake_id}")

            # Prepare invoice document with data validation
            missing_fields = missing_fields or []
            invoice_doc = {
                "intake_id": intake_id,
                "document_number": extracted_data.document_number,
                "date": extracted_data.date,
                "due_date": extracted_data.due_date,
                "from_company": (
                    asdict(extracted_data.from_company)
                    if extracted_data.from_company
                    else None
                ),
                "to_company": (
                    asdict(extracted_data.to_company)
                    if extracted_data.to_company
                    else None
                ),
                "line_items": [asdict(item) for item in extracted_data.line_items],
                "subtotal": extracted_data.subtotal,
                "tax_amount": extracted_data.tax_amount,
                "total_amount": extracted_data.total_amount,
                "currency": extracted_data.currency,
                "receipt_id": None,
                "status": "complete" if is_complete else "review",
                "missing_fields": missing_fields if not is_complete else [],
                "raw_text": (
                    extracted_data.raw_text[:10000] if extracted_data.raw_text else None
                ),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            try:
                # Check for duplicates
                existing = self.invoices_collection.find_one({"intake_id": intake_id})
                if existing:
                    logger.warning(f"Invoice already exists for intake_id {intake_id}")
                    return existing.get("_id")

                # Insert into MongoDB
                result = self.invoices_collection.insert_one(invoice_doc)

                if result.inserted_id:
                    logger.info(
                        f"Invoice saved successfully with ID: {result.inserted_id}"
                    )
                    return result.inserted_id
                else:
                    error_msg = "Insert operation returned no ID"
                    self._update_status_to_failed(intake_id, error_msg)
                    return None

            except DuplicateKeyError as e:
                logger.warning(f"Duplicate key error: {e}")
                # Check if the duplicate is for our document
                existing = self.invoices_collection.find_one({"intake_id": intake_id})
                if existing:
                    return existing.get("_id")
                return None

            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                error_msg = f"Database connection error: {e}"
                self._update_status_to_failed(intake_id, error_msg)
                logger.error(error_msg)
                return None

        except ValueError:
            # Already handled above
            return None
        except Exception as e:
            error_msg = f"Unexpected error saving invoice data: {e}"
            self._update_status_to_failed(intake_id, error_msg)
            logger.error(error_msg)
            return None

    def _save_to_receipts_collection(
        self,
        extracted_data: ExtractedData,
        intake_id: ObjectId,
        is_complete: bool = True,
        missing_fields: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Save receipt data to MongoDB receipts collection.

        Args:
            extracted_data: ExtractedData containing receipt information
            intake_id: Original intake record ID for reference

        Returns:
            String containing the receipt_id of saved record, None if failed
        """
        try:
            # Input validation
            if not extracted_data:
                error_msg = "ExtractedData cannot be None"
                self._update_status_to_failed(intake_id, error_msg)
                raise ValueError(error_msg)
            if not intake_id:
                error_msg = "Intake ID cannot be empty"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate extracted data
            if not self._validate_extracted_data(extracted_data):
                logger.warning(f"Invalid extracted data for receipt {intake_id}")

            # Prepare receipt document with data validation
            missing_fields = missing_fields or []
            receipt_doc = {
                "intake_id": intake_id,
                "document_number": extracted_data.document_number,
                "date": extracted_data.date,
                "from_company": (
                    asdict(extracted_data.from_company)
                    if extracted_data.from_company
                    else None
                ),
                "to_company": (
                    asdict(extracted_data.to_company)
                    if extracted_data.to_company
                    else None
                ),
                "line_items": [asdict(item) for item in extracted_data.line_items],
                "subtotal": extracted_data.subtotal,
                "tax_amount": extracted_data.tax_amount,
                "total_amount": extracted_data.total_amount,
                "payment_method": extracted_data.payment_method,
                "currency": extracted_data.currency,
                "status": "complete" if is_complete else "review",
                "missing_fields": missing_fields if not is_complete else [],
                "raw_text": (
                    extracted_data.raw_text[:10000] if extracted_data.raw_text else None
                ),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            try:
                # Check for duplicates
                existing = self.receipts_collection.find_one({"intake_id": intake_id})
                if existing:
                    logger.warning(f"Receipt already exists for intake_id {intake_id}")
                    return existing.get("_id")

                # Insert into MongoDB
                result = self.receipts_collection.insert_one(receipt_doc)

                if result.inserted_id:
                    logger.info(
                        f"Receipt saved successfully with ID: {result.inserted_id}"
                    )
                    return result.inserted_id
                else:
                    error_msg = "Insert operation returned no ID"
                    self._update_status_to_failed(intake_id, error_msg)
                    return None

            except DuplicateKeyError as e:
                logger.warning(f"Duplicate key error: {e}")
                # Check if the duplicate is for our document
                existing = self.receipts_collection.find_one({"intake_id": intake_id})
                if existing:
                    return existing.get("_id")
                return None

            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                error_msg = f"Database connection error: {e}"
                self._update_status_to_failed(intake_id, error_msg)
                logger.error(error_msg)
                return None

        except ValueError:
            # Already handled above
            return None
        except Exception as e:
            error_msg = f"Unexpected error saving receipt data: {e}"
            self._update_status_to_failed(intake_id, error_msg)
            logger.error(error_msg)
            return None

    def close(self):
        """Close MongoDB connection safely."""
        try:
            if hasattr(self, "mongo_client") and self.mongo_client:
                self.mongo_client.close()
                logger.info("MongoDB connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with error handling."""
        try:
            self.close()
        except Exception as e:
            logger.error(f"Error in context manager exit: {e}")
            # Don't suppress the original exception
            return False

    def _validate_extracted_data(self, extracted_data: ExtractedData) -> bool:
        """
        Validate extracted data structure and content.

        Args:
            extracted_data: ExtractedData to validate

        Returns:
            True if data is valid, False otherwise
        """
        try:
            if not extracted_data:
                return False

            # Check required fields
            if not extracted_data.document_type:
                logger.warning("Missing document type in extracted data")
                return False

            # Validate amounts if present
            if extracted_data.total_amount is not None:
                if not isinstance(extracted_data.total_amount, int):
                    logger.warning("Invalid total_amount type")
                    return False
                if extracted_data.total_amount < 0:
                    logger.warning("Negative total_amount")
                    return False

            if extracted_data.tax_amount is not None:
                if not isinstance(extracted_data.tax_amount, int):
                    logger.warning("Invalid tax_amount type")
                    return False
                if extracted_data.tax_amount < 0:
                    logger.warning("Negative tax_amount")
                    return False

            # Validate line items
            for item in extracted_data.line_items:
                if not item.description:
                    logger.warning("Line item missing description")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating extracted data: {e}")
            return False

    def _validate_extracted_data_for_completeness(
        self, extracted_data: ExtractedData
    ) -> tuple[bool, list[str]]:
        """
        Validate extracted data for completeness and return missing required fields.

        Args:
            extracted_data: ExtractedData to validate

        Returns:
            Tuple of (is_complete, list_of_missing_fields)
        """
        missing_fields = []

        try:
            # Common required fields for both invoices and receipts
            if not extracted_data.total_amount or extracted_data.total_amount <= 0:
                missing_fields.append("total_amount")

            if not extracted_data.date:
                missing_fields.append("date")

            if not extracted_data.from_company or not extracted_data.from_company.name:
                missing_fields.append("from_company_name")

            # Document type specific validations
            if extracted_data.document_type == DocumentType.INVOICE:
                if not extracted_data.document_number:
                    missing_fields.append("invoice_number")

                if not extracted_data.to_company or not extracted_data.to_company.name:
                    missing_fields.append("to_company_name")

            elif extracted_data.document_type == DocumentType.RECEIPT:
                if not extracted_data.document_number:
                    missing_fields.append("receipt_number")

                # Receipts should have at least basic line items or total
                if (
                    not extracted_data.line_items or len(extracted_data.line_items) == 0
                ) and not extracted_data.total_amount:
                    missing_fields.append("line_items_or_total")

            is_complete = len(missing_fields) == 0
            return is_complete, missing_fields

        except Exception as e:
            logger.error(f"Error validating extracted data completeness: {e}")
            return False, ["validation_error"]
