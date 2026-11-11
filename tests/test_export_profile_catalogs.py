import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import export_profile_catalogs as exporter


def item(name='Finance', key='023'):
    return {kind: {'name': name, 'key': key} for kind in ('template', 'area', 'level')}


def page(items, number=0, total=1):
    return {'content': items, 'number': number, 'totalPages': total,
            'last': number >= total - 1}


def response(payload):
    return io.BytesIO(json.dumps(payload).encode('utf-8'))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.opener = patch('export_profile_catalogs.build_opener').start().return_value
        self.addCleanup(patch.stopall)

    def collect(self, payload):
        self.opener.open.return_value = response(payload)
        return exporter.collect_catalogs('https://example.test/profiles', 'SECRET', 100)

    def test_all_pages_unique_pairs_and_request(self):
        self.opener.open.side_effect = [
            response(page([item(), item('Finance', '024')], 0, 2)),
            response(page([item(), item('Other', '023')], 1, 2)),
        ]
        result = exporter.collect_catalogs(
            'https://example.test/profiles?filter=active&page=9&size=2', 'SECRET', 100)
        for kind in ('template', 'area', 'level'):
            self.assertEqual(result[kind], {('Finance', '023'), ('Finance', '024'), ('Other', '023')})
        for number, call in enumerate(self.opener.open.call_args_list):
            request = call.args[0]
            self.assertEqual(parse_qs(urlsplit(request.full_url).query),
                             {'filter': ['active'], 'page': [str(number)], 'size': ['100']})
            self.assertEqual(request.get_header('Authorization'), 'Bearer SECRET')
            self.assertEqual(call.kwargs['timeout'], 30)

    def test_categories_are_independent(self):
        record = item()
        record['area'] = {'name': 'Vendor', 'key': 'VEN'}
        record['level'] = {'name': 'Other', 'key': 'ULOTH'}
        result = self.collect(page([record]))
        self.assertEqual(result['template'], {('Finance', '023')})
        self.assertEqual(result['area'], {('Vendor', 'VEN')})
        self.assertEqual(result['level'], {('Other', 'ULOTH')})

    def test_csv_round_trip_sort_and_overwrite(self):
        pairs = {('Zeta', '002'), ('Área, "Core"\nTransport', '001')}
        catalogs = {kind: pairs for kind in ('template', 'area', 'level')}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'reports'
            with contextlib.redirect_stdout(io.StringIO()):
                exporter.write_catalogs(catalogs, out)
            for filename in ('templates.csv', 'areas.csv', 'levels.csv'):
                with (out / filename).open(encoding='utf-8', newline='') as handle:
                    self.assertEqual(list(csv.reader(handle)), [['name', 'key']] +
                                     [list(pair) for pair in sorted(pairs)])
            with contextlib.redirect_stdout(io.StringIO()):
                exporter.write_catalogs({kind: set() for kind in catalogs}, out)
            self.assertEqual((out / 'templates.csv').read_text(), 'name,key\n')

    def test_empty_catalogs(self):
        self.assertEqual(self.collect(page([], total=0)),
                         {'template': set(), 'area': set(), 'level': set()})

    def test_malformed_records_and_pagination_rejected(self):
        bad = [None, {}, {'content': []}, page([None]), page([{}]),
               page([{'template': None}]), page([item(key=23)]),
               page([item(name=None)]), page([], number=1),
               dict(page([]), last=False), dict(page([]), totalPages=-1),
               dict(page([]), number=True), page([item()], total=0)]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(exporter.ExportError):
                self.collect(payload)

    def test_repeated_page_rejected(self):
        self.opener.open.side_effect = [response(page([item()], 0, 2)),
                                        response(page([item()], 0, 2))]
        with self.assertRaises(exporter.ExportError):
            exporter.collect_catalogs('https://example.test', 'SECRET', 100)

    def test_invalid_json(self):
        self.opener.open.return_value = io.BytesIO(b'not json')
        with self.assertRaises(exporter.ExportError):
            exporter.collect_catalogs('https://example.test', 'SECRET', 100)

    def test_failure_keeps_existing_files_and_hides_token(self):
        failures = [HTTPError('https://example.test', 401, 'SECRET', {}, None),
                    URLError('SECRET'), TimeoutError('SECRET')]
        for failure in failures:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                for name in ('templates.csv', 'areas.csv', 'levels.csv'):
                    (Path(tmp) / name).write_text('existing')
                self.opener.open.side_effect = [response(page([item()], 0, 2)), failure]
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code = exporter.main(['--token', 'SECRET', '--output-dir', tmp])
                self.assertEqual(code, 1)
                self.assertNotIn('SECRET', err.getvalue())
                for name in ('templates.csv', 'areas.csv', 'levels.csv'):
                    self.assertEqual((Path(tmp) / name).read_text(), 'existing')

    def test_invalid_arguments(self):
        for args in ([], ['--token', ''], ['--token', 'SECRET', '--page-size', '0'],
                     ['--token', 'SECRET', '--url', 'file:///tmp/data'],
                     ['--token', 'SECRET', '--url', 'http://example.test']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    exporter.main(args)
                self.assertEqual(caught.exception.code, 2)
        self.opener.open.assert_not_called()

    def test_main_success_prints_counts(self):
        self.opener.open.return_value = response(page([item()]))
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(exporter.main(['--token', 'SECRET', '--output-dir', tmp]), 0)
            self.assertTrue((Path(tmp) / 'templates.csv').exists())
            self.assertIn('1 unique', out.getvalue())
            self.assertNotIn('SECRET', out.getvalue())


if __name__ == '__main__':
    unittest.main()
