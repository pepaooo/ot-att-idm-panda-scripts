#!/usr/bin/env python3
"""Export all profiles as JSON and unique template, area, and level pairs as CSV."""

import argparse
import csv
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_URL = 'https://app.acme.com.mx/apiQA/v1/catalogs/profiles'
REPORTS = {'template': 'templates.csv', 'area': 'areas.csv', 'level': 'levels.csv'}


class ExportError(Exception):
    """An API request or response could not be used for a complete export."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward the Authorization header to another destination.
        return None


def fetch_profiles(url: str, token: str, page_size: int) -> dict:
    """Fetch all pages into one content array, preserving complete profile records."""
    profiles = {'content': []}
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if key not in ('page', 'size')]
    opener = build_opener(NoRedirect())
    number = 0
    expected_total = None
    processed = 0

    while True:
        page_query = urlencode(query + [('page', number), ('size', page_size)])
        page_url = urlunsplit(parts._replace(query=page_query))
        request = Request(page_url, headers={
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/json',
        })
        print(f'Requesting page {number} (timeout: 30s)...', file=sys.stderr, flush=True)
        try:
            with opener.open(request, timeout=30) as handle:
                payload = json.load(handle)
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise ExportError(f'HTTP {code} while fetching page {number}. '
                              'Check the endpoint and token.') from None
        except (URLError, OSError):
            raise ExportError(f'Network failure while fetching page {number}.') from None
        except (ValueError, UnicodeError):
            raise ExportError(f'Invalid JSON on page {number}.') from None

        if not isinstance(payload, dict):
            raise ExportError(f'Expected a JSON object on page {number}.')
        content = payload.get('content')
        total = payload.get('totalPages')
        actual_number = payload.get('number')
        last = payload.get('last')
        if (not isinstance(content, list)
                or type(total) is not int or total < 0
                or type(actual_number) is not int or actual_number != number
                or type(last) is not bool):
            raise ExportError(f'Invalid content or pagination metadata on page {number}.')
        if expected_total is None:
            expected_total = total
        if (total != expected_total
                or (total == 0 and (number != 0 or content))
                or (total > 0 and number >= total)
                or last != (number >= total - 1)
                or (not last and not content)):
            raise ExportError(f'Inconsistent pagination metadata on page {number}.')

        profiles['content'].extend(content)
        processed += len(content)
        print(f'Page {number} OK ({number + 1}/{max(total, 1)}): '
              f'{len(content)} profiles; {processed} processed in total.',
              file=sys.stderr, flush=True)
        if last:
            return profiles
        number += 1


def extract_catalogs(profiles: dict) -> dict:
    """Validate the combined profiles and collect unique pairs without changing records."""
    catalogs = {kind: set() for kind in REPORTS}
    for index, record in enumerate(profiles['content']):
        for kind in REPORTS:
            value = record.get(kind) if isinstance(record, dict) else None
            if (not isinstance(value, dict)
                    or not isinstance(value.get('name'), str)
                    or not isinstance(value.get('key'), str)):
                raise ExportError(f'Invalid {kind} name/key in combined profile '
                                  f'{index + 1}; expected strings.')
            catalogs[kind].add((value['name'], value['key']))
    return catalogs


def collect_catalogs(url: str, token: str, page_size: int) -> dict:
    """Fetch and validate all profiles, returning the unique catalog pairs."""
    return extract_catalogs(fetch_profiles(url, token, page_size))


def write_profiles(profiles: dict, output_dir: Path) -> None:
    """Save the full combined document as readable UTF-8 JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / 'profiles.json'
    with target.open('w', encoding='utf-8', newline='\n') as handle:
        json.dump(profiles, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(f"{target}: {len(profiles['content'])} profiles", flush=True)


def write_catalogs(catalogs: dict, output_dir: Path) -> None:
    """Write each category as a sorted UTF-8 CSV with name,key headers."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for kind, filename in REPORTS.items():
        target = output_dir / filename
        with target.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['name', 'key'])
            writer.writerows(sorted(catalogs[kind]))
        print(f'{target}: {len(catalogs[kind])} unique {kind} pairs', flush=True)


def positive_integer(value):
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('must be a positive integer') from None
    if result < 1:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token', required=True, help='Raw bearer token (without the Bearer prefix)')
    parser.add_argument('--url', default=DEFAULT_URL, help='Profiles endpoint URL (HTTPS)')
    parser.add_argument('--page-size', type=positive_integer, default=100,
                        help='Requested profiles per page (default: 100)')
    parser.add_argument('--output-dir', type=Path, default=Path('.'),
                        help='Report directory (default: current directory)')
    args = parser.parse_args(argv)
    if not args.token.strip() or any(char.isspace() for char in args.token):
        parser.error('--token must be a nonempty raw token without whitespace')
    try:
        args.token.encode('ascii')
    except UnicodeEncodeError:
        parser.error('--token must contain ASCII characters')
    try:
        parts = urlsplit(args.url)
        valid = (parts.scheme == 'https' and parts.hostname and parts.port != 0
                 and not parts.username and not parts.password and not parts.fragment
                 and not any(char.isspace() for char in args.url))
    except ValueError:
        valid = False
    if not valid:
        parser.error('--url must be an HTTPS URL without credentials or a fragment')
    try:
        profiles = fetch_profiles(args.url, args.token, args.page_size)
        # Validate every record before replacing any existing JSON or CSV report.
        catalogs = extract_catalogs(profiles)
        write_profiles(profiles, args.output_dir)
        write_catalogs(catalogs, args.output_dir)
        print('Export completed successfully.', flush=True)
    except ExportError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except OSError:
        print('Error: could not create or write the report files. Check the output directory.',
              file=sys.stderr)
        return 1
    except ValueError:
        print('Error: the request URL or headers could not be processed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
