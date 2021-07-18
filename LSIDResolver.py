import os
import argparse
import re
import urllib.request
import dns.resolver
import datetime
import socket

from pathlib import Path
from lxml import etree

# global namespace definitions
NAMESPACES = {'re': 'http://exslt.org/regular-expressions',
                      'wsdl': 'http://schemas.xmlsoap.org/wsdl/',
                      'http': 'http://schemas.xmlsoap.org/wsdl/http/'}


class Resolver:
    """Life Science Identifier resolver (client part)

    Simple CLI application to test LSID resolving. See README for package dependencies
    Usage: $ python LSIDResolver.py -lsid urn:lsid:ipni.org:names:20012728-1
    """

    def __init__(self):
        self.lsid = None
        self.authority = Authority()
        self.service = Service()

    def set_lsid(self, lsid):
        self.lsid = lsid

    def get_lsid(self):
        return self.lsid

    def print_lsid(self):
        print('Resolved LSID: ' + self.lsid)

    def resolve_lsid(self):
        try:
            self.validate_lsid()
            self.authority.get_authority_part(self.lsid)
            self.authority.get_authority_wsdl()
            self.service.get_service_wsdl(self.authority.get_authority_url(), self.authority.get_service_name(),
                                          self.get_lsid())
            # get data and metadata
            print('Data:')
            print(self.service.get_data(self.lsid))
            print('Metadata:')
            print(self.service.get_metadata(self.lsid))

        except (ValidationError, urllib.request.URLError, socket.timeout, dns.resolver.NoAnswer, Exception) as e:
            print('\033[91m' + str(e) + '\033[0m')
            print('LSID resolving failed')

    def validate_lsid(self):
        # All credit for the LSID regex pattern goes to IBM
        pattern = re.compile(
            r'^[uU][rR][nN]:[lL][sS][iI][dD]:[A-Za-z0-9][\w()+,\-.=@;$"!*\']*:[A-Za-z0-9]'
            r'[\w()+,\-.=@;$"!*\']*:[A-Za-z0-9][\w()+,\-.=@;$"!*\']*(:[A-Za-z0-9][\w()+,\-.=@;$"!*\']*)?$'
        )

        if not re.match(pattern, self.lsid):
            raise ValidationError('Error: LSID is not well formed!')
        else:
            print('This is a valid LSID')
            return True


class CacheMixin(object):

    @property
    def cache_instance(self):
        return Cache()


class Singleton(type):

    def __init__(cls, name, bases, attrs, **kwargs):
        super().__init__(name, bases, attrs)
        cls._instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)
        return cls._instance


class Cache(metaclass=Singleton):

    # cache files for 2 days (value in seconds)
    CACHE_TIME = 172800
    PATH = 'cache/'

    def check_cache_file(self, service_name, file_name):
        path = self.PATH + service_name
        cache_file = Path(path + '/' + file_name)

        # check if file exists and cache is still valid
        if (cache_file.exists()) and (self.get_cache_expiration(os.path.getmtime(path + '/' + file_name))):
            return cache_file.read_bytes()
        else:
            return False

    def get_cache_expiration(self, file_date):
        # check if cache is expired
        cache_valid = datetime.datetime.utcnow() - datetime.timedelta(seconds=self.CACHE_TIME)

        if cache_valid <= datetime.datetime.fromtimestamp(file_date):
            return True
        else:
            return False

    def store_cache_file(self, service_name, file_name, content):
        path = self.PATH + service_name

        cache_path = Path(path)
        cache_path.mkdir(parents=True, exist_ok=True)
        cache_file = Path(path + '/' + file_name)
        cache_file.write_bytes(content)


class Authority(CacheMixin):

    def __init__(self):
        self.url_part = None
        self.service_url = None
        self.service_port = None
        self.authority_url = None

    def get_authority_part(self, lsid):
        components = lsid.split(':')
        # get authority part of LSID
        self.url_part = components[2]
        print('Authority part of LSID: ' + self.url_part)
        # set service url from SRV DNS record
        self.set_service_url()

    def set_service_url(self):
        # query DNS SRV record
        answers = dns.resolver.query('_lsid._tcp.' + self.url_part, 'SRV')

        for dnsdata in answers:
            # remove last point in target string
            if dnsdata.target.to_text()[-1] == '.':
                self.service_url = dnsdata.target.to_text()[:-1]
            else:
                self.service_url = dnsdata.target.to_text()

            self.service_port = str(dnsdata.port)
            print('Service target: ' + self.service_url + ' | Port: ' + str(dnsdata.port))

        if not self.service_url:
            raise NoValueError('Error: Unable to parse the service URL in SRV record')

    def get_authority_url(self):
        return self.authority_url

    def get_service_name(self):
        return self.url_part

    def get_authority_wsdl(self):
        file = self.cache_instance.check_cache_file(self.url_part, 'authority.wsdl')

        if not file:
            print('No authority.wsdl file cached or file expired')

            if self.service_port == '443':
                protocol = 'https://'
            else:
                protocol = 'http://'
            url = protocol + self.service_url + ':' + self.service_port + '/authority/'
            answer = urllib.request.urlopen(url, timeout=120)

            wsdl_content = answer.read()
            wsdl = etree.fromstring(wsdl_content)

            # cache the authority answer
            self.cache_instance.store_cache_file(self.url_part, 'authority.wsdl', wsdl_content)
        else:
            print('Cached authority.wsdl file available')
            wsdl = etree.fromstring(file)
        # extract authority url
        self.extract_authority_url(wsdl)

    def extract_authority_url(self, wsdl):

        try:
            (node,) = wsdl.xpath("wsdl:service/wsdl:port[re:test(@binding, "
                                 "'LSIDAuthorityHTTPBinding$')]/*[local-name()='address']", namespaces=NAMESPACES)
        except ValueError:
            raise NoElementError('No authority address element found')

        self.authority_url = node.get('location')
        print('Authority binding: ' + node.get('location'))

        if not self.authority_url:
            raise NoValueError('No HTTP binding in authority.wsdl found')


class Service(CacheMixin):

    def __init__(self):
        self.data_url = None
        self.metadata_url = None

    def get_service_wsdl(self, authority_url, service_name, lsid):
        file = self.cache_instance.check_cache_file(service_name, 'service.wsdl')

        if not file:
            print('No service.wsdl file cached or file expired')
            url = authority_url + '/authority/?lsid=' + lsid
            answer = urllib.request.urlopen(url, timeout=120)
            wsdl_content = answer.read()
            wsdl = etree.fromstring(wsdl_content)
            # cache service file
            self.cache_instance.store_cache_file(service_name, 'service.wsdl', wsdl_content)
        else:
            print('Cached service.wsdl file available')
            wsdl = etree.fromstring(file)

        self.extract_service_url(wsdl)

    def extract_service_url(self, wsdl):

        try:
            (node_data,) = wsdl.xpath("wsdl:service/wsdl:port[re:test(@binding, ':LSIDDataHTTPBinding$')]/http:address",
                                      namespaces=NAMESPACES)
            self.data_url = node_data.get('location')
            print('Data service HTTP binding: ' + node_data.get('location'))
        except ValueError:
            print("No data service endpoint found")

        try:
            (node_metadata,) = wsdl.xpath(
                "wsdl:service/wsdl:port[re:test(@binding, ':LSIDMetadataHTTPBinding$')]/http:address",
                namespaces=NAMESPACES)
            self.metadata_url = node_metadata.get('location')
            print('Metadata service HTTP binding : ' + node_metadata.get('location'))
        except ValueError:
            print("No metadata service endpoint found")

    def get_data(self, lsid):
        if self.data_url is None:
            print('No data URL available')
            return False
        else:
            url = self.data_url + '?lsid=' + lsid
            answer = urllib.request.urlopen(url)
            return answer.read()

    def get_metadata(self, lsid):
        if self.metadata_url is None:
            print('No metadata URL available')
        else:
            url = self.metadata_url + '?lsid=' + lsid
            answer = urllib.request.urlopen(url)
            return answer.read()


class ValidationError(Exception):
    pass


class NoValueError(Exception):
    pass


class NoElementError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(description='LSIDResolver')
    parser.add_argument('-lsid', help='Provide a valid LSID, e.g. urn:lsid:nmbe.ch:spidersp:021946', required=True)
    return parser.parse_args()


def main(lsid):
    print('Resolving LSID ...')
    app = Resolver()
    app.set_lsid(lsid)
    app.resolve_lsid()
    app.print_lsid()


if __name__ == '__main__':
    # parse arguments
    args = parse_args()
    main(args.lsid)
