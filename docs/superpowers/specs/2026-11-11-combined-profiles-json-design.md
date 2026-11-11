# Combined PANDA profiles JSON

## Intent

Extend `export_profile_catalogs.py` to save the full set of PANDA profiles for a
future script while continuing to generate the existing three catalog CSVs.

## Approaches

- Merge profile records into one `content` array: recommended and selected by the
  user. Downstream scripts can consume all profiles without navigating pages.
- Store complete responses in a `pages` array: preserves pagination envelopes but
  makes downstream record processing more complicated; not selected.

## Required behavior

- Fetch sequential API pages starting at zero through the last page, retaining
  existing pagination validation, request timeout, token handling, and progress.
- Combine every page's `content` array into `{"content": [...]}`. Preserve every
  record, including extra fields, nested values, duplicates, and retrieval order.
  Do not retain page-level metadata in this combined document.
- After all pages have been fetched and validated, save `profiles.json` in the
  same `--output-dir` as the CSVs (current directory by default).
- Generate `templates.csv`, `areas.csv`, and `levels.csv` from the combined
  document's content. Retain exact `(name, key)` uniqueness independently per
  category, sorted output, UTF-8, and the `name,key` headers.
- Empty results produce `{"content": []}` and header-only CSVs.
- API, pagination, or catalog validation failures must not replace existing JSON
  or CSV reports. On success, existing reports are overwritten.

## Implementation proposals

- Use the same in-memory combined document to save JSON and derive CSV values;
  avoid rereading a file that has just been written.
- Write JSON as readable UTF-8 with indentation and Unicode characters preserved.
- Print the JSON output path and record count, alongside existing CSV counts;
  print completion only after all four outputs have been written.

## Constraints and non-goals

Keep Python standard library only and the existing command-line interface.
Do not change the Salesforce conversion script or create the future consumer.
The combined JSON is a valid single document, not raw adjacent JSON responses.
No streaming, resume, or offline CSV mode is required. As with existing CSVs,
outputs are not a single filesystem transaction: disk-write failures may leave
partial outputs. Concurrent API changes remain subject to existing checks and
the service's consistency guarantees.

## Verification

Exercise multiple pages with duplicate records and additional nested fields;
verify the combined JSON retains their exact contents and order while CSVs still
deduplicate category pairs. Check empty results, JSON Unicode round trips, final
completion messaging, and preservation of all existing output files when a later
API page fails. Run the full existing test suite with these additions.
