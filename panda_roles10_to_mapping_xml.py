#!/usr/bin/env python3
"""Join PANDA Level 10 roles and second approvers by Id to build workflow mapping XML."""

import argparse
import csv
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


COLUMN_DEFINITIONS = ('DN de perfil', 'Primer aprobador', 'Segundo aprobador', 'Tercer aprobador')
PRIMER_APROBADOR = 'Gerente o nivel superior'
NOT_REQUIRED = '#NOT_REQUIRED#'


class ConversionError(Exception):
    """Input, joining, or output configuration prevents a complete conversion."""


def valid_xml_text(value: str) -> bool:
    return all(char in '\t\n\r' or 0x20 <= ord(char) <= 0xD7FF
               or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF
               for char in value)


def load_records(path: Path, required: tuple, delimiter: str) -> dict:
    """Validate a CSV and return unique normalized records keyed by exact Id."""
    records = {}
    try:
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.reader(handle, delimiter=delimiter, strict=True)
            rows = (row for row in reader if row)
            headers = next(rows, None)
            if (headers is None or any(not header.strip() for header in headers)
                    or len(headers) != len(set(headers)) or not set(required).issubset(headers)):
                raise ConversionError(f'{path}: require unique named headers including {", ".join(required)}.')
            indexes = {field: headers.index(field) for field in required}
            for row in rows:
                if len(row) != len(headers):
                    raise ConversionError(f'{path}, line {reader.line_num}: field count differs from header.')
                record = {}
                for field, index in indexes.items():
                    value = row[index]
                    if not valid_xml_text(value):
                        raise ConversionError(f'{path}, line {reader.line_num}: {field} contains invalid XML 1.0 text.')
                    value = value.strip()
                    if not value:
                        raise ConversionError(f'{path}, line {reader.line_num}: {field} must be nonempty.')
                    record[field] = value
                identifier = record['Id']
                if identifier in records:
                    if records[identifier] != record:
                        raise ConversionError(f'{path}, line {reader.line_num}: conflicting duplicate Id {identifier}.')
                else:
                    records[identifier] = record
    except csv.Error as exc:
        raise ConversionError(f'{path}: malformed CSV ({exc}).') from None
    except UnicodeError:
        raise ConversionError(f'{path}: input must be valid UTF-8.') from None
    return records


def build_mapping_table(approvers: dict, roles: dict) -> bytes:
    """Join by Id and serialize the complete four-column XML mapping table."""
    root = ET.Element('mapping-table')
    for name in COLUMN_DEFINITIONS:
        ET.SubElement(root, 'col-def', name=name, type='nocase')
    for identifier, approver in approvers.items():
        if identifier not in roles:
            raise ConversionError(f'Approver Id {identifier} is missing from the Level 10 role mapping.')
        values = (roles[identifier]['DN'], PRIMER_APROBADOR, approver['Grupo IDM'], NOT_REQUIRED)
        row = ET.SubElement(root, 'row')
        for value in values:
            ET.SubElement(row, 'col').text = value
    ET.indent(root, space='\t')
    # Preserve interior carriage returns through XML parser newline normalization.
    body = ET.tostring(root, encoding='utf-8').replace(b'\r', b'&#13;')
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + body + b'\n'


def validate_output_path(output: Path, inputs: list) -> None:
    """Validate a writable target without allowing it to alias either input."""
    resolved = output.resolve()
    input_paths = {path.resolve() for path in inputs}
    identities = set()
    for source in inputs:
        info = source.stat()
        identities.add((info.st_dev, info.st_ino))
    if resolved in input_paths:
        raise ConversionError('Output must differ from both input files.')
    if not resolved.parent.is_dir() or not os.access(resolved.parent, os.W_OK | os.X_OK):
        raise ConversionError(f'Output directory must exist and be writable: {output.parent}')
    if resolved.exists():
        if not resolved.is_file() or not os.access(resolved, os.W_OK):
            raise ConversionError(f'Output must be a writable regular file: {output}')
        info = resolved.stat()
        if (info.st_dev, info.st_ino) in identities:
            raise ConversionError('Output must not link to either input file.')


def parse_delimiter(value: str) -> str:
    if value.lower() == 'tab':
        return '\t'
    if value.lower() == 'comma':
        return ','
    if len(value) != 1 or value in '\r\n\x00':
        raise argparse.ArgumentTypeError('use tab, comma, or a single non-newline delimiter character')
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_csv', type=Path, help='Approvers CSV with Name, Id, Grupo IDM headers')
    parser.add_argument('output_xml', type=Path, help='Output workflow mapping XML path')
    parser.add_argument('--perfilMapeo', type=Path, required=True, metavar='CSV',
                        help='Comma-separated Level 10 role lookup with Name,Id,DN headers')
    parser.add_argument('--delimiter', type=parse_delimiter, default='tab', metavar='CHAR',
                        help='Approvers delimiter: tab (default), comma, or a single character')
    args = parser.parse_args(argv)
    try:
        roles = load_records(args.perfilMapeo, ('Name', 'Id', 'DN'), ',')
        print(f'Loaded {len(roles)} role mappings from {args.perfilMapeo}', flush=True)
        approvers = load_records(args.input_csv, ('Name', 'Id', 'Grupo IDM'), args.delimiter)
        print(f'Loaded {len(approvers)} approver mappings from {args.input_csv}', flush=True)
        document = build_mapping_table(approvers, roles)
        validate_output_path(args.output_xml, [args.input_csv, args.perfilMapeo])
        args.output_xml.write_bytes(document)
        print(f'XML mapping table written to {args.output_xml}: {len(approvers)} rows', flush=True)
    except (ConversionError, OSError, ValueError, UnicodeError, RuntimeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
