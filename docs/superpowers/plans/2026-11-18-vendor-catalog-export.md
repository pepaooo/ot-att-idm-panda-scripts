# Vendor Catalog Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Fetch the PANDA vendors catalog once and export its records to CSV and an XML mapping table without changing string values.

**Architecture:** A standalone CLI fetches one JSON array, validates the complete
response and prepares both documents, checks output paths, then writes the two
reports. Keep HTTP handling, response validation, XML serialization, and report
writing separate. Simulate HTTP responses in tests; no live credentials required.

**Tech Stack:** Python 3.9+ standard library: argparse, urllib, json, csv, pathlib, xml.etree.ElementTree, unittest.

**Spec:** `docs/superpowers/specs/2026-11-18-vendor-catalog-export-design.md`

## Global Constraints

- Create `export_vendor_catalog.py`; leave existing scripts unchanged.
- Required `--token TOKEN`; optional `--url URL` and `--output-dir DIR` (default current directory).
- Default URL: `https://panda.att.com.mx/apiQA/v1/catalogs/vendors`.
- Make one HTTPS GET, no added pagination parameters or pagination loop; Authorization Bearer and Accept JSON headers, 30-second timeout, redirects rejected.
- Write `vendors.csv` with cve,name,businessName headers; null businessName becomes an empty cell.
- Write `MT-Catalogo-vendors.xml` with mapping-table root, id/nocase and name/nocase definitions, and cve/name row values.
- Preserve every string, order, duplicates, Unicode, leading zeroes, and boundary whitespace; no trimming or deduplication.
- Require array/object/field types from the approved design; ignore additional object fields.
- Validate and serialize the complete response before opening outputs; create the output directory when necessary.
- Reject output aliases and invalid file targets. API/data errors preserve existing reports; filesystem write failures may leave partial output.
- Progress must flush immediately, never expose token/headers/body, and report final success only after both writes.
- Exit 0 success, 1 request/validation/write failure, 2 invalid arguments; expected failures have no traceback.

## Review Focus

- A leading-space vendor name must survive both CSV and XML without normalization.
- Null and empty businessName values must both become empty CSV cells without changing the other columns.
- HTTP/transport failures must not expose credentials through exception strings or response bodies.
- A late malformed vendor must preserve both existing reports rather than write a partial export.
- XML-special text, multiline values, and carriage returns must round-trip without data loss.

### Task 1: Implement and verify the standalone vendors exporter

**Files:** Create `export_vendor_catalog.py`, `tests/test_export_vendor_catalog.py`; update `README.md` with usage and output details.

**Interfaces:**
- `fetch_vendors(url: str, token: str) -> list`: perform one request and validate the complete response, returning original records without mutation.
- `build_mapping_table(vendors: list) -> bytes`: serialize the two-column UTF-8 XML with declaration, tab indentation, and preserved carriage returns.
- `write_reports(vendors: list, output_dir: Path) -> None`: prepare CSV/XML, check both output targets, write reports and print counts/paths.
- `main(argv=None) -> int`: parse/validate CLI, fetch, write, print completion, and sanitize expected errors.
- `ExportError`: expected HTTP/data/path failure.

- [x] Add tests for one GET with the exact supplied URL/query, bearer/Accept
  headers and timeout; sample records with null/empty businessName; default/custom
  URL and output directory; exact CSV header/values; XML definitions and cve/name
  positions; whitespace, Unicode, commas/quotes/newlines/carriage returns;
  duplicates/order and empty response. Check progress appears before the request
  and success appears only after both reports are written.
- [x] Add failure tests for HTTP errors including redirects, network/timeout/body
  transport failures, invalid JSON/UTF-8/schema/fields/XML characters, missing or
  invalid arguments, unsafe URLs, report aliases and invalid paths. Assert late
  bad records and fetch failures preserve both sentinel outputs and errors never
  include token or response body. Inject a write failure and check nonzero exit
  without final success or traceback.
- [x] Run `python3 -B -m unittest discover -s tests -v`; confirm the new module is
  absent and new tests fail while existing tests continue to pass.
- [x] Implement single-request HTTP handling and strict response validation,
  including UTF-8 encodability of strings and XML 1.0 validity of cve/name.
  Catch HTTP/network/body-read failures with sanitized errors; do not log raw
  URLs, headers, bodies, or exception messages containing credentials.
- [x] Implement CSV/XML document preparation, alias/path checks and report writing;
  retain the existing exporter conventions for CLI validation and flushed progress.
  Use XML character references for carriage returns so parsing preserves text.
- [x] Run the full suite; expect all passing. Document invocation, defaults,
  string preservation, null conversion, empty results, overwrite behavior, errors,
  progress, output paths, and partial-write limitation in README.
- [x] Run `python3 -B export_vendor_catalog.py --help`, full tests, and scoped
  `git diff --check`; expect success. Obtain an independent read-only final review
  under executing-plans and fix material findings with regression tests.

## Execution context

Continue direct implementation in the current approved workspace without commits
or branch changes. Preserve unrelated tracked/untracked work and user reports.
No token has been supplied, so do not attempt a live API call.
