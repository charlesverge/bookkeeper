# Bookkeeper Agent - Project Specifications

## Project Overview

The Bookkeeper Agent is an intelligent financial management system that automates expense tracking and reporting by processing emails, extracting financial information, classifying expenses, and storing data in MongoDB. The system leverages LangGraph for AI-powered decision making and workflow orchestration.

## Core Features

### Document Processing Workflow

The Bookkeeper Agent follows a simple three-step process:

1. **Input**: Files are uploaded manually or emails are retrieved from email providers
2. **Queue**: Documents are added to the Entry Queue Manager for tracking and processing
3. **Extraction**: The Extractor processes queued documents and saves invoice/receipt information to MongoDB collections

#### Starting Points

**File Upload**: Users manually upload documents (invoices, receipts, PDFs, images) via File Handler
**Email Retrieval**: Email Handler retrieves emails and adds each attachment to entry queue separately

### Data Management

- Store processed data in MongoDB
- Implement proper indexing for performance

### Reporting & Analytics

- Generate expense reports for specific date ranges
- Breakdown expenses by category and type
- Calculate total amounts for expense and tax
- Export reports in CSV

## Technology Stack

- **Primary Language**: Python 3.12+
- **Database**: MongoDB for data storage
- **Email Processing**: IMAP/OAuth2 for email access
- **Document Processing**: OCR and text extraction libraries

## Architecture Components

### Core Libraries and Classes

#### Email Handler (`email_handler/`)

**Purpose**: Retrieve emails and add attachments/content to entry queue

**Key Classes**:

- `EmailClient`: Connect to email providers (Gmail, Outlook, etc.)
- `EmailProcessor`: Process email content and attachments
- `AttachmentExtractor`: Extract attachments from emails

**Key Methods**:

- `connect()`: Establish email connection
- `retrieve_emails(labels: [str])`: Retrieve emails with specific labels
- `process_email(email: dict)`: Process email and add each attachment to entry queue
- `extract_attachments(email: dict)`: Extract all attachments from email
- `add_to_entry_queue(attachment: dict)`: Add individual attachment to entry queue

#### File Handler (`file_handler/`)

**Purpose**: Process individual files from various sources (email attachments, manual uploads, email body text)

**Key Classes**:

- `FileUploadHandler`: Handle manual file uploads
- `FileValidator`: Validate uploaded files

**Key Methods**:

- `upload_file(file_path: str, metadata: dict)`: Process uploaded file and add to entry queue
- `validate_file(file_data: bytes)`: Ensure file is valid for processing

#### Entry Queue Manager (`entry_queue/`)

**Purpose**: Manage document intake queue and duplicate detection

**Key Classes**:

- `EntryQueueManager`: Main queue orchestrator
- `DuplicateChecker`: Check for previously processed documents
- `IntakeRecord`: Data structure for tracking queued documents

**Key Methods**:

- `add_to_queue(file_info: dict)`: Add document to processing queue
- `get_next_item()`: Get next document from queue for processing
- `check_duplicate(file_hash: str)`: Verify if document was previously processed
- `update_status(intake_id: str, status: str)`: Update processing status

#### Extractor (`extractor/`)

**Purpose**: Extract invoice and receipt information from queued documents

**Key Classes**:

- `DocumentExtractor`: Main extraction orchestrator
- `InvoiceExtractor`: Extract invoice-specific information
- `ReceiptExtractor`: Extract receipt-specific information
- `DocumentClassifier`: Determine if document is invoice or receipt

**Key Methods**:

- `process_queue_item(queue_entry: dict)`: Process queued document and save to MongoDB
- `extract_invoice_data(document: bytes)`: Extract invoice information
- `extract_receipt_data(document: bytes)`: Extract receipt information
- `save_to_invoices_collection(invoice_data: dict)`: Save invoice to MongoDB
- `save_to_receipts_collection(receipt_data: dict)`: Save receipt to MongoDB

## Data Models

### Currency Storage Convention

All monetary amounts are stored as integers in the smallest currency unit (e.g., cents for USD).
For example: $123.45 is stored as 12345 (cents).

### Date Storage Convention

All dates are stored as datetime objects in MongoDB for consistent date handling and timezone support.

### Intake Record Schema

```python
{
    "_id": ObjectId,
    "batch_id": str,  # Groups multiple files from same source
    "document_type": str,  # "receipt", "invoice", "other", "ignored"
    "source_type": str,  # "file_upload" or "email_attachment"
    "source_identifier": str,  # file path or email ID
    "source_hash": str,  # for duplicate detection
    "original_filename": str,
    "intake_date": datetime,
    "processing_status": str,  # "pending", "processing", "completed", "failed", "ignored"
    "unique_directory": str,  # Path to unique directory storing originals
    "metadata": {
        # Common fields
        "identifier": str,
        "date": datetime,
        "source": str,

        # Email source specific fields
        "email_subject": str,  # Only present if source_type = "email_attachment"
        "email_sender": str,   # Only present if source_type = "email_attachment"
        "email_body_preview": str,  # Only present if source_type = "email_attachment"

        # File upload specific fields
        "upload_user": str,    # Only present if source_type = "file_upload"
        "upload_notes": str,   # Only present if source_type = "file_upload"
        "manual_classification": str  # Only present if source_type = "file_upload"
    },
    "created_at": datetime,
    "updated_at": datetime
}
```

### Invoice Collection Schema

```python
{
    "_id": ObjectId,
    "intake_id": ObjectId,  # Reference to intake record
    "invoice_number": str,
    "vendor": str,
    "issue_date": datetime,
    "due_date": datetime,
    "amount": int,  # Stored in smallest currency unit (e.g., cents)
    "currency": str,
    "tax_amount": int,  # Stored in smallest currency unit (e.g., cents)
    "description": str,
    "line_items": [
        {
            "description": str,
            "quantity": int,
            "unit_price": int,  # Stored in smallest currency unit (e.g., cents)
            "total": int  # Stored in smallest currency unit (e.g., cents)
        }
    ],
    "payment_terms": str,
    "status": str,  # "pending", "paid", "overdue", "cancelled"
    "receipt_id": ObjectId,  # Reference to associated receipt (if exists)
    "created_at": datetime,
    "updated_at": datetime
}
```

### Receipt Collection Schema

```python
{
    "_id": ObjectId,
    "receipt_id": ObjectId,
    "intake_id": ObjectId,  # Reference to intake record
    "receipt_number": str,
    "vendor": str,
    "transaction_date": datetime,
    "amount": int,  # Stored in smallest currency unit (e.g., cents)
    "currency": str,
    "tax_amount": int,  # Stored in smallest currency unit (e.g., cents)
    "payment_method": str,
    "description": str,
    "line_items": [
        {
            "description": str,
            "quantity": int,
            "unit_price": int,  # Stored in smallest currency unit (e.g., cents)
            "total": int  # Stored in smallest currency unit (e.g., cents)
        }
    ],
    "created_at": datetime,
    "updated_at": datetime
}
```

## Configuration Requirements

### Environment Variables

- `MONGODB_URI`: MongoDB connection string
- `GMAIL_CLIENT_ID`: Gmail OAuth2 client ID
- `GMAIL_CLIENT_SECRET`: Gmail OAuth2 client secret
- `OPENAI_API_KEY`: OpenAI API key (if using GPT models)
- `LOG_LEVEL`: Application logging level
