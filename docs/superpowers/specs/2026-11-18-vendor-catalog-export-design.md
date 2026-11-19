# PANDA vendor catalog export

## Intent and approaches

Create a standalone `export_vendor_catalog.py` that fetches PANDA vendors and
generates CSV and XML mapping-table outputs from the same response.

- Standalone script: recommended and selected by the user. Handles the vendors
  response directly and leaves existing exporters and converters unchanged.
- Vendors mode in the profiles exporter: shares an interface but complicates its
  paginated response and output handling; not selected.

## Interface

`python3 export_vendor_catalog.py --token TOKEN [--url URL] [--output-dir DIR]`

- Default URL: `https://panda.att.com.mx/apiQA/v1/catalogs/vendors`.
- Required `--token` is a manually obtained raw bearer token, without `Bearer `.
- Default output directory is the current directory; create a requested directory
  when needed, consistent with the profiles exporter.
- Use Python 3.9+ standard library only. No token acquisition or new dependencies.
- Make a single GET request, without adding page/size parameters or following a
  pagination loop. Send Authorization and Accept headers over HTTPS, use the
  existing 30-second timeout convention, and reject redirects.

## Outputs and mapping

Write these two files in the output directory:

- `vendors.csv`: headers `cve,name,businessName`, with one row per returned vendor.
  Use UTF-8 and standard CSV quoting for commas, quotes, and multiline strings.
  JSON null in businessName becomes an empty CSV cell; an empty string also
  remains an empty cell, so these two values cannot be distinguished in CSV.
- `MT-Catalogo-vendors.xml`: a complete UTF-8 XML 1.0 document with a mapping-table
  root and two col-def elements: id/nocase first and name/nocase second. Each row
  contains cve in its first col and name in its second col. Use tab indentation
  and XML escaping, preserving carriage returns through XML parsing.

The user explicitly requires preserving every string exactly as returned,
including leading/trailing whitespace, Unicode, punctuation, and leading zeroes.
Preserve response order and repeated records in both files. Do not trim, sort,
deduplicate, substitute businessName for name, or generate additional JSON output.
An empty response array produces a header-only CSV and XML definitions with no rows.

## Proposed validation and errors

- Require a JSON array of objects with the three specified fields. cve and name
  must be nonblank strings; businessName must be a string or null. Extra object
  fields are outside the supplied schema and are ignored, not added to the CSV.
- Validate the entire response and prepare the XML before opening report files.
  Reject invalid JSON, missing fields, wrong field types, invalid Unicode, and
  cve/name characters forbidden by XML 1.0. Do not remove or replace characters.
- Reject existing output files that alias each other (including hardlinks and
  symlinks), directories in place of report files, and invalid output paths.
- HTTP, network, or response-validation failures leave existing reports untouched.
  Valid runs overwrite both reports. Filesystem write errors can leave partial
  outputs; the two writes are not an atomic transaction.
- Print an immediately flushed request-start message, received/validated vendor
  count, each written path/row count, and final success only after both writes.
  Show errors clearly without printing the bearer token, headers, or response body.
- Exit 0 on success, 1 on request/validation/write failure, and 2 on invalid CLI
  arguments. Expected errors should not produce tracebacks.

## Non-goals and implementation choices

Do not change the profile exporter, catalog XML converter, IdM converters, or
Salesforce references. No API authentication flow, pagination, retries, extra
output-format switches, or live IdM import is required. Function organization and
exact error wording remain implementation choices. No live token has been
provided; test API handling with simulated responses.

## Verification

Test the supplied sample shape, one GET with no added pagination parameters,
bearer header, exact CSV columns and values, null-to-empty behavior, preserved
whitespace/Unicode/quoted and multiline strings, cve-to-id XML mapping, XML
escaping and carriage-return round trips, duplicate order, empty results,
progress and completion, output-directory creation, alias/path errors, HTTP and
network failures, invalid responses, preservation of existing reports on fetch or
validation failure, token-safe errors, and partial-write failure reporting.
Run the full existing test suite and CLI help; perform an independent final review.
