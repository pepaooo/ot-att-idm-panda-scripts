import contextlib
import csv
import io
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import export_vendor_catalog as exporter


def vendor(cve='OTHER', name=' Otro (No listado)', business=None):
    return {'cve': cve, 'name': name, 'businessName': business}


def response(payload):
    return io.BytesIO(json.dumps(payload, ensure_ascii=True).encode())


class Progress(io.StringIO):
    def __init__(self):
        super().__init__()
        self.flushes = 0

    def flush(self):
        self.flushes += 1
        super().flush()


class VendorExportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.opener_patch = patch('export_vendor_catalog.build_opener')
        self.opener = self.opener_patch.start().return_value
        self.addCleanup(self.opener_patch.stop)
        self.opener.open.return_value = response([vendor()])

    def run_cli(self, extra=(), output_dir=None):
        stdout, stderr = io.StringIO(), Progress()
        args = ['--token', 'SECRET_TOKEN', '--output-dir', str(output_dir or self.directory), *extra]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = exporter.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_one_get_default_endpoint_and_bearer_header(self):
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.opener.open.call_count, 1)
        call = self.opener.open.call_args
        request = call.args[0]
        self.assertEqual(request.full_url, 'https://panda.att.com.mx/apiQA/v1/catalogs/vendors')
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.get_header('Authorization'), 'Bearer SECRET_TOKEN')
        self.assertEqual(request.get_header('Accept'), 'application/json')
        self.assertEqual(call.kwargs['timeout'], 30)
        self.assertTrue(out.rstrip().endswith('Export completed successfully.'))
        self.assertNotIn('SECRET_TOKEN', out + err)

    def test_custom_url_query_is_unchanged(self):
        url = 'https://example.test/vendors?filter=active'
        self.assertEqual(self.run_cli(['--url', url])[0], 0)
        self.assertEqual(self.opener.open.call_args.args[0].full_url, url)
        self.assertEqual(self.opener.open.call_count, 1)

    def test_csv_and_xml_preserve_all_strings_nulls_order_and_duplicates(self):
        name = '  Área & <Core>, "A"\nNext\r\nMore\rEnd  '
        records = [vendor(), vendor('001', name, '  Business, "Quoted"\nMéxico  '),
                   vendor('EMPTY', 'Empty business', ''), vendor()]
        self.opener.open.return_value = response(records)
        code, _, err = self.run_cli()
        self.assertEqual(code, 0, err)
        with (self.directory / 'vendors.csv').open(encoding='utf-8', newline='') as handle:
            self.assertEqual(list(csv.reader(handle)), [
                ['cve', 'name', 'businessName'], ['OTHER', ' Otro (No listado)', ''],
                ['001', name, '  Business, "Quoted"\nMéxico  '], ['EMPTY', 'Empty business', ''],
                ['OTHER', ' Otro (No listado)', '']])
        raw = (self.directory / 'MT-Catalogo-vendors.xml').read_bytes()
        self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn(b'\n\t<row>', raw)
        self.assertIn(b'&amp;', raw)
        self.assertIn(b'&#13;', raw)
        root = ET.fromstring(raw)
        self.assertEqual(root.tag, 'mapping-table')
        self.assertEqual([node.attrib for node in root.findall('col-def')],
                         [{'name': 'id', 'type': 'nocase'}, {'name': 'name', 'type': 'nocase'}])
        self.assertEqual([[col.text for col in row] for row in root.findall('row')],
                         [[record['cve'], record['name']] for record in records])

    def test_empty_response_and_output_directory_creation(self):
        self.opener.open.return_value = response([])
        target = self.directory / 'new' / 'reports'
        self.assertEqual(self.run_cli(output_dir=target)[0], 0)
        with (target / 'vendors.csv').open(newline='') as handle:
            self.assertEqual(list(csv.reader(handle)), [['cve', 'name', 'businessName']])
        root = ET.parse(target / 'MT-Catalogo-vendors.xml').getroot()
        self.assertEqual(len(root.findall('col-def')), 2)
        self.assertEqual(root.findall('row'), [])

    def test_current_directory_default(self):
        previous = Path.cwd()
        try:
            os.chdir(self.directory)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(exporter.main(['--token', 'SECRET_TOKEN']), 0)
            self.assertTrue(Path('vendors.csv').is_file())
            self.assertTrue(Path('MT-Catalogo-vendors.xml').is_file())
        finally:
            os.chdir(previous)

    def test_request_progress_is_flushed_before_network_call(self):
        progress = Progress()

        def serve(request, timeout):
            self.assertIn('Requesting vendor catalog', progress.getvalue())
            self.assertGreater(progress.flushes, 0)
            return response([vendor()])

        self.opener.open.side_effect = serve
        with contextlib.redirect_stderr(progress):
            records = exporter.fetch_vendors('https://example.test/vendors', 'SECRET_TOKEN')
        self.assertEqual(records, [vendor()])
        self.assertIn('1 vendors', progress.getvalue())

    def test_bad_records_preserve_both_existing_reports(self):
        missing_business = {'cve': 'X', 'name': 'Example'}
        bad_records = [None, {}, missing_business, vendor(cve=1), vendor(name=None),
                       vendor(cve=' '), vendor(name=''), vendor(business=23),
                       vendor(name='bad\x00'), vendor(cve='bad\x01'),
                       vendor(name='bad\ud800'), vendor(business='bad\ud800')]
        payloads = [None, {}, 'wrong'] + [[vendor(), bad] for bad in bad_records]
        for payload in payloads:
            with self.subTest(payload=payload):
                for name in ('vendors.csv', 'MT-Catalogo-vendors.xml'):
                    (self.directory / name).write_text('existing')
                self.opener.open.return_value = response(payload)
                code, out, err = self.run_cli()
                self.assertEqual(code, 1)
                self.assertNotIn('Export completed successfully.', out)
                self.assertNotIn('SECRET_TOKEN', err)
                for name in ('vendors.csv', 'MT-Catalogo-vendors.xml'):
                    self.assertEqual((self.directory / name).read_text(), 'existing')

    def test_http_network_and_invalid_json_failures_hide_sensitive_details(self):
        failures = [HTTPError('https://example.test', status, 'SECRET_TOKEN', {}, io.BytesIO(b'PRIVATE_BODY'))
                    for status in (302, 401, 500)]
        failures += [URLError('SECRET_TOKEN'), TimeoutError('SECRET_TOKEN'), IncompleteRead(b'PRIVATE_BODY')]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                for name in ('vendors.csv', 'MT-Catalogo-vendors.xml'):
                    (self.directory / name).write_text('existing')
                self.opener.open.side_effect = failure
                code, out, err = self.run_cli()
                self.assertEqual(code, 1)
                self.assertNotIn('SECRET_TOKEN', out + err)
                self.assertNotIn('PRIVATE_BODY', out + err)
                for name in ('vendors.csv', 'MT-Catalogo-vendors.xml'):
                    self.assertEqual((self.directory / name).read_text(), 'existing')
        self.opener.open.side_effect = None
        for body in (b'not JSON', b'[\xff]'):
            self.opener.open.return_value = io.BytesIO(body)
            self.assertEqual(self.run_cli()[0], 1)

    def test_invalid_cli_arguments_do_not_make_requests(self):
        for args in ([], ['--token', ''], ['--token', 'SECRET TOKEN'], ['--token', 'bad\x00'],
                     ['--token', 'SECRET', '--url', 'http://example.test'],
                     ['--token', 'SECRET', '--url', 'https://user:pass@example.test'],
                     ['--token', 'SECRET', '--url', 'https://example.test/#fragment']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    exporter.main(args)
                self.assertEqual(caught.exception.code, 2)
        self.opener.open.assert_not_called()

    def test_invalid_output_paths_preserve_existing_csv(self):
        csv_path = self.directory / 'vendors.csv'
        csv_path.write_text('existing')
        (self.directory / 'MT-Catalogo-vendors.xml').mkdir()
        self.assertEqual(self.run_cli()[0], 1)
        self.assertEqual(csv_path.read_text(), 'existing')

    def test_output_aliases_rejected(self):
        for kind in ('symlink', 'hardlink'):
            directory = self.directory / kind
            directory.mkdir()
            csv_path, xml_path = directory / 'vendors.csv', directory / 'MT-Catalogo-vendors.xml'
            csv_path.write_text('existing')
            try:
                if kind == 'symlink':
                    xml_path.symlink_to(csv_path)
                else:
                    os.link(csv_path, xml_path)
            except (OSError, NotImplementedError):
                continue
            self.opener.open.return_value = response([vendor()])
            self.assertEqual(self.run_cli(output_dir=directory)[0], 1)
            self.assertEqual(csv_path.read_text(), 'existing')

    def test_write_failure_has_no_final_success(self):
        original_open = Path.open

        def fail_xml_write(path, mode='r', *args, **kwargs):
            if 'w' in mode and path.name == 'MT-Catalogo-vendors.xml':
                raise OSError('Disk failure SECRET_TOKEN')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', fail_xml_write):
            code, out, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertNotIn('Export completed successfully.', out)
        self.assertNotIn('SECRET_TOKEN', err)
        self.assertNotIn('Traceback', err)


if __name__ == '__main__':
    unittest.main()
