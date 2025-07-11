# Bookkeeper Agent Test: Claude Sonnet 4 Invoice Processing Experiment

This was a test of using Claude Sonnet 4 to generate a bookkeeper agent to process invoices. The code that Claude Sonnet generates is verbose and requires constant review to ensure it reflects the original intent. This shifts the task from code writing to specification writing, prompt writing, and code review. Writing system prompts to fix common errors improves quality within limits.

For the product management aspect, Claude Sonnet is trained on the past. If someone relies on Claude Sonnet too much, they will skate where the problems were in the past, rather than where they are in the present. This can be seen in what Claude Sonnet thinks will be the highest priority items vs what the results show.

OpenAI handled the invoice and receipt text over 80% of the time in my small test, producing results that revealed edge cases specific to each phase of extraction: source to text, text to structured data, and invoice/receipt issues.

For this use case of translating invoices/receipts to a database, the LLM shifts the work from manual entry to verification that the system worked as expected and handling edge cases. This enables a measurable number of tasks to be shifted from manual to automated and increases the reliance on people with deep domain expertise to handle edge cases. Over time, edge case detection improves as more data is collected and automation can be improved by training on manual interventions.
