import unittest
import LSIDResolver
import datetime
import os

from lxml import etree
from pathlib import Path
from unittest.mock import patch
from io import StringIO


class TestResolver(unittest.TestCase):

    def setUp(self):
        self.resolver = LSIDResolver.Resolver()

    def test_bogus_lsid_throws_exception(self):
        # test bogus LSID
        self.resolver.set_lsid('urn:lsrsp:021946')
        with self.assertRaises(LSIDResolver.ValidationError):
            self.resolver.validate_lsid()

    def test_valid_lsid_returns_true(self):
        self.resolver.set_lsid('urn:lsid:nmbe.ch:spidersp:021946')
        self.assertTrue(self.resolver.validate_lsid())

    def test_no_lsid_argument_provided_exit(self):
        with patch('sys.argv', ['', '']):
            with self.assertRaises(SystemExit):
                LSIDResolver.parse_args()

    def test_empty_lsid_argument_exit(self):
        with patch('sys.argv', ['', '-lsid']):
            with self.assertRaises(SystemExit):
                LSIDResolver.parse_args()


class TestCache(unittest.TestCase):
    def test_cache_valid_file_expiration_function(self):
        cache = LSIDResolver.Cache()
        # cached file is valid
        self.assertTrue(cache.get_cache_expiration(datetime.datetime.utcnow().timestamp()))

    def test_cache_invalid_file_expiration_function(self):
        cache = LSIDResolver.Cache()
        # cached file is invalid
        test_date = datetime.datetime.utcnow() - datetime.timedelta(seconds=cache.CACHE_TIME + 10)
        self.assertFalse(cache.get_cache_expiration(test_date.timestamp()))

    def test_singleton_cache_instance(self):
        self.assertEqual(LSIDResolver.Authority().cache_instance, LSIDResolver.Service().cache_instance)


class TestAuthority(unittest.TestCase):
    def setUp(self):
        self.authority = LSIDResolver.Authority()

    def test_authority_binding_extraction_from_wsdl(self):
        file = Path(os.path.dirname(os.path.realpath(__file__)) + '/files/test_authority.wsdl')
        wsdl = etree.fromstring(file.read_bytes())
        self.authority.extract_authority_url(wsdl)
        self.assertEqual(self.authority.authority_url, 'https://lsid.nmbe.ch:443')

    def test_no_element_throws_error(self):
        with self.assertRaises(LSIDResolver.NoElementError):
            self.authority.extract_authority_url(etree.Element('root'))


class TestService(unittest.TestCase):

    def setUp(self):
        self.service = LSIDResolver.Service()

    def test_service_binding_extraction_from_wsdl(self):
        file = Path(os.path.dirname(os.path.realpath(__file__)) + '/files/test_service.wsdl')
        wsdl = etree.fromstring(file.read_bytes())
        self.service.extract_service_url(wsdl)
        self.assertEqual(self.service.data_url, 'https://lsid.nmbe.ch/authority/data')
        self.assertEqual(self.service.metadata_url, 'https://lsid.nmbe.ch/authority/metadata')

    def test_no_element_shows_message(self):
        with patch('sys.stdout', new=StringIO()) as capture_output:
            self.service.extract_service_url(etree.Element('root'))
            self.assertEqual(capture_output.getvalue().strip(), 'No data service endpoint found\nNo metadata '
                                                            'service endpoint found')


if __name__ == '__main__':
    unittest.main()
