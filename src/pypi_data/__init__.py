import abc
import json
import logging
import os
import os.path
import posixpath
import shutil
import tarfile
import tempfile
import urllib
import urllib2
import xmlrpclib

import six

@six.add_metaclass(abc.ABCMeta)
class AbstractData(object):
    PYPI_XMLRPC_URL = 'https://pypi.python.org/pypi'
    ARCHIVE_URL = 'https://s3.amazonaws.com/pypi-data/data.tar.bz2'

    def init(self):
        self.init_from_archive_url(self.ARCHIVE_URL)

    def init_from_archive_url(self, url):
        logger = self._get_logger()
        with tempfile.NamedTemporaryFile() as fp:
            logger.info('Downloading from {}'.format(url))
            response = urllib2.urlopen(url)
            shutil.copyfileobj(response, fp)
            self.init_from_archive_file(fp)

    def init_from_archive_file(self, fp):
        logger = self._get_logger()
        with tarfile.open(fileobj=fp, mode='r:bz2') as tar:
            for info in tar:
                if not info.isfile():
                    continue

                if info.name == 'serial':
                    self.set_serial(int(tar.extractfile(info).read()))
                else:
                    package = urllib.unquote(posixpath.basename(info.name))
                    logger.info('{}: setting metadata from archive'.format(package))
                    self.set_metadata_from_file(package, tar.extractfile(info))
        self.update()

    def update(self):
        logger = self._get_logger()
        client = self._get_client()
        serial = self.get_serial()
        
        logger.debug('Fetching changelog since serial {}'.format(serial))
        serials = dict()
        for package, _, _, _, serial in client.changelog_since_serial(serial):
            serials[package] = serial

        logger.info('{} package(s) to update'.format(len(serials)))
        package_serials = sorted(serials.iteritems(), key=lambda (package, serial): serial)
        for package, serial in package_serials:
            self.set_metadata_from_remote(package)
            self.set_serial(serial)

    def full_download(self):
        logger = self._get_logger()
        client = self._get_client()

        logger.info('Listing packages')
        packages = client.list_packages()
        logger.info('{} packages available'.format(len(packages)))

        serial = client.changelog_last_serial()
        for package in packages:
            self.set_metadata_from_remote(package)
        self.set_serial(serial)

        self.update()

    def get_remote_metadata(self, package):
        url = 'https://pypi.python.org/pypi/{}/json'.format(urllib.quote(package, safe=''))
        try:
            response = urllib2.urlopen(url)
        except urllib2.HTTPError as exc:
            if exc.code == 404:
                return None
            else:
                raise
        return json.loads(response.read())

    def set_metadata_from_file(self, package, fp):
        self.set_metadata(package, json.loads(fp.read()))

    def set_metadata_from_remote(self, package):
        logger = self._get_logger()
        metadata = self.get_remote_metadata(package)
        if metadata is not None:
            logger.info('{}: updating metadata'.format(package))
            self.set_metadata(package, metadata)
        else:
            logger.info('{}: removing metadata'.format(package))
            self.remove_metadata(package)

    def metadata_exists(self, package):
        return self._metadata_exists(package)

    def get_metadata(self, package):
        return self._get_metadata(package)

    def set_metadata(self, package, data):
        if not isinstance(data, dict):
            raise ValueError('Expected a dict, received {}: {!r}'.format(type(data), data))
        return self._set_metadata(package, data)

    def remove_metadata(self, package):
        return self._remove_metadata(package)

    def get_serial(self):
        return self._get_serial()

    def set_serial(self, serial):
        return self._set_serial(serial)

    def _get_logger(self):
        return logging.getLogger('{}.{}'.format(__name__, type(self).__name__))

    def _get_client(self):
        return xmlrpclib.ServerProxy(self.PYPI_XMLRPC_URL)

    @abc.abstractmethod
    def _metadata_exists(self, package):
        pass

    @abc.abstractmethod
    def _get_metadata(self, package):
        pass

    @abc.abstractmethod
    def _set_metadata(self, package, data):
        pass

    @abc.abstractmethod
    def _remove_metadata(self, package):
        pass

    @abc.abstractmethod
    def _get_serial(self):
        pass

    @abc.abstractmethod
    def _set_serial(self, serial):
        pass

class FileSystemData(AbstractData):
    def __init__(self, path):
        self.path = path

    def _metadata_exists(self, package):
        return os.path.isfile(self._get_metadata_filename(package))

    def _get_metadata(self, package):
        with open(self._get_metadata_filename(package)) as fp:
            return self._unserialize_data(fp.read())

    def _set_metadata(self, package, data):
        serialized_data = self._serialize_data(data)
        filename = self._get_metadata_filename(package)
        path = os.path.dirname(filename)
        try:
            os.makedirs(path)
        except OSError:
            if not os.path.isdir(path):
                raise
        with open(filename, 'w') as fp:
            fp.write(serialized_data)

    def _remove_metadata(self, package):
        filename = self._get_metadata_filename(package)
        try:
            os.remove(filename)
        except OSError:
            if os.path.isfile(filename):
                raise

    def _get_serial(self):
        with open(self._get_serial_filename()) as fp:
            return int(fp.read().strip())

    def _set_serial(self, serial):
        if not isinstance(serial, int):
            raise ValueError('Serial must be an integer')

        with open(self._get_serial_filename(), 'w') as fp:
            fp.write(str(serial))

    def _serialize_data(self, data):
        return json.dumps(data, indent=4)

    def _unserialize_data(self, serialized_data):
        return json.loads(serialized_data)

    def _get_metadata_filename(self, package):
        return os.path.join(*([self.path] + [
            urllib.quote(component)
            for component in (package[0], package)
        ]))

    def _get_serial_filename(self):
        return os.path.join(self.path, 'serial')
