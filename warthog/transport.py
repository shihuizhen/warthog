# -*- coding: utf-8 -*-
#
# Warthog - Simple client for A10 load balancers
#
# Copyright 2014-2015 Smarter Travel
#
# Available under the MIT license. See LICENSE for details.
#

"""
warthog.transport
~~~~~~~~~~~~~~~~~

Methods to configure how to interact with the load balancer API over HTTP or HTTPS.
"""

import ssl

import warnings
import requests
from requests.adapters import (
    HTTPAdapter,
    DEFAULT_POOLBLOCK,
    DEFAULT_POOLSIZE,
    DEFAULT_RETRIES)
from requests.packages.urllib3.poolmanager import PoolManager
from requests.packages.urllib3.exceptions import InsecureRequestWarning


# Default to using the SSL/TLS version that the A10 requires instead of
# the default that the requests/urllib3 library picks. Or, maybe the A10
# just doesn't allow the client to negotiate. Either way, we use TLSv1.
DEFAULT_SSL_VERSION = ssl.PROTOCOL_TLSv1


def get_transport_factory(verify=True, ssl_version=DEFAULT_SSL_VERSION):
    """Get a new callable that returns :class:`requests.Session` instances that
    have been configured according to the given parameters.

    :class:`requests.Session` instances are then used for interacting with the API
    of the load balancer over HTTP or HTTPS.

    It is typically not required for user code to call this function directly unless
    you have special requirements such as needing to bypass HTTPS certificate validation
    because you use a self signed certificate.

    :param bool verify: Should SSL certificates by verified when connecting
        over HTTPS? Default is ``True``. If you have chosen not to verify certificates
        warnings about this emitted by the requests library will be suppressed.
    :param int ssl_version: Explicit version of SSL to use for HTTPS connections
        to an A10 load balancer. The version is a constant as specified by the
        :mod:`ssl` module. The default is TLSv1. If you don't wish to use a specific
        version and instead rely on the default for the requests / urllib3 module,
        pass ``ssl_version=None``.
    :return: A callable to return new configured session instances for making HTTP(S)
        requests
    :rtype: callable
    """
    # pylint: disable=missing-docstring
    def factory():
        transport = requests.Session()

        if not verify:
            transport.verify = False

        if ssl_version is not None:
            transport.mount('https://', VersionedSSLAdapter(ssl_version))
        return transport

    # Make sure that we suppress warnings about invalid certs since the user
    # has explicitly asked us to not verify it, they know that we're doing
    # something dangerous and don't care.
    if not verify:
        warnings.filterwarnings("ignore", category=InsecureRequestWarning)

    return factory


class VersionedSSLAdapter(HTTPAdapter):
    """"Transport adapter that requires the use of a specific version of SSL."""

    # pylint: disable=too-many-arguments
    def __init__(self, ssl_version, pool_connections=DEFAULT_POOLSIZE,
                 pool_maxsize=DEFAULT_POOLSIZE, max_retries=DEFAULT_RETRIES,
                 pool_block=DEFAULT_POOLBLOCK):
        self.ssl_version = ssl_version

        super(VersionedSSLAdapter, self).__init__(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=max_retries,
            pool_block=pool_block)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        # pylint: disable=attribute-defined-outside-init
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block,
            ssl_version=self.ssl_version, **pool_kwargs)
