# Extractor Edge Cases Documentation

## Overview

This document outlines potential edge cases that may be encountered when extracting invoice and receipt data from various document formats. These edge cases should be considered during implementation and testing of the DocumentExtractor, InvoiceExtractor, ReceiptExtractor, and DocumentClassifier components.

## Document Classification Edge Cases

### Ambiguous Document Types

| Edge Case                   | Description                                   | Example                               | Handling Strategy                          |
| --------------------------- | --------------------------------------------- | ------------------------------------- | ------------------------------------------ |
| Proforma Invoice            | Document looks like invoice but is not final  | "Proforma Invoice" header             | Classify as `invoice` but flag as draft    |
| Credit Note                 | Negative invoice amounts                      | "Credit Note" or negative totals      | Classify as `invoice` with negative amount |
| Estimate/Quote              | Future invoice, not yet billed                | "Estimate" or "Quote" header          | Classify as `other`                        |
| Receipt for Invoice Payment | Receipt that references invoice number        | Receipt with "Invoice #12345 Payment" | Classify as `receipt`, link to invoice     |
| Combined Document           | Single document with both invoice and receipt | Multi-page PDF with both              | Split into separate records                |

### Document Quality Issues

| Edge Case                | Description                              | Impact                       | Mitigation                        |
| ------------------------ | ---------------------------------------- | ---------------------------- | --------------------------------- |
| Poor Scan Quality        | Blurry, low resolution images            | OCR failures                 | Retry with enhanced preprocessing |
| Rotated Documents        | Document scanned upside down or sideways | Text extraction fails        | Auto-rotate detection             |
| Multi-language Documents | Text in multiple languages               | Incorrect field extraction   | Language detection and processing |
| Handwritten Documents    | Handwritten receipts or invoices         | OCR cannot read text         | Flag for manual review            |
| Partially Obscured       | Coffee stains, torn pages                | Missing critical information | Flag incomplete extractions       |

## Invoice Extraction Edge Cases

### Invoice Number Variations

| Pattern           | Example                                             | Extraction Challenge                |
| ----------------- | --------------------------------------------------- | ----------------------------------- |
| Multiple Formats  | "INV-2024-001", "Invoice #12345", "Bill No: ABC123" | Different regex patterns needed     |
| No Invoice Number | Small business handwritten invoice                  | Generate placeholder or flag        |
| Duplicate Numbers | Same invoice number from different vendors          | Requires vendor + number uniqueness |
| Alpha-numeric Mix | "2024-Q1-INV-001A"                                  | Complex parsing required            |

### Vendor Information Edge Cases

- **Multiple Business Names**: Company has trade name and legal name
- **Address Variations**: P.O. Box vs. street address, international formats
- **Missing Vendor Info**: Handwritten receipts without clear business details
- **Vendor Name Changes**: Same business, different name over time
- **Subsidiary Companies**: Parent company vs. subsidiary billing

### Date Field Complications

| Issue                 | Example                                       | Solution Approach                |
| --------------------- | --------------------------------------------- | -------------------------------- |
| Multiple Date Formats | "01/02/2024" vs "Feb 1, 2024" vs "2024-02-01" | Universal date parser            |
| Ambiguous Dates       | "01/02/24" (Jan 2 or Feb 1?)                  | Use regional settings or context |
| Missing Due Date      | Only issue date provided                      | Calculate based on payment terms |
| Future Dates          | Invoice dated in future                       | Flag for validation              |
| Invalid Dates         | "32/13/2024"                                  | Error handling and manual review |

### Amount and Currency Edge Cases

| Scenario                   | Example                                                  | Storage Challenge             |
| -------------------------- | -------------------------------------------------------- | ----------------------------- |
| Multiple Currencies        | Invoice in EUR, payment in USD                           | Currency conversion tracking  |
| Missing Decimal            | "1234" vs "12.34" vs "1,234.00"                          | Amount interpretation         |
| Tax-Inclusive vs Exclusive | "Total: $100 (incl. tax)" vs "Subtotal: $100 + Tax: $10" | Different calculation methods |
| Negative Amounts           | Credit notes, refunds                                    | Proper sign handling          |
| Zero Amounts               | Free services, promotional items                         | Validation of zero values     |
| Rounding Discrepancies     | Line items don't sum to total                            | Handle small differences      |

### Line Items Complexity

- **Variable Line Item Count**: 1 item vs. 50+ items
- **Missing Descriptions**: Only product codes or part numbers
- **Bundled Items**: Package deals with multiple components
- **Discount Applications**: Line-level vs. total discounts
- **Tax Variations**: Different tax rates per item
- **Unit Measurement Variations**: "each", "dozen", "kg", "hours"

## Receipt Extraction Edge Cases

### Payment Method Variations

| Payment Type     | Variations                                         | Extraction Notes       |
| ---------------- | -------------------------------------------------- | ---------------------- |
| Credit Card      | "Visa ending 1234", "\*\*\*\*1234", "Card Payment" | Mask sensitive data    |
| Cash             | "Cash", "Cash Payment", blank field                | Default assumption     |
| Digital Payments | "PayPal", "Venmo", "Apple Pay", "Google Pay"       | Multiple service names |
| Check            | "Check #1234", "CHK", "Cheque"                     | Include check number   |
| Store Credit     | "Gift Card", "Store Credit", "Account Credit"      | Special handling       |
| Split Payments   | Multiple payment methods on one receipt            | Complex parsing        |

### Receipt Format Variations

- **Thermal Receipts**: Faded text, narrow format
- **Email Receipts**: HTML format, different layouts
- **Mobile App Receipts**: Screenshots with varying layouts
- **Handwritten Receipts**: Manual cash transactions
- **International Receipts**: Different cultural formats and languages

### Transaction Context Issues

| Issue             | Description                                 | Impact                                 |
| ----------------- | ------------------------------------------- | -------------------------------------- |
| Refund Receipts   | Negative amounts, return transactions       | Proper transaction type classification |
| Partial Payments  | Receipt for partial invoice payment         | Link to correct invoice                |
| Tip Amounts       | Restaurant receipts with tips               | Separate tip from base amount          |
| Tax Exemptions    | Non-profit or business tax-exempt purchases | Handle zero tax amounts                |
| Loyalty Discounts | Points redemption, member discounts         | Track discount sources                 |

## Cross-Document Relationship Edge Cases

### Invoice-Receipt Matching

| Challenge             | Description                                      | Resolution Strategy                  |
| --------------------- | ------------------------------------------------ | ------------------------------------ |
| Partial Payments      | Multiple receipts for one invoice                | Track payment history                |
| Overpayments          | Receipt amount exceeds invoice                   | Handle credit balances               |
| Payment Date Mismatch | Receipt dated before invoice                     | Validate business logic              |
| Different Amounts     | Receipt total doesn't match invoice (tips, fees) | Allow reasonable variance            |
| Missing References    | Receipt doesn't mention invoice number           | Fuzzy matching by vendor/amount/date |

### Duplicate Detection Edge Cases

- **Same Document, Different Sources**: Email attachment vs. manual upload
- **Amended Documents**: Corrected invoice with same number
- **Copy vs. Original**: "Copy" stamped on duplicate
- **Different File Formats**: Same document as PDF and image
- **Multi-page Documents**: Pages processed separately

## Technical Processing Edge Cases

### File Format Issues

| Format            | Potential Issues                               | Handling                             |
| ----------------- | ---------------------------------------------- | ------------------------------------ |
| PDF               | Password protected, corrupted, scanned images  | PDF parsing libraries, OCR fallback  |
| Images            | Multiple formats (JPG, PNG, HEIC), large files | Format conversion, compression       |
| Email Body        | HTML parsing, embedded images                  | Text extraction, attachment handling |
| Scanned Documents | Poor quality, skewed orientation               | Image preprocessing                  |

### Document Format Specific Extraction Issues

| Format       | AI Extraction Challenges                                    | Impact on Data Quality              |
| ------------ | ----------------------------------------------------------- | ----------------------------------- |
| Email HTML   | Complex HTML structure, embedded CSS, inline styling       | AI may miss structured data         |
| PDF Text     | Multi-column layouts, embedded tables, form fields         | AI may lose table structure         |
| Plain Text   | Minimal formatting, inconsistent spacing                   | AI must infer document structure    |
| Email Plain  | Quote levels (>), signature blocks, thread history         | AI may extract irrelevant content   |
| HTML Files   | Web page formatting, navigation elements, ads              | AI may extract non-invoice content  |

### OCR and Text Extraction Failures

- **Character Recognition Errors**: "8" vs "B", "0" vs "O"
- **Table Structure Loss**: Columns merge, rows misaligned
- **Special Characters**: Currency symbols, accented characters
- **Font Variations**: Decorative fonts, very small text
- **Background Interference**: Watermarks, colored backgrounds

### AI Extraction Failures

- **OpenAI API Timeout**: Request exceeds time limit
- **OpenAI Rate Limiting**: API quota exceeded
- **Invalid JSON Response**: AI returns malformed JSON
- **Incomplete Field Extraction**: AI misses required fields
- **Incorrect Field Classification**: AI assigns wrong field types
- **Currency Symbol Misinterpretation**: AI fails to parse currency formats
- **Date Format Confusion**: AI extracts invalid or incorrect dates
- **Amount Parsing Errors**: AI returns non-numeric amount values
- **Vendor Name Extraction Issues**: AI fails to identify business names
- **Line Item Structure Problems**: AI doesn't properly structure item lists

### Data Validation Edge Cases

| Validation Type     | Edge Cases                                    | Business Rules            |
| ------------------- | --------------------------------------------- | ------------------------- |
| Amount Validation   | Unreasonably large/small amounts              | Define acceptable ranges  |
| Date Validation     | Future dates, very old dates                  | Business date ranges      |
| Vendor Validation   | New vendor vs. existing with slight variation | Fuzzy matching thresholds |
| Currency Validation | Unsupported currencies                        | Default handling          |
| Tax Calculation     | Different tax jurisdictions                   | Location-based rules      |

## Business Logic Edge Cases

### Multi-jurisdictional Issues

- **Different Tax Systems**: VAT vs. Sales Tax vs. GST
- **Currency Regulations**: Cross-border payment restrictions
- **Date Format Standards**: US vs. European vs. ISO formats
- **Business Practice Variations**: Net terms, payment customs

### Industry-Specific Variations

| Industry              | Unique Characteristics                     | Special Handling                  |
| --------------------- | ------------------------------------------ | --------------------------------- |
| Construction          | Progress billing, retention amounts        | Partial completion tracking       |
| Professional Services | Time-based billing, expense reimbursements | Hour tracking, expense categories |
| Retail                | High volume, small amounts, returns        | Batch processing, return policies |
| Manufacturing         | Raw materials, work orders                 | Inventory tracking, job costing   |
| Healthcare            | Insurance claims, patient billing          | Privacy compliance, claim numbers |

## Error Recovery Strategies

### Graceful Degradation

1. **Full Extraction Failure**: Save document for manual review
2. **Partial Extraction**: Save available fields, flag missing data
3. **Classification Uncertainty**: Use confidence scores, human verification
4. **Amount Parsing Issues**: Store original text, attempt multiple parsing methods
5. **Date Ambiguity**: Use multiple date formats, flag for verification

### Manual Review Triggers

- Confidence score below threshold
- Missing required fields
- Amount discrepancies
- Duplicate document detected
- Vendor not in approved list
- Unusual transaction patterns

## Testing Scenarios

### Comprehensive Test Cases

1. **Happy Path**: Clean, well-formatted documents
2. **Format Variations**: Different layouts, fonts, orientations
3. **Quality Issues**: Poor scans, faded text, damaged documents
4. **Edge Amounts**: Very large, very small, zero, negative amounts
5. **Date Variations**: All supported formats, edge dates
6. **Multi-language**: Different languages and character sets
7. **Complex Layouts**: Multi-page, multi-column, embedded tables
8. **Business Variations**: Different industries, countries, currencies

### Performance Edge Cases

- **Large Documents**: Multi-page invoices, high-resolution images
- **Batch Processing**: Multiple documents simultaneously
- **Concurrent Access**: Multiple users uploading simultaneously
- **Memory Constraints**: Large file processing limits
- **Timeout Scenarios**: Complex documents requiring extended processing

## Monitoring and Alerting

### Key Metrics to Track

- Extraction success rate by document type
- Processing time distribution
- Manual review rate
- Classification accuracy
- Amount parsing accuracy
- Duplicate detection effectiveness

### Alert Conditions

- Extraction failure rate above threshold
- Processing time exceeding limits
- High manual review volume
- Unusual transaction patterns
- System resource constraints

---

## Edge Case Implementation TODO List

### Implementation Status Summary

**✅ Items marked as checked** have basic implementation through AI-powered extraction using OpenAI's GPT models. The current implementation provides:

- AI-powered document classification (invoice/receipt/other)
- AI-powered structured data extraction with JSON output
- Basic file format support (PDF, images, HTML, text)
- OCR capabilities for images
- Error handling for corrupted/invalid files
- Currency amount conversion to cents
- Basic date parsing with fallbacks
- MongoDB integration for data storage

**⏳ Items still unchecked** require specific algorithmic implementations, advanced preprocessing, or specialized business logic beyond the current AI extraction capabilities.

### Priority Classification

- **P1 (High)**: Very common edge cases, will impact most users
- **P2 (Medium)**: Moderately common, important for robustness
- **P3 (Low)**: Rare cases, nice-to-have improvements

---

## P1 - High Priority (Very Common Edge Cases)

### Document Quality Issues

- [ ] **Poor scan quality handling** - Enhance preprocessing for blurry images
- [ ] **Rotated document detection** - Auto-rotate documents before OCR
- [x] **Multi-page document processing** - Handle PDF/image sequences *(Basic PDF multi-page support implemented)*
- [ ] **Partially obscured documents** - Handle coffee stains, torn pages

### Amount Parsing Variations

- [ ] **Multiple currency formats** - "$1,234.56", "1.234,56 €", "¥1234"
- [x] **Missing decimal interpretation** - Determine if "1234" is $12.34 or $1234.00 *(AI extracts decimal amounts, convert_to_cents handles conversion)*
- [x] **Negative amounts** - Credit notes, refunds, returns *(Basic negative amount support in AI extraction)*
- [x] **Zero amount handling** - Free services, promotional items *(Handled by convert_to_cents function)*
- [ ] **Rounding discrepancies** - Line items don't sum to total

### Date Format Complications

- [ ] **Ambiguous date resolution** - "01/02/24" interpretation logic
- [x] **Multiple date formats** - MM/DD/YYYY vs DD/MM/YYYY vs YYYY-MM-DD *(Basic support via AI extraction)*
- [ ] **Text date parsing** - "January 15, 2024", "15-Jan-2024"
- [ ] **Invalid date handling** - "32/13/2024", impossible dates
- [ ] **Future date validation** - Invoices dated in future

### Invoice Number Variations

- [x] **Multiple format patterns** - "INV-001", "#12345", "Bill No: ABC" *(Handled by AI extraction)*
- [ ] **No invoice number handling** - Generate placeholders or flag
- [ ] **Duplicate number detection** - Same number from different vendors
- [ ] **Alphanumeric combinations** - "2024-Q1-INV-001A" parsing

### AI Extraction Data Validation

- [ ] **Missing document number extraction** - AI fails to find invoice/receipt number
- [ ] **Missing date extraction** - AI cannot identify transaction dates
- [ ] **Missing amount extraction** - AI fails to extract total amounts
- [ ] **Missing vendor extraction** - AI cannot identify business/vendor name
- [ ] **Corrupted JSON response** - AI returns malformed or invalid JSON
- [ ] **Incorrect currency extraction** - AI assigns wrong currency code
- [ ] **Invalid date format extraction** - AI extracts unparseable date strings
- [ ] **Non-numeric amount extraction** - AI returns text instead of numbers
- [ ] **Empty line items array** - AI fails to extract any line items
- [ ] **Incomplete company information** - AI partially extracts vendor details

---

## P2 - Medium Priority (Moderately Common)

### Document Classification Edge Cases

- [ ] **Proforma invoice detection** - Flag as draft invoices
- [ ] **Credit note classification** - Handle negative invoice amounts
- [x] **Estimate/quote detection** - Classify as "other" type *(Handled by AI classification)*
- [ ] **Receipt for invoice payment** - Link receipts to invoices
- [ ] **Combined document splitting** - Single PDF with invoice + receipt

### Vendor Information Edge Cases

- [ ] **Multiple business names** - Trade name vs legal name
- [ ] **Address format variations** - P.O. Box vs street address
- [ ] **Missing vendor information** - Handle incomplete data
- [ ] **Vendor name changes** - Same business, different name over time
- [ ] **Subsidiary company handling** - Parent vs subsidiary billing

### Payment Method Variations

- [x] **Credit card parsing** - "Visa ending 1234", "\*\*\*\*1234" *(Basic support via AI extraction)*
- [x] **Digital payment detection** - PayPal, Venmo, Apple Pay, Google Pay *(Basic support via AI extraction)*
- [x] **Check number extraction** - "Check #1234", "CHK", "Cheque" *(Basic support via AI extraction)*
- [ ] **Split payment handling** - Multiple payment methods per receipt
- [x] **Cash vs card determination** - Default payment method logic *(Handled by AI extraction)*

### Line Item Complexity

- [x] **Variable line item count** - Handle 1 to 50+ items *(Handled by AI extraction)*
- [x] **Missing descriptions** - Product codes only *(Handled by AI extraction with optional fields)*
- [ ] **Bundled item parsing** - Package deals, grouped items
- [ ] **Discount application tracking** - Line-level vs total discounts
- [x] **Unit measurement variations** - "each", "dozen", "kg", "hours" *(Handled by AI extraction)*

### Cross-Document Relationships

- [ ] **Partial payment tracking** - Multiple receipts for one invoice
- [ ] **Overpayment handling** - Receipt amount exceeds invoice
- [ ] **Payment date mismatch** - Receipt dated before invoice
- [ ] **Fuzzy invoice-receipt matching** - Match by vendor/amount/date

### AI Extraction Quality Control

- [ ] **Incorrect currency extraction** - AI assigns wrong currency code
- [ ] **Invalid date format extraction** - AI extracts unparseable date strings
- [ ] **Non-numeric amount extraction** - AI returns text instead of numbers
- [ ] **Empty line items array** - AI fails to extract any line items
- [ ] **Incomplete company information** - AI partially extracts vendor details
- [ ] **OpenAI API timeout handling** - Request exceeds time limit
- [ ] **OpenAI rate limiting recovery** - API quota exceeded scenarios
- [ ] **Malformed JSON response handling** - AI returns invalid JSON structure

---

## P3 - Low Priority (Less Common Edge Cases)

### Advanced Quality Issues

- [ ] **Multi-language document support** - Non-English documents
- [ ] **Handwritten document flagging** - Manual review triggers
- [ ] **Watermark interference** - Background elements affecting OCR

### Complex Business Scenarios

- [ ] **Multiple currency transactions** - Invoice in EUR, payment in USD
- [ ] **Tax calculation variations** - Different tax rates per item
- [ ] **Industry-specific formats** - Construction, healthcare variations
- [ ] **Tip amount separation** - Restaurant receipts with tips
- [ ] **Tax exemption handling** - Non-profit or business tax-exempt

### Advanced Duplicate Detection

- [ ] **Same document, different sources** - Email vs manual upload
- [ ] **Amended document handling** - Corrected invoice with same number
- [ ] **Copy vs original detection** - "Copy" stamped duplicates
- [ ] **Multi-format duplicate detection** - PDF vs image of same document

### Technical Edge Cases

- [ ] **Large document optimization** - Multi-page, high-resolution handling
- [ ] **Password protected PDFs** - Handle secured documents
- [x] **Corrupted file handling** - Graceful failure for damaged files *(Comprehensive error handling implemented)*
- [ ] **Character recognition errors** - "8" vs "B", "0" vs "O"
- [ ] **Table structure preservation** - Maintain column/row alignment

### Document Format Extraction Issues

- [ ] **Email HTML structure parsing** - Complex HTML layouts with CSS/styling
- [ ] **PDF multi-column layout handling** - AI loses table structure in complex PDFs
- [ ] **Plain text structure inference** - AI must infer document layout from minimal formatting
- [ ] **Email thread extraction** - AI extracts irrelevant quoted/signature content
- [ ] **HTML web page filtering** - AI extracts navigation/ads instead of invoice content

---

## Implementation Priority Ranking

### Most Critical (Implement First)

1. **Poor scan quality handling** - Affects 60-80% of scanned documents ⏳
2. ✅ **Multiple currency formats** - Every document has amounts *(Basic AI extraction)*
3. ✅ **Date format variations** - Universal challenge across regions *(Basic AI parsing)*
4. ✅ **Invoice number variations** - Common across all businesses *(AI extraction)*
5. **Rotated document detection** - Very common scanning issue ⏳

### High Impact (Implement Second)

6. ✅ **Missing decimal interpretation** - Affects amount accuracy *(AI extracts decimals, convert_to_cents handles conversion)*
7. ✅ **Negative amounts** - Credit notes are common *(Basic AI support)*
8. **Vendor information variations** - Address/name inconsistencies ⏳
9. **Document classification edge cases** - Proforma, credit notes ⏳
10. ✅ **Payment method variations** - Receipt processing essential *(Basic AI extraction)*
11. **Missing document number extraction** - AI fails to find invoice/receipt number ⏳
12. **Missing amount extraction** - AI fails to extract total amounts ⏳
13. **Corrupted JSON response** - AI returns malformed or invalid JSON ⏳

### Moderate Impact (Implement Third)

14. ✅ **Line item complexity** - Multi-item invoices *(Basic AI extraction)*
15. **Cross-document relationships** - Invoice-receipt matching ⏳
16. ✅ **Zero amount handling** - Free services, promotions *(AI extraction)*
17. **Duplicate detection** - Prevent data duplication ⏳
18. **Split payment handling** - Complex payment scenarios ⏳
19. **Missing date extraction** - AI cannot identify transaction dates ⏳
20. **Missing vendor extraction** - AI cannot identify business/vendor name ⏳

### Lower Priority (Implement Later)

16. **Multi-language support** - Specific market needs
17. **Industry-specific variations** - Niche requirements
18. **Advanced duplicate detection** - Edge case scenarios
19. **Technical optimizations** - Performance improvements
20. **Character recognition errors** - Rare OCR issues

---

## Expected Frequency Analysis

### Daily Occurrence (>50% of documents)

- Poor scan quality
- Multiple currency formats
- Date format variations
- Invoice number variations

### Weekly Occurrence (10-50% of documents)

- Rotated documents
- Missing vendor information
- Payment method variations
- Negative amounts

### Monthly Occurrence (1-10% of documents)

- Document classification edge cases
- Line item complexity
- Cross-document relationships
- Zero amounts

### Rare Occurrence (<1% of documents)

- Multi-language documents
- Industry-specific variations
- Advanced duplicate scenarios
- Technical edge cases

---

## Testing Strategy for Edge Cases

### P1 Testing (Essential)

- Create test documents for each common edge case
- Performance testing with poor quality scans
- Cross-format testing (PDF, JPG, PNG)
- Amount parsing accuracy tests

### P2 Testing (Important)

- Business scenario simulation
- Multi-document workflow testing
- Vendor variation testing
- Payment method recognition tests

### P3 Testing (Nice-to-have)

- Multi-language document testing
- Stress testing with complex scenarios
- Edge case combination testing
- Performance optimization validation
