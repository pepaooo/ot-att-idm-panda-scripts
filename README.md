# Profile catalog CSV exporter

Requires Python 3. No packages need to be installed.

Obtain a valid token manually, then run:

```bash
python3 export_profile_catalogs.py --token 'YOUR_VALID_TOKEN' --output-dir reports
```

Supply the token itself, without `Bearer `. The script adds the Authorization
header; it does not obtain, refresh, save, or print tokens. Command-line arguments
can be visible in shell history and process listings. For interactive Bash use,
you can avoid putting the literal token in shell history:

```bash
read -rsp 'Bearer token: ' profile_token
echo
python3 export_profile_catalogs.py --token "$profile_token" --output-dir reports
unset profile_token
```

The default endpoint is
`https://app.acme.com.mx/apiQA/v1/catalogs/profiles`. To override it or the requested
page size:

```bash
python3 export_profile_catalogs.py --token 'YOUR_VALID_TOKEN' \
  --url 'https://app.acme.com.mx/apiQA/v1/catalogs/profiles' \
  --page-size 100 --output-dir reports
```

The script starts at page zero and follows `number`, `totalPages`, and `last`
metadata through all pages. Each request has a 30-second timeout. HTTPS is required;
redirects are rejected. If the service redirects, pass its final HTTPS endpoint
explicitly. An expired token stops the export; supply a fresh token and rerun.

The output directory contains:

- `templates.csv`
- `areas.csv`
- `levels.csv`

Each file has exactly the columns `name,key`. Unique `(name, key)` pairs are
collected independently across all profiles and sorted by name, then key. Different
names sharing a key and different keys sharing a name are retained. String keys
such as `023` are preserved; spreadsheet software may require importing the key
column as text. Files use UTF-8 and standard CSV quoting for commas, quotes, and
newlines. Empty catalogs produce headers only. The default output directory is
the current directory.

Existing reports are overwritten after all pages have been fetched and validated.
API, network, or data-validation errors leave existing reports untouched. A disk
or permissions failure during writing can leave partially written reports; the
three files are not replaced as a single transaction. Results also depend on the
API remaining consistent while pages are fetched.

Progress is shown automatically while running: each requested page (starting at
zero), each successfully validated page, its profile count, and the running total.
These messages go to standard error and are flushed immediately, so they remain
visible while the next request is in progress. A request can wait up to 30 seconds
before reporting a timeout. Tokens, headers, and response bodies are not printed.

The script prints each output path and its unique pair count, followed by
`Export completed successfully.` only after all three files are written. Exit status is 0
for success, 1 for request/data/write failures, and 2 for invalid arguments.

Run local tests (simulated API responses, no token or network required):

```bash
python3 -m unittest discover -s tests -v
```
