# -*- coding: utf-8 -*-
#
# Warthog - Simple client for A10 load balancers
#
# Copyright 2014 Smarter Travel
#
# Available under the MIT license. See LICENSE for details.
#

"""
warthog.client
~~~~~~~~~~~~~~

Simple interface for a load balancer with retry logic and intelligent draining of nodes.
"""

import time
import contextlib

import warthog.core
import warthog.exceptions
import warthog.transport


class CommandFactory(object):
    """Factory for getting new :mod:`warthog.core` command instances that each
    perform some type of request against the load balancer API.

    It is typically not required for user code to instantiate this class directly
    unless you have special requirements and need to inject a custom ``transport_factory``
    method.

    This class is thread safe.
    """

    def __init__(self, transport_factory):
        """Set the a factory that will create new HTTP Sessions instances to be
        used for executing commands.

        :param callable transport_factory: Callable for creating new Session instances
            for executing commands.
        """
        self._transport_factory = transport_factory

    def get_session_start(self, scheme_host, username, password):
        """Get a new command instance to start a session.

        :param basestring scheme_host: Scheme, host, and port combination of the load balancer.
        :param basestring username: Name of the user to authenticate with.
        :param basestring password: Password for the user to authenticate with.
        :return: A new command to start a session.
        :rtype: warthog.core.SessionStartCommand
        """
        return warthog.core.SessionStartCommand(
            self._transport_factory(), scheme_host, username, password)

    def get_session_end(self, scheme_host, session_id):
        """Get a new command instance to close an existing session.

        :param basestring scheme_host: Scheme, host, and port combination of
            the load balancer.
        :param basestring session_id: Previously authenticated session ID.
        :return: A new command to close a session.
        :rtype: warthog.core.SessionEndCommand
        """
        return warthog.core.SessionEndCommand(
            self._transport_factory(), scheme_host, session_id)

    def get_server_status(self, scheme_host, session_id, server):
        """Get a new command to get the status (enabled / disabled) of a server.

        :param basestring scheme_host: Scheme, host, and port combination of
            the load balancer.
        :param basestring session_id: Previously authenticated session ID.
        :param basestring server: Host name of the server to get the status of.
        :return: A new command to get the status of a server.
        :rtype: warthog.core.NodeStatusCommand
        """
        return warthog.core.NodeStatusCommand(
            self._transport_factory(), scheme_host, session_id, server)

    def get_enable_server(self, scheme_host, session_id, server):
        """Get a new command to enable a server at the node level.

        :param basestring scheme_host: Scheme, host, and port combination of
            the load balancer.
        :param basestring session_id: Previously authenticated session ID.
        :param basestring server: Host name of the server to enable.
        :return: A new command to enable a server.
        :rtype: warthog.core.NodeEnableCommand
        """
        return warthog.core.NodeEnableCommand(
            self._transport_factory(), scheme_host, session_id, server)

    def get_disable_server(self, scheme_host, session_id, server):
        """Get a new command to disable a server at the node level.

        :param basestring scheme_host: Scheme, host, and port combination of the
            load balancer.
        :param basestring session_id: Previously authenticated session ID.
        :param basestring server: Host name of the server to disable.
        :return: A new command to disable a server.
        :rtype: warthog.core.NodeDisableCommand
        """
        return warthog.core.NodeDisableCommand(
            self._transport_factory(), scheme_host, session_id, server)

    def get_active_connections(self, scheme_host, session_id, server):
        """Get a new command to get the number of active connections to a server.

        :param basestring scheme_host: Scheme, host, and port combination of
            the load balancer.
        :param basestring session_id: Previously authenticated session ID.
        :param basestring server: Host name of the server to get the number of
            active connections to.
        :return: A new command to get active connections to a server.
        :rtype: warthog.core.NodeActiveConnectionsCommand
        """
        return warthog.core.NodeActiveConnectionsCommand(
            self._transport_factory(), scheme_host, session_id, server)


def _get_default_cmd_factory():
    """Get a :class:`CommandFactory` instance configured to use the TLS version
    expected by the A10 when using https connections.

    :return: Default command factory for building new commands to interact
        with the A10 load balancer
    :rtype: WarthogCommandFactory
    """
    return CommandFactory(warthog.transport.get_transport_factory())


@contextlib.contextmanager
def session_context(scheme_host, username, password, commands):
    """Context manager that makes a request to start an authenticated session, yields the
    session ID, and then closes the session afterwards.

    :param basestring scheme_host: Scheme, host, and port combination of the load balancer.
    :param basestring username: Name of the user to authenticate with.
    :param basestring password: Password for the user to authenticate with.
    :param CommandFactory commands: Factory instance for creating new commands
        for starting and ending sessions with the load balancer.
    :return: The session ID of the newly established session.
    """
    session = None
    try:
        start_cmd = commands.get_session_start(scheme_host, username, password)
        session = start_cmd.send()

        yield session
    finally:
        if session is not None:
            end_cmd = commands.get_session_end(scheme_host, session)
            end_cmd.send()


@contextlib.contextmanager
def disabled_node_context(client, server, logger):
    """Context manager that disables a server, yields, and then enables the server
    again if it was initially enabled. If the server was disabled before we started
    operating on it, it will be left disabled.

    :param WarthogClient client: Client to use for manipulating the server
    :param basestring server: Hostname of the server to disable and enable
    :param logging.Logger logger: Logger instance to use
    """
    status = client.get_status(server)
    is_in_lb = (status == warthog.core.STATUS_ENABLED)

    if is_in_lb:
        client.disable_server(server)
    else:
        logger.debug(
            'Server %s was not in load balancer (%s), not disabling...', server, status)

    yield

    if is_in_lb:
        client.enable_server(server)
    else:
        logger.debug(
            'Server %s was not in load balancer (%s), not enabling...', server, status)


class WarthogClient(object):
    """Client for interacting with an A10 load balancer to get the status
    of nodes managed by it, enable them, and disable them.

    This class is thread safe.
    """
    _logger = warthog.core.get_log()
    _default_wait_interval = 2.0

    # pylint: disable=too-many-arguments
    def __init__(self, scheme_host, username, password,
                 wait_interval=_default_wait_interval, commands=None):
        """Set the load balancer scheme/host/port combination, username and password
        to use for connecting and authenticating with the load balancer.

        Optionally, the amount of time to wait between retries of various operations
        and the factory used for creating commands may be set.

        If the interval between retries is not supplied, the default is two seconds.

        If the command factory is not supplied, a default instance will be used. The
        command factory is also responsible for creating new :class:`requests.Session`
        instances to be used by each command. The default configuration is to use
        session instances that use TLSv1 for SSL connections and verify certificates.

        :param basestring scheme_host: Scheme, host, and port combination of the load balancer.
        :param basestring username: Name of the user to authenticate with.
        :param basestring password: Password for the user to authenticate with.
        :param float wait_interval: How long (in seconds) to wait between each retry of
            various operations (waiting for nodes to transition, waiting for connections
            to close, etc.).
        :param CommandFactory commands: Factory instance for creating new commands for
            starting and ending sessions with the load balancer.
        """
        self._scheme_host = scheme_host
        self._username = username
        self._password = password
        self._interval = wait_interval
        self._commands = commands if commands is not None else _get_default_cmd_factory()

    def _session_context(self):
        """Get a new context manager that starts and ends a session with the load balancer."""
        self._logger.debug('Creating new session context for %s', self._scheme_host)
        return session_context(self._scheme_host, self._username, self._password, self._commands)

    def disabled_context(self, server):
        """Return a context manager that will disable the given server, yield, and then
        enable the server. Note that the context manager will not re-enable the server
        afterwards if the server was initially disabled.

        Typical usage would look like this.

        .. code-block:: python

            with client.disabled_context('app1.example.com'):
                install_my_app_or_something()

        This is an equivalent and more concise way to do something like the following.

        .. code-block:: python

            enabled = ('enabled' == client.get_status('app1.example.com'))
            if enabled:
                client.disable_server('app1.example.com')

            install_my_app_or_something()

            if enabled:
                client.enable_server('app1.example.com')

        :param basestring server: Hostname of the server to disable and enable
        :return: Context manager for disabling and enabling a server
        """
        self._logger.debug('Creating new disabled node context for %s', server)
        return disabled_node_context(self, server, self._logger)

    def get_status(self, server):
        """Get the current status of the given server, at the node level.

        The status will be one of the constants :data:`warthog.core.STATUS_ENABLED`
        :data:`warthog.core.STATUS_DISABLED`, or :data:`warthog.core.STATUS_DOWN`.

        :param basestring server: Hostname of the server to get the status of.
        :return: The current status of the server, enabled, disabled, or down.
        :rtype: basestring
        :raises warthog.exceptions.WarthogAuthFailureError: If authentication with
            the load balancer failed when trying to establish a new session for this
            operation.
        :raises warthog.exceptions.WarthogNoSuchNodeError: If the load balancer does
            not recognize the given hostname.
        :raises warthog.exceptions.WarthogNodeStatusError: If there are any other
            problems getting the status of the given server.
        """
        with self._session_context() as session:
            cmd = self._commands.get_server_status(
                self._scheme_host, session, server)
            return cmd.send()

    def get_connections(self, server):
        """Get the current number of active connections to a server, at the node level.

        The number of connections will be 0 or a positive integer.

        :param basestring server: Hostname of the server to get the number of active
            connections for.
        :return: The number of active connections total for the node, across all groups
            the server is in.
        :rtype: int
        :raises warthog.exceptions.WarthogAuthFailureError: If authentication with
            the load balancer failed when trying to establish a new session for this
            operation.
        :raises warthog.exceptions.WarthogNoSuchNodeError: If the load balancer does
            not recognize the given hostname.
        :raises warthog.exceptions.WarthogNodeStatusError: If there are any other
            problems getting the active connections for the given server.

        .. versionadded:: 0.4.0
        """
        with self._session_context() as session:
            cmd = self._commands.get_active_connections(
                self._scheme_host, session, server)
            return cmd.send()

    def disable_server(self, server, max_retries=5):
        """Disable a server at the node level, optionally retrying when there are transient
        errors and waiting for the number of active connections to the server to reach zero.

        If ``max_retries`` is zero, no attempt will be made to retry on transient errors
        or to wait until there are no active connections to the server, the method will
        try a single time to disable the server and then return immediately.

        :param basestring server: Hostname of the server to disable
        :param int max_retries: Max number of times to sleep and retry when encountering
            some sort of transient error when disabling the server and while waiting for
            the number of active connections to a server to reach zero.
        :return: True if the server was disabled, false otherwise.
        :rtype: bool
        :raises warthog.exceptions.WarthogAuthFailureError: If authentication with
            the load balancer failed when trying to establish a new session for this
            operation.
        :raises warthog.exceptions.WarthogNoSuchNodeError: If the load balancer does
            not recognize the given hostname.
        :raises warthog.exceptions.WarthogNodeDisableError: If there are any other
            problems disabling the given server.
        """
        with self._session_context() as session:
            disable = self._commands.get_disable_server(
                self._scheme_host, session, server)
            self._try_repeatedly(disable.send, max_retries)

            active = self._commands.get_active_connections(
                self._scheme_host, session, server)
            self._wait_for_connections(active.send, max_retries)

            status = self._commands.get_server_status(
                self._scheme_host, session, server)
            return warthog.core.STATUS_DISABLED == status.send()

    # NOTE: there's a fair amount of duplicate code between this method and _wait_for_status
    # and we could consolidate them to one method that just accepts a function and waits for
    # it to return true and then break. But, this way we have more useful debug information
    # logged at the expense of duplicate code.
    # pylint: disable=missing-docstring
    def _wait_for_connections(self, conn_method, max_retries):
        retries = 0

        while retries < max_retries:
            conns = conn_method()
            if conns == 0:
                break

            self._logger.debug(
                "Connections still active: %s, sleeping for %s seconds...", conns, self._interval)
            time.sleep(self._interval)
            retries += 1

    def enable_server(self, server, max_retries=5):
        """Enable a server at the node level, optionally retrying when there are transient
        errors and waiting for the server to enter the expected, enabled state.

        If ``max_retries`` is zero, no attempt will be made to retry on transient errors
        or to wait until the server enters the expected, enabled state, the method will
        try a single time to enable the server then return immediately.

        :param basestring server: Hostname of the server to enable
        :param int max_retries: Max number of times to sleep and retry when encountering
            some transient error while trying to enable the server
        :return: True if the server was enabled, false otherwise
        :rtype: bool
        :raises warthog.exceptions.WarthogAuthFailureError: If authentication with
            the load balancer failed when trying to establish a new session for this
            operation.
        :raises warthog.exceptions.WarthogNoSuchNodeError: If the load balancer does
            not recognize the given hostname.
        :raises warthog.exceptions.WarthogNodeEnableError: If there are any other
            problems enabling the given server.
        """
        with self._session_context() as session:
            enable = self._commands.get_enable_server(
                self._scheme_host, session, server)
            self._try_repeatedly(enable.send, max_retries)

            status = self._commands.get_server_status(
                self._scheme_host, session, server)
            self._wait_for_enable(status.send, max_retries)

            return warthog.core.STATUS_ENABLED == status.send()

    # pylint: disable=missing-docstring
    def _wait_for_enable(self, status_method, max_retries):
        retries = 0

        while retries < max_retries:
            status = status_method()
            if status == warthog.core.STATUS_ENABLED:
                break

            self._logger.debug(
                "Server is not yet enabled (%s), sleeping for %s seconds...",
                status, self._interval)
            time.sleep(self._interval)
            retries += 1

    def _try_repeatedly(self, method, max_retries):
        """Execute a method, retrying if it fails due to a transient error
        up to a given number of times, with the instance-wide interval in
        between each try.
        """
        retries = 0

        while True:
            try:
                return method()
            except warthog.exceptions.WarthogApiError as e:
                if e.api_code not in warthog.core.TRANSIENT_ERRORS or retries >= max_retries:
                    raise
                self._logger.debug(
                    "Encountered transient error %s - %s, retrying... ", e.api_code, e.api_msg)
                time.sleep(self._interval)
                retries += 1
