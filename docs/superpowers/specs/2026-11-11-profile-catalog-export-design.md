# Profile catalog CSV export

## Intent and scope

Provide a standalone Python script that retrieves every profile from the supplied
paginated API and exports the distinct catalog values for templates, areas, and
levels. The user obtains a bearer token manually and supplies it to the script.

## Approaches

- Python standard library: portable JSON, HTTP, and CSV handling with no installed
  dependencies. Selected by the user following this recommendation.
- Bash with curl and jq: workable, but requires jq and more shell error handling.

## Interface and behavior

- Script: `export_profile_catalogs.py`, using Python 3 standard library only.
- Required argument: `--token TOKEN`, containing the raw bearer token.
- Default endpoint: `https://app.acme.com.mx/apiQA/v1/catalogs/profiles`.
- Optional `--url`, `--page-size` (default 100), and `--output-dir` (default current
  directory) arguments. These are implementation proposals for reuse and testing.
- Send `Authorization: Bearer TOKEN`; do not obtain, refresh, store, or log tokens.
- Fetch sequential pages starting at zero, using the response pagination metadata
  to stop at the last page. Validate pagination to avoid silently incomplete data.
- Independently deduplicate each category by the exact `(name, key)` pair across
  all pages. Preserve different names sharing a key and different keys sharing a
  name; preserve key strings, including leading zeroes.
- Write `templates.csv`, `areas.csv`, and `levels.csv`, each with columns `name,key`.
  Proposed defaults: UTF-8, standard CSV quoting, sorted by name then key, existing
  files replaced on successful retrieval. Empty catalogs produce headers only.
- Fetch and validate all responses before writing reports. Reject malformed items,
  missing/null fields, invalid JSON, and HTTP/network failures with a clear error
  and nonzero exit status; never silently skip records.
- Use a finite request timeout and print the exported unique counts and paths.

## Non-goals and failure conditions

No token acquisition, scheduling, combined-profile CSV, or deduplication solely by
key. A report missing later pages or containing duplicate pairs is a failure.
Consistency during concurrent API changes depends on the service; this script
does not provide a transactional snapshot.

## Verification and remaining implementation choices

Use mocked HTTP responses to check multi-page retrieval, duplicate pairs, distinct
pairs sharing a name or key, CSV escaping/Unicode, empty results, and failures
before output. Document command-line usage. No live token is available, so a live
API run is outside local verification. Function structure and exact error wording
are left to implementation.
