# Profile JSON and catalog CSV exporter

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

- `profiles.json`
- `templates.csv`
- `areas.csv`
- `levels.csv`

`profiles.json` is a single document shaped as `{"content": [...]}` containing
every profile from every page. All record fields, nested values, duplicates, and
retrieval order are preserved. Page-level pagination metadata is omitted. JSON is
indented UTF-8 with Unicode characters preserved; an empty result is
`{"content": []}`. This file can serve as input to a future processing script.

The three CSVs are generated from the same combined content in memory; the JSON
file is not reread during this run. Each CSV has exactly the columns `name,key`.
Unique `(name, key)` pairs are
collected independently across all profiles and sorted by name, then key. Different
names sharing a key and different keys sharing a name are retained. String keys
such as `023` are preserved; spreadsheet software may require importing the key
column as text. Files use UTF-8 and standard CSV quoting for commas, quotes, and
newlines. Empty catalogs produce headers only. The default output directory is
the current directory.

Existing JSON and CSV reports are overwritten after all pages have been fetched
and every catalog record validated. API, network, or data-validation errors leave
all existing reports untouched. A disk
or permissions failure during writing can leave partially written reports; the
four files are not replaced as a single transaction. Results also depend on the
API remaining consistent while pages are fetched.

Progress is shown automatically while running: each requested page (starting at
zero), each received page with valid pagination, its profile count, and the running total.
These messages go to standard error and are flushed immediately, so they remain
visible while the next request is in progress. A request can wait up to 30 seconds
before reporting a timeout. Tokens, headers, and response bodies are not printed.

The script prints the JSON path and full profile count, then each CSV path and
its unique pair count, followed by `Export completed successfully.` only after all
four files are written. Exit status is 0
for success, 1 for request/data/write failures, and 2 for invalid arguments.

Run local tests (simulated API responses, no token or network required):

```bash
python3 -m unittest discover -s tests -v
```

## Convert PANDA profiles into IdM CSVs

`panda_profiles_to_resource_csv.py` reads the combined `profiles.json` locally.
It does not call the API or need a token. Use the same four output flags as the
Salesforce converter, individually or together:

```bash
python3 panda_profiles_to_resource_csv.py reports/profiles.json \
  --generaRecursos reports/panda_resources.csv \
  --genereRoles reports/panda_roles.csv \
  --generaAsociaciones reports/panda_associations.csv \
  --generaMapeoRol10 reports/panda_role10_mapping.csv
```

Output directories must already exist. The resource, role, and association CSVs
have 13, 12, and 12 columns respectively, without headers. The mapping has three
columns with the header `"Name","Id","DN"`. All fields are quoted and files use
UTF-8. Each selected file's path and data-row count are printed after it is written.

Only combinations present in `content` are processed. For template key `6`, area
key `HORUS`, and level key `ULAVP`, the converter uses:

- Role and resource CN: `PANDA-6-HORUS-ULAVP`.
- Metadata `ID`: `6-HORUS-ULAVP`.
- Metadata `ID2`: the three names joined by hyphens, such as `Horus User-Horus Access-AVP`.
- Category for resources and roles: `panda-perfil`.
- Resource permission DN: `cn=Permission,cn=MID-PANDA,cn=DriverSet1,ou=idm,ou=services,o=system`.
- Association target: `cn=PANDA-Permission-DRS,cn=ResourceDefs,cn=RoleConfig,cn=AppConfig,cn=User Application Driver,cn=DriverSet1,ou=idm,ou=services,o=system`.

Roles use the existing `cn=Level10,cn=RoleDefs,...` base, and resources use the
existing `cn=ResourceDefs,...` base from the Salesforce reference. Associations
link each role to the shared `PANDA-Permission-DRS` resource with its combination's
metadata. They do not link to the individually generated resource DN.

Resource and association metadata fields retain the reference's legacy format:

```text
"{\"ID\":\"6-HORUS-ULAVP\",\"ID2\":\"Horus User-Horus Access-AVP\"}"
```

This field uses backslash escaping; other fields use standard CSV doubled quotes.
Generic CSV parsers configured for ordinary CSV quoting may not decode this mixed
format correctly. Quotes, backslashes, and newlines inside metadata names are
JSON-escaped before the outer escaping is applied. Original names remain in
metadata, descriptions, and mapping rows. Resource and role display names remove
the same punctuation as the Salesforce reference (`* + ~ = / \\ # " , ;`).

Exact duplicate key/name combinations are skipped in first-occurrence order.
Different names for the same key triple or different triples yielding the same
joined ID cause an error. Keys retain leading zeroes. CNs longer than 64 characters
or containing unsafe DN characters are rejected rather than truncated.

The entire input and every selected output path are checked before files are
opened for writing. Missing or empty fields, malformed input, conflicting data,
and output paths aliasing the input or another output cause an error without
replacing existing outputs. Empty `content` produces empty resource/role/association
files and a header-only mapping. Valid runs overwrite selected outputs; disk-write
failures may leave partial files because writes are not a multi-file transaction.

Exit status is 0 for success, 1 for input/path/write errors, 2 for invalid CLI
arguments, and 3 if no output flag is supplied. The test command above checks both
the API exporter and this converter.

## Convert PANDA catalogs into XML mapping tables

`panda_catalogs_to_xml.py` requires Python 3.9 or newer and no additional packages.
It accepts any subset of the three catalog CSVs. To convert all three:

```bash
python3 panda_catalogs_to_xml.py \
  --templates reports/templates.csv \
  --areas reports/areas.csv \
  --levels reports/levels.csv
```

This creates the following files in the **current directory**:

- `MT-Catalogo-templates.xml`
- `MT-Catalogo-area.xml`
- `MT-Catalogo-level.xml`

To convert only templates and choose an output path:

```bash
python3 panda_catalogs_to_xml.py \
  --templates reports/templates.csv \
  --templates-output reports/custom-templates.xml
```

Use `--areas-output` and `--levels-output` for the other overrides. An output
override requires its corresponding input. Output directories must already exist.

Each file is a UTF-8 XML 1.0 document with tab indentation and this structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mapping-table>
	<col-def name="id" type="nocase" />
	<col-def name="name" type="nocase" />
	<row>
		<col>14</col>
		<col>Admin User</col>
	</row>
</mapping-table>
```

CSV `key` maps to the first (`id`) column and CSV `name` to the second (`name`)
column, regardless of CSV header order. Values, row order, duplicates, and leading
zeroes are preserved. XML special characters are escaped automatically. UTF-8 CSV
with or without a BOM, quoted commas, and quoted newlines are supported. A
header-only catalog produces both column definitions and no rows.

Headers must be unique and include `name` and `key`; extra named columns are
ignored. Malformed CSV, inconsistent field counts, blank required values, and
characters forbidden by XML 1.0 cause an error. Every selected input and output
path is validated before writing; outputs cannot alias any selected input or
another output. Input/validation/path failures leave existing XMLs untouched.
Successful conversions overwrite selected outputs and print their paths and row
counts. Disk-write failures can leave partial files; writes are not a multi-file
transaction.

Exit status is 0 for success, 1 for conversion/write failures, and 2 for invalid
CLI arguments. The test command above also checks this converter.
