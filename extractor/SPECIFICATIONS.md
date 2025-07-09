# Extractor Module Specifications

## Overview

The Extractor module is responsible for processing documents from the entry queue, extracting financial information from invoices and receipts, and saving the extracted data to MongoDB collections. This module serves as the final processing stage in the Bookkeeper Agent workflow.

## Purpose

Extract invoice and receipt information from queued documents and store the structured data in MongoDB for further analysis and reporting.

## Data Format Conventions

### Currency Storage

- All currency values are stored as integers (e.g., $123.45 becomes 12345)
- This applies to amounts, tax amounts, unit prices, and totals

### Date Storage

- All dates are stored as datetime objects
- This includes transaction dates, issue dates, due dates, and timestamps

### Data Types

- Quantities: integers
- Descriptions: strings
- Payment methods: strings

## Architecture

### Key Classes

#### `DocumentExtractor`

**Purpose**: Main extraction orchestrator that coordinates the entire extraction process

**Responsibilities**:

- Retrieve documents from the entry queue
- Classify documents as invoices or receipts
- Delegate extraction to appropriate specialized extractors
- Handle errors and update processing status
- Coordinate saving to MongoDB collections

**Dependencies**:

- `EntryQueueManager` for queue operations
- `DocumentClassifier` for document type determination
- `InvoiceExtractor` and `ReceiptExtractor` for specialized extraction
- MongoDB connection for data persistence

#### `InvoiceExtractor`

**Purpose**: Extract invoice-specific information from documents

**Responsibilities**:

- Parse invoice documents (PDF, images, text)
- Extract structured invoice data (vendor, amount, date, line items, etc.)
- Validate extracted data integrity
- Format data according to invoice schema

**Key Extraction Fields**:

- Invoice number
- Vendor information
- Issue date and due date
- Total amount and currency
- Tax amount
- Line items with descriptions, quantities, and prices
- Payment terms

#### `ReceiptExtractor`

**Purpose**: Extract receipt-specific information from documents

**Responsibilities**:

- Parse receipt documents (PDF, images, text)
- Extract structured receipt data (vendor, amount, date, payment method, etc.)
- Validate extracted data integrity
- Format data according to receipt schema

**Key Extraction Fields**:

- Receipt number
- Vendor information
- Transaction date
- Total amount and currency
- Tax amount
- Payment method
- Line items with descriptions, quantities, and prices

#### `DocumentClassifier`

**Purpose**: Determine if a document is an invoice, receipt, or other type

**Responsibilities**:

- Analyze document content and structure
- Apply classification algorithms/rules
- Return document type classification with confidence score
- Handle edge cases and ambiguous documents

**Classification Types**:

- `invoice`: Business invoices requiring payment
- `receipt`: Proof of payment documents
- `other`: Non-financial documents

## Key Methods

### DocumentExtractor Methods

#### `process_queue_item(queue_entry: dict) -> dict`

**Purpose**: Process a single queued document and save extracted data to MongoDB

**Parameters**:

- `queue_entry`: Dictionary containing intake record information

**Returns**:

- Dictionary with processing results and extracted data reference

**Process Flow**:

1. Retrieve document from unique directory
2. Classify document type
3. Delegate to appropriate extractor
4. Save extracted data to MongoDB
5. Update intake record status
6. Handle errors and logging

#### `extract_invoice_data(document: bytes) -> dict`

**Purpose**: Extract invoice information from document bytes

**Parameters**:

- `document`: Raw document data as bytes

**Returns**:

- Dictionary containing structured invoice data

**Process**:

1. Use InvoiceExtractor to parse document
2. Validate required fields are present
3. Format data according to invoice schema
4. Return structured invoice data

#### `extract_receipt_data(document: bytes) -> dict`

**Purpose**: Extract receipt information from document bytes

**Parameters**:

- `document`: Raw document data as bytes

**Returns**:

- Dictionary containing structured receipt data

**Process**:

1. Use ReceiptExtractor to parse document
2. Validate required fields are present
3. Format data according to receipt schema
4. Return structured receipt data

#### `save_to_invoices_collection(invoice_data: dict) -> ObjectId`

**Purpose**: Save invoice data to invoices collection

**Parameters**:

- `invoice_data`: Structured invoice data dictionary

**Returns**:

- The ObjectId of the saved invoice record

**Process**:

1. Validate invoice data completeness
2. Set receipt_id to null (will be updated if associated receipt exists)
3. Add metadata (created_at, updated_at)
4. Insert into invoices collection
5. Return the id

#### `save_to_receipts_collection(receipt_data: dict) -> ObjectId`

**Purpose**: Save receipt data to receipts collection

**Parameters**:

- `receipt_data`: Structured receipt data dictionary

**Returns**:

- The ObjectId of the saved receipt record

**Process**:

1. Validate receipt data completeness
2. Add receipt_id field using MongoDB ObjectId
3. Add metadata (created_at, updated_at)
4. Insert into receipts collection
5. Return the id

## Data Processing Pipeline

### Input Processing

1. **Queue Retrieval**: Get next pending item from entry queue
2. **Document Loading**: Load document from unique directory path
3. **Classification**: Determine document type (invoice/receipt/other)
4. **Extraction**: Apply appropriate extractor based on classification

### Extraction Process

1. **OCR/Text Extraction**: Convert images/PDFs to text
2. **Pattern Recognition**: Identify key fields using regex/AI
3. **Data Validation**: Ensure extracted data meets schema requirements
4. **Data Formatting**: Structure data according to collection schemas

### Storage Process

1. **Data Preparation**: Add required metadata fields
2. **Database Insert**: Save to appropriate MongoDB collection
3. **Reference Updates**: Link intake record to extracted data
4. **Status Updates**: Mark intake record as completed

## Error Handling

### Document Processing Errors

- **File Access Errors**: Handle missing or corrupted files
- **Format Errors**: Manage unsupported document formats
- **Extraction Errors**: Handle OCR or parsing failures
- **Classification Errors**: Manage ambiguous document types

### Data Validation Errors

- **Required Field Missing**: Handle incomplete extractions
- **Data Type Errors**: Validate numeric and date fields
- **Schema Violations**: Ensure data matches collection schemas

### Database Errors

- **Connection Errors**: Handle MongoDB connectivity issues
- **Insert Errors**: Manage duplicate records or constraint violations
- **Transaction Errors**: Ensure data consistency

## Configuration

### Environment Variables

- `MONGODB_URI`: MongoDB connection string
- `EXTRACTOR_LOG_LEVEL`: Logging level for extractor operations
- `OCR_SERVICE_URL`: External OCR service endpoint (if used)
- `AI_MODEL_ENDPOINT`: AI model for extraction (if used)

### Processing Settings

- `MAX_RETRY_ATTEMPTS`: Number of retry attempts for failed extractions
- `BATCH_SIZE`: Number of documents to process in each batch
- `TIMEOUT_SECONDS`: Maximum time allowed for single document processing

## Dependencies

### Internal Dependencies

- `entry_queue.EntryQueueManager`: For queue operations
- `database.MongoDBClient`: For database operations

### External Dependencies

- `pymongo`: MongoDB client library
- `PIL` or `opencv`: Image processing
- `PyPDF2` or `pdfplumber`: PDF text extraction
- `pytesseract`: OCR capabilities (optional)
- `openai` or similar: AI-powered extraction (optional)

## Testing Requirements

### Unit Tests

- Test each extractor class independently
- Mock external dependencies (MongoDB, OCR services)
- Test error handling scenarios
- Validate data schema compliance

### Integration Tests

- Test full extraction pipeline
- Test with real document samples
- Verify MongoDB integration
- Test queue integration

### Performance Tests

- Measure extraction time per document
- Test with large document batches
- Monitor memory usage during processing
- Validate concurrent processing capabilities
