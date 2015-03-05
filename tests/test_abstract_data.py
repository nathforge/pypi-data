import json
import os.path
import re
import unittest
import xmlrpclib

import httpretty

from pypi_data import AbstractData

PYPI_METADATA_REGEX = re.compile(r'^https://pypi\.python\.org/pypi/(.*)/json$')

class AbstractDataTestCase(unittest.TestCase):
    def setUp(self):
        self.data = Data()
        self.pypi = PyPI()

        archive_filename = os.path.join(os.path.dirname(__file__), 'data/testdata.tar.bz2')
        with open(archive_filename, 'rb') as fp:
            archive_data = fp.read()

        httpretty.enable()

        httpretty.register_uri(httpretty.GET, self.data.ARCHIVE_URL, body=archive_data)
        httpretty.register_uri(httpretty.POST, self.data.PYPI_XMLRPC_URL, body=self.pypi.httpretty_xmlrpc_callback)
        httpretty.register_uri(httpretty.GET, PYPI_METADATA_REGEX, body=self.pypi.httpretty_metadata_callback)

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()

    def test_init(self):
        self.data.init()
        self.assertSetEqual(set(self.data.metadata.keys()), {'distribute', 'setuptools', 'virtualenv'})
        self.assertEqual(self.data.metadata['distribute'], {'info': {'name': 'distribute'}})
        self.assertEqual(self.data.metadata['setuptools'], {'info': {'name': 'setuptools'}})
        self.assertEqual(self.data.metadata['virtualenv'], {'info': {'name': 'virtualenv'}})

    def test_update(self):
        self.data.init()

        self.pypi.metadata['distribute'] = {'info': {'name': 'distribute'}, 'changed': True}
        self.pypi.metadata['new_package'] = {'info': {'name': 'new_package'}}
        self.pypi.metadata['package_not_in_changelog'] = {'info': {'name': 'package_not_in_changelog'}}

        serial = self.data.get_serial()
        self.pypi.add_changelog_entry('old_package', serial=serial - 100)
        self.pypi.add_changelog_entry('distribute', serial=serial + 1)
        self.pypi.add_changelog_entry('new_package', serial=serial + 2)

        self.data.update()
        self.assertSetEqual(set(self.data.metadata.keys()), {'distribute', 'new_package', 'setuptools', 'virtualenv'})
        self.assertEqual(self.data.metadata['distribute'], {'info': {'name': 'distribute'}, 'changed': True})
        self.assertEqual(self.data.metadata['new_package'], {'info': {'name': 'new_package'}})
        self.assertEqual(self.data.metadata['setuptools'], {'info': {'name': 'setuptools'}})
        self.assertEqual(self.data.metadata['virtualenv'], {'info': {'name': 'virtualenv'}})

        del self.pypi.metadata['new_package']
        self.pypi.add_changelog_entry('new_package', serial=serial + 3)
        self.data.update()
        self.assertSetEqual(set(self.data.metadata.keys()), {'distribute', 'setuptools', 'virtualenv'})
        self.assertEqual(self.data.metadata['distribute'], {'info': {'name': 'distribute'}, 'changed': True})
        self.assertEqual(self.data.metadata['setuptools'], {'info': {'name': 'setuptools'}})
        self.assertEqual(self.data.metadata['virtualenv'], {'info': {'name': 'virtualenv'}})

    def test_full_download(self):
        for package in 'package1', 'package2', 'package3':
            self.pypi.metadata[package] = {'info': {'name': package}}
            self.pypi.add_changelog_entry(package)

        self.data.full_download()
        self.assertSetEqual(set(self.data.metadata.keys()), {'package1', 'package2', 'package3'})
        self.assertEqual(self.data.metadata['package1'], {'info': {'name': 'package1'}})
        self.assertEqual(self.data.metadata['package2'], {'info': {'name': 'package2'}})
        self.assertEqual(self.data.metadata['package3'], {'info': {'name': 'package3'}})

        self.data.update()

class PyPI(object):
    def __init__(self):
        self.changelog = []
        self.metadata = {}

    def add_changelog_entry(self, package, version='1.0', timestamp=1, action='new release', serial=None):
        if serial is None:
            serial = self.changelog_last_serial() + 1

        if serial in self.changelog_serials():
            raise ValueError('Serial {} already exists'.format(serial))

        self.changelog.append((package, version, timestamp, action, serial))

    def changelog_serials(self):
        return [iter_serial for (_, _, _, _, iter_serial) in self.changelog]

    def changelog_last_serial(self):
        sorted_serials = sorted(self.changelog_serials())
        if sorted_serials:
            return sorted_serials[-1]
        else:
            return 0

    def httpretty_metadata_callback(self, request, uri, headers):
        package = PYPI_METADATA_REGEX.search(uri).group(1)
        if package in self.metadata:
            return (200, headers, json.dumps(self.metadata[package]))
        else:
            return (404, headers, '')

    def httpretty_xmlrpc_callback(self, request, uri, headers):
        params, method = xmlrpclib.loads(request.body)
        result = getattr(self, 'xmlrpc_{}'.format(method))(*params)
        return (200, headers, xmlrpclib.dumps((result,), methodresponse=True))

    def xmlrpc_changelog_since_serial(self, since_serial):
        filtered_changelog = [
            (name, version, timestamp, action, serial)
            for name, version, timestamp, action, serial in self.changelog
            if serial > since_serial
        ]

        sorted_changelog = sorted(filtered_changelog,
            key=lambda (name, version, timestamp, action, serial): serial
        )

        return sorted_changelog

    def xmlrpc_list_packages(self):
        return self.metadata.keys()

    def xmlrpc_changelog_last_serial(self):
        return self.changelog_last_serial()

class Data(AbstractData):
    def __init__(self):
        self.metadata = {}
        self.serial = None

    def _metadata_exists(self, package):
        return package in self.metadata

    def _get_metadata(self, package):
        return self.metadata[package]

    def _set_metadata(self, package, data):
        self.metadata[package] = data

    def _remove_metadata(self, package):
        if package in self.metadata:
            del self.metadata[package]

    def _get_serial(self):
        return self.serial

    def _set_serial(self, serial):
        self.serial = serial
