# -*- coding: utf-8 -*-

"""
"""
import logging
import urlparse

import requests
import warthog.exc


STATUS_ENABLED = 'enabled'

STATUS_DISABLED = 'disabled'

_API_VERSION = 'v2'

_ACTION_AUTHENTICATE = 'authenticate'

_ACTION_ENABLE = _ACTION_DISABLE = 'slb.server.update'

_ACTION_STATUS = 'slb.server.search'

_ACTION_STATISTICS = 'slb.server.fetchStatistics'

_ACTION_CLOSE_SESSION = 'session.close'


def get_log():
    return logging.getLogger('warthog')


class RequestsRunner(object):
    def __init__(self, timeout=None):
        self._timeout = timeout

    def get(self, *args, **kwargs):
        if self._timeout is not None:
            kwargs['timeout'] = self._timeout
        return requests.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        if self._timeout is not None:
            kwargs['timeout'] = self._timeout
        return requests.post(*args, **kwargs)


class SessionStartCommand(object):
    """

    """
    _logger = get_log()

    def __init__(self, scheme_host, username, password, runner=None):
        """
        """
        self._scheme_host = scheme_host
        self._username = username
        self._password = password
        self._runner = runner if runner is not None else RequestsRunner()

    def send(self):
        """
        """
        url = get_base_url(self._scheme_host)
        params = get_base_query_params(_ACTION_AUTHENTICATE)
        params['username'] = self._username
        params['password'] = self._password

        self._logger.debug('Making session start request to %s', url)
        r = self._runner.get(url, params=params)
        self._logger.debug(r.text)
        json = r.json()

        if 'session_id' not in json:
            msg, code = extract_error_message(json['response'])
            raise warthog.exc.WarthogAuthFailureError(
                'Authentication failure with {0}'.format(self._scheme_host), msg, code)
        return json['session_id']


class AuthenticatedCommand(object):
    """

    """
    _logger = get_log()

    def __init__(self, scheme_host, session_id):
        """
        """
        self._scheme_host = scheme_host
        self._session_id = session_id

    def send(self, *args):
        """
        """
        raise NotImplementedError()


class SessionEndCommand(AuthenticatedCommand):
    def __init__(self, scheme_host, session_id, runner=None):
        super(SessionEndCommand, self).__init__(scheme_host, session_id)
        self._runner = runner if runner is not None else RequestsRunner()

    def send(self):
        url = get_base_url(self._scheme_host)
        params = get_base_query_params(_ACTION_CLOSE_SESSION, self._session_id)

        self._logger.debug('Making session close request to %s', url)
        r = self._runner.post(url, params=params)
        self._logger.debug(r.text)
        json = r.json()

        if json['response']['status'] == 'fail':
            msg, code = extract_error_message(json['response'])
            raise warthog.exc.WarthogAuthCloseError(
                'Could not close session {0} on {1}'.format(
                    self._session_id, self._scheme_host), msg, code)
        return True


class NodeEnableCommand(AuthenticatedCommand):
    """

    """

    def __init__(self, scheme_host, session_id, runner=None):
        """


        """
        super(NodeEnableCommand, self).__init__(scheme_host, session_id)
        self._runner = runner if runner is not None else RequestsRunner()

    def send(self, server):
        """
        """
        url = get_base_url(self._scheme_host)
        params = get_base_query_params(_ACTION_ENABLE, self._session_id)
        params['name'] = server
        params['server'] = server
        params['status'] = 1

        self._logger.debug('Making node enable request for %s', server)
        r = self._runner.post(url, params=params)
        self._logger.debug(r.text)
        json = r.json()

        if json['response']['status'] == 'fail':
            msg, code = extract_error_message(json['response'])
            raise warthog.exc.WarthogNodeEnableError(
                'Could not enable node {0}'.format(server), msg, code)
        return True


class NodeDisableCommand(AuthenticatedCommand):
    """

    """

    def __init__(self, scheme_host, session_id, runner=None):
        """
        """
        super(NodeDisableCommand, self).__init__(scheme_host, session_id)
        self._runner = runner if runner is not None else RequestsRunner()

    def send(self, server):
        """
        """
        url = get_base_url(self._scheme_host)
        params = get_base_query_params(_ACTION_ENABLE, self._session_id)
        params['name'] = server
        params['server'] = server
        params['status'] = 0

        self._logger.debug('Making node disable request for %s', server)
        r = self._runner.post(url, params=params)
        self._logger.debug(r.text)
        json = r.json()

        if json['response']['status'] == 'fail':
            msg, code = extract_error_message(json['response'])
            raise warthog.exc.WarthogNodeDisableError(
                'Could not disable node {0}'.format(server), msg, code)
        return True


class NodeStatusCommand(AuthenticatedCommand):
    """

    """

    def __init__(self, scheme_host, session_id, runner=None):
        """

        """
        super(NodeStatusCommand, self).__init__(scheme_host, session_id)
        self._runner = runner if runner is not None else RequestsRunner()

    def send(self, server):
        """
        """
        url = get_base_url(self._scheme_host)
        params = get_base_query_params(_ACTION_STATUS, self._session_id)
        params['name'] = server

        self._logger.debug('Making node status request for %s', server)
        r = self._runner.get(url, params=params)
        self._logger.debug(r.text)
        json = r.json()

        if 'server' not in json:
            msg, code = extract_error_message(json['response'])
            raise warthog.exc.WarthogNodeStatusError(
                'Could not get status of {0}'.format(server), msg, code)

        status = json['server']['status']
        if status:
            return STATUS_ENABLED
        return STATUS_DISABLED


class NodeActiveConnectionsCommand(AuthenticatedCommand):
    """




    """

    def __init__(self, scheme_host, session_id, runner=None):
        """
        """
        super(NodeActiveConnectionsCommand, self).__init__(scheme_host, session_id)
        self._runner = runner if runner is not None else RequestsRunner()

    def send(self, server):
        """
        """
        url = get_base_url(self._scheme_host)
        params = get_base_query_params(_ACTION_STATISTICS, self._session_id)
        params['name'] = server

        self._logger.debug('Making active connection count request for %s', server)
        r = self._runner.get(url, params=params)
        self._logger.debug(r.text)
        json = r.json()

        if 'server_stat' not in json:
            msg, code = extract_error_message(json['response'])
            raise warthog.exc.WarthogNodeStatusError(
                'Could not get active connection count of {0}'.format(server), msg, code)
        return json['server_stat']['cur_conns']


def extract_error_message(response):
    """

    :param response:
    :return:
    """
    if response['status'] == 'fail':
        return response['err']['msg'].strip(), response['err']['code']
    raise ValueError(
        "Unexpected response format from request: {0}".format(response))


def get_base_url(scheme_host):
    """


    :param scheme_host:
    :return:
    """
    return urlparse.urljoin(
        scheme_host, 'services/rest/{version}/'.format(version=_API_VERSION))


def get_base_query_params(action, session_id=None):
    params = {
        'format': 'json',
        'method': action
    }

    if session_id is not None:
        params['session_id'] = session_id
    return params