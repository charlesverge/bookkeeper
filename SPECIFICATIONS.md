# Bookkeeper Agent - Project Specifications

## Project Overview

The Bookkeeper Agent is an intelligent financial management system that automates expense tracking and reporting by processing emails, extracting financial information, classifying expenses, and storing data in MongoDB. The system leverages LangGraph for AI-powered decision making and workflow orchestration.

## Core Features

### Email Processing

#### Intake Process

- Accept inputs from multiple sources: file uploads or email sources
- Handle multiple files and invoices within a single input/email
- Process manually uploaded documents, receipts, and email attachments
- Classify documents as receipts, invoices, or other non-financial documents
- Handle various file formats (PDF, images, text files)
- Store original files in unique directories for organization
- Track relationships between invoices and their associated receipts
- Check MongoDB for duplicate processing prevention
- Store both original and processed forms of documents
- Assign unique identifiers and metadata to incoming documents
- Track processing status and source information
- Filter out and ignore non-financial documents (shipping updates, etc.)

#### Email Retrieval Process

- Download emails with specific labels from email providers (Gmail, Outlook, etc.)
- Extract financial information from email content and attachments
- Parse receipts, invoices, and financial documents
- Handle multiple email formats (text, HTML, PDF attachments)

### Expense Classification

- Automatically categorize expenses using AI
- Support custom expense categories
- Learn from user corrections and feedback
- Handle tax-deductible vs non-deductible classifications

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
- **AI Framework**: LangGraph for workflow orchestration
- **Database**: MongoDB for data storage
- **Email Processing**: IMAP/OAuth2 for email access
- **Document Processing**: OCR and text extraction libraries

## Architecture Components

### Core Libraries and Classes

#### Email Handler (`email_handler/`)

**Purpose**: Manage email connectivity and message retrieval

**Key Classes**:

- `EmailClient`: Abstract base class for email providers
- `EmailMessage`: Wrapper for email data structure
- `EmailFilter`: Filter emails by labels, dates, and criteria

**Key Methods**:

- `connect()`: Establish email connection
- `get_messages(labels: [str] | None)`: Retrieve emails with specific labels
- `download_attachments()`: Extract and save attachments

#### File Intake Handler (`file_intake/`)

**Purpose**: Handle manual file uploads and document intake

**Key Classes**:

- `FileIntakeManager`: Main intake orchestrator
- `FileValidator`: Validate incoming files and metadata
- `DocumentClassifier`: Classify documents as receipt, invoice, or other
- `IntakeRecord`: Data structure for intake tracking
- `SourceTracker`: Track document sources and origins
- `DuplicateChecker`: Check for previously processed documents
- `DocumentStore`: Manage original and processed document storage
- `DirectoryManager`: Manage unique directory creation and file organization
- `ReceiptInvoiceLinker`: Manage relationships between invoices and receipts

**Key Methods**:

- `accept_file(file_path: str, identifier: str, date: datetime, source: str)`: Process single incoming file
- `accept_multiple_files(file_paths: [str], identifier: str, date: datetime, source: str)`: Process multiple files as a batch
- `accept_email_source(email_id: str, attachment_paths: [str], date: datetime)`: Process email with multiple attachments
- `classify_document_type(file_content: bytes)`: Determine if document is receipt, invoice, or other
- `link_receipt_to_invoice(receipt_id: str, invoice_id: str)`: Associate receipt with its invoice
- `create_unique_directory()`: Create unique directory for storing original files
- `organize_files_by_batch()`: Organize multiple files within unique directory
- `check_duplicate(source_hash: str)`: Verify if document was previously processed
- `store_original(document: bytes, metadata: dict, directory_path: str)`: Store original document in unique directory
- `store_processed(processed_data: dict, original_id: str)`: Store processed document data
- `filter_non_financial_docs()`: Identify and exclude non-financial documents
- `validate_metadata()`: Ensure required metadata is present
- `assign_unique_id()`: Generate unique document identifiers
- `queue_for_processing()`: Add to processing pipeline

#### Document Processor (`document_processor/`)

**Purpose**: Extract and parse financial information from documents

**Key Classes**:

- `DocumentProcessor`: Main document processing orchestrator
- `PDFProcessor`: Handle PDF documents and invoices
- `ImageProcessor`: Process receipt images with OCR
- `TextExtractor`: Extract structured data from text
- `ReceiptParser`: Specialized receipt parsing logic
- `InvoiceParser`: Specialized invoice parsing logic
- `DocumentTypeDetector`: Identify document types during processing

**Key Methods**:

- `extract_financial_data()`: Main extraction pipeline
- `process_by_document_type(doc_type: str)`: Route processing based on document type
- `parse_amount()`: Extract monetary amounts
- `parse_date()`: Extract transaction dates
- `parse_vendor()`: Identify merchant/vendor
- `extract_line_items()`: Parse itemized expenses
- `detect_receipt_vs_invoice()`: Distinguish between receipt and invoice characteristics
- `extract_invoice_number()`: Extract invoice/receipt numbers for linking

#### Expense Classifier (`expense_classifier/`)

**Purpose**: AI-powered expense categorization and classification

**Key Classes**:

- `ExpenseClassifier`: Main classification engine
- `CategoryModel`: ML model for expense categorization
- `TaxClassifier`: Determine tax deductibility

**Key Methods**:

- `classify_expense()`: Categorize expense type
- `determine_tax_status()`: Assess tax implications
- `get_confidence_score()`: Return classification confidence

#### Data Manager (`data_manager/`)

**Purpose**: MongoDB operations and data persistence

**Key Classes**:

- `DatabaseManager`: MongoDB connection and operations
- `ExpenseModel`: Expense data model/schema
- `ReportModel`: Report data model/schema
- `IntakeModel`: Intake tracking data model/schema
- `DocumentModel`: Original and processed document storage model
- `DataValidator`: Validate data integrity

**Key Methods**:

- `save_expense()`: Store expense records
- `get_expenses()`: Query expense data
- `update_expense()`: Modify existing records
- `delete_expense()`: Remove records
- `save_intake_record()`: Store intake tracking information
- `get_intake_record()`: Query intake records
- `save_document()`: Store original and processed documents
- `check_document_exists()`: Verify if document was previously processed
- `create_indexes()`: Optimize database performance

#### Report Generator (`report_generator/`)

**Purpose**: Generate financial reports and analytics

**Key Classes**:

- `ReportGenerator`: Main reporting engine
- `ExpenseReport`: Standard expense report
- `TaxReport`: Tax-focused reporting
- `CategoryAnalyzer`: Category-based analysis
- `ExportManager`: Handle multiple export formats

**Key Methods**:

- `generate_expense_report()`: Create standard reports
- `generate_tax_summary()`: Tax-specific reporting
- `analyze_spending_patterns()`: Spending analysis
- `export_to_pdf()`: PDF export functionality
- `export_to_csv()`: CSV export functionality

#### LangGraph Workflow (`workflow/`)

**Purpose**: Orchestrate the entire bookkeeping process using LangGraph

**Key Classes**:

- `BookkeeperWorkflow`: Main LangGraph workflow definition
- `EmailProcessorNode`: Email processing node
- `FileIntakeNode`: File intake processing node
- `ClassificationNode`: Expense classification node
- `ValidationNode`: Data validation node
- `StorageNode`: Data storage node
- `ReportingNode`: Report generation node

**Key Methods**:

- `process_emails()`: Main workflow entry point for email processing
- `process_intake_files()`: Main workflow entry point for file intake
- `validate_and_store()`: Validation and storage pipeline
- `generate_reports()`: Reporting workflow
- `handle_errors()`: Error handling and recovery

#### Configuration Manager (`config/`)

**Purpose**: Manage application configuration and settings

**Key Classes**:

- `ConfigManager`: Central configuration management
- `EmailConfig`: Email provider settings
- `DatabaseConfig`: MongoDB connection settings
- `AIConfig`: AI model configurations
- `ReportConfig`: Report generation settings

**Key Methods**:

- `load_config()`: Load configuration from files
- `validate_config()`: Ensure configuration validity
- `update_config()`: Modify configuration settings
- `get_secret()`: Retrieve sensitive credentials

## Data Models

### Intake Record Schema

```python
{
    "_id": ObjectId,
    "intake_id": str,
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
    "invoice_id": str,
    "intake_id": str,  # Reference to intake record
    "invoice_number": str,
    "vendor": str,
    "issue_date": datetime,
    "due_date": datetime,
    "amount": Decimal,
    "currency": str,
    "tax_amount": Decimal,
    "description": str,
    "line_items": [
        {
            "description": str,
            "quantity": int,
            "unit_price": Decimal,
            "total": Decimal
        }
    ],
    "payment_terms": str,
    "status": str,  # "pending", "paid", "overdue", "cancelled"
    "receipt_id": str,  # Reference to associated receipt (if exists)
    "created_at": datetime,
    "updated_at": datetime
}
```

### Receipt Collection Schema

```python
{
    "_id": ObjectId,
    "receipt_id": str,
    "intake_id": str,  # Reference to intake record
    "receipt_number": str,
    "vendor": str,
    "transaction_date": datetime,
    "amount": Decimal,
    "currency": str,
    "tax_amount": Decimal,
    "payment_method": str,
    "description": str,
    "line_items": [
        {
            "description": str,
            "quantity": int,
            "unit_price": Decimal,
            "total": Decimal
        }
    ],
    "invoice_id": str,  # Reference to associated invoice (if exists)
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
