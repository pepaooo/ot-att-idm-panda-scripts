#!/usr/bin/env python3
"""Fetch PANDA vendors once and export CSV and XML while preserving string values."""

import argparse
import csv
import io
import json
import os
import sys
import xml.etree.ElementTree as ET
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_URL = 'https://panda.att.com.mx/apiQA/v1/catalogs/vendors'
CSV_FIELDS = ('cve', 'name', 'businessName')


class ExportError(Exception):
    """The vendor response or report configuration cannot produce a complete export."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the bearer token to a redirect destination.
        return None


def valid_xml_text(value: str) -> bool:
    return all(char in '\t\n\r' or 0x20 <= ord(char) <= 0xD7FF
               or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF
               for char in value)


def validate_vendors(payload) -> list:
    """Validate the complete response without changing any record or string."""
    if not isinstance(payload, list):
        raise ExportError('Expected a JSON array of vendors.')
    for index, record in enumerate(payload, start=1):
        if not isinstance(record, dict) or not set(CSV_FIELDS).issubset(record):
            raise ExportError(f'Vendor {index}: expected cve, name, and businessName fields.')
        for field in ('cve', 'name'):
            value = record[field]
            if not isinstance(value, str) or not value.strip():
                raise ExportError(f'Vendor {index}: {field} must be a nonblank string.')
            if not valid_xml_text(value):
                raise ExportError(f'Vendor {index}: {field} contains invalid XML 1.0 text.')
        business = record['businessName']
        if business is not None and not isinstance(business, str):
            raise ExportError(f'Vendor {index}: businessName must be a string or null.')
        try:
            for field in CSV_FIELDS:
                if record[field] is not None:
                    record[field].encode('utf-8')
        except UnicodeError:
            raise ExportError(f'Vendor {index}: invalid Unicode string.') from None
    return payload


def fetch_vendors(url: str, token: str) -> list:
    """Perform one GET without pagination and return fully validated vendor records."""
    request = Request(url, headers={'Authorization': 'Bearer ' + token,
                                    'Accept': 'application/json'})
    opener = build_opener(NoRedirect())
    print('Requesting vendor catalog (timeout: 30s)...', file=sys.stderr, flush=True)
    try:
        with opener.open(request, timeout=30) as handle:
            payload = json.load(handle)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        raise ExportError(f'HTTP {code} fetching vendor catalog. Check the endpoint and token.') from None
    except (URLError, OSError, HTTPException):
        raise ExportError('Network failure while fetching vendor catalog.') from None
    except (ValueError, UnicodeError):
        raise ExportError('Invalid JSON in the vendor response.') from None
    vendors = validate_vendors(payload)
    print(f'Received and validated {len(vendors)} vendors.', file=sys.stderr, flush=True)
    return vendors


def build_mapping_table(vendors: list) -> bytes:
    """Build the cve/name mapping with UTF-8 declaration and tab indentation."""
    root = ET.Element('mapping-table')
    for field in ('id', 'name'):
        ET.SubElement(root, 'col-def', name=field, type='nocase')
    for vendor in vendors:
        row = ET.SubElement(root, 'row')
        ET.SubElement(row, 'col').text = vendor['cve']
        ET.SubElement(row, 'col').text = vendor['name']
    ET.indent(root, space='\t')
    # XML parsers normalize literal CRs; references preserve the original values.
    body = ET.tostring(root, encoding='utf-8').replace(b'\r', b'&#13;')
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + body + b'\n'


def validate_output_paths(paths: list) -> None:
    """Check both targets and reject aliases before either report is opened."""
    resolved_paths, identities = set(), set()
    for path in paths:
        resolved = path.resolve()
        if resolved in resolved_paths:
            raise ExportError('CSV and XML outputs must not refer to the same file.')
        resolved_paths.add(resolved)
        if not resolved.parent.is_dir() or not os.access(resolved.parent, os.W_OK | os.X_OK):
            raise ExportError('Report output directories must exist and be writable.')
        if resolved.exists():
            if not resolved.is_file() or not os.access(resolved, os.W_OK):
                raise ExportError('Report outputs must be writable regular files.')
            info = resolved.stat()
            identity = (info.st_dev, info.st_ino)
            if identity in identities:
                raise ExportError('CSV and XML outputs must not be links to the same file.')
            identities.add(identity)


def write_reports(vendors: list, output_dir: Path) -> None:
    """Prepare both complete documents, validate their paths, then write reports."""
    csv_buffer = io.StringIO(newline='')
    writer = csv.writer(csv_buffer)
    writer.writerow(CSV_FIELDS)
    for vendor in vendors:
        writer.writerow([vendor['cve'], vendor['name'],
                         '' if vendor['businessName'] is None else vendor['businessName']])
    csv_document = csv_buffer.getvalue().encode('utf-8')
    xml_document = build_mapping_table(vendors)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / 'vendors.csv'
    xml_path = output_dir / 'MT-Catalogo-vendors.xml'
    validate_output_paths([csv_path, xml_path])
    for path, document in ((csv_path, csv_document), (xml_path, xml_document)):
        path.write_bytes(document)
        print(f'{path}: {len(vendors)} rows', flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token', required=True, help='Raw bearer token (without the Bearer prefix)')
    parser.add_argument('--url', default=DEFAULT_URL, help='Vendors endpoint URL (HTTPS)')
    parser.add_argument('--output-dir', type=Path, default=Path('.'),
                        help='Report directory (default: current directory)')
    args = parser.parse_args(argv)
    if not args.token or any(not 0x21 <= ord(char) <= 0x7E for char in args.token):
        parser.error('--token must be a nonempty raw ASCII token without whitespace or controls')
    try:
        parts = urlsplit(args.url)
        valid = (parts.scheme == 'https' and parts.hostname and parts.port != 0
                 and not parts.username and not parts.password and not parts.fragment
                 and not any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F
                             for char in args.url))
    except ValueError:
        valid = False
    if not valid:
        parser.error('--url must be an HTTPS URL without credentials, controls, whitespace, or a fragment')
    try:
        vendors = fetch_vendors(args.url, args.token)
        write_reports(vendors, args.output_dir)
        print('Export completed successfully.', flush=True)
    except ExportError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except (OSError, RuntimeError):
        print('Error: could not create or write the report files. Check the output directory.',
              file=sys.stderr)
        return 1
    except (ValueError, UnicodeError):
        print('Error: the request or output data could not be processed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
