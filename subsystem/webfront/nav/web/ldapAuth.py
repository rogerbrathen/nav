# -*- coding: UTF-8 -*-
# Copyright 2004 Norwegian University of Science and Technology
# Copyright 2007 UNINETT AS
#
# This file is part of Network Administration Visualized (NAV)
#
# NAV is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# NAV is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with NAV; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#
# $Id$
# Authors: Morten Brekkevold <morten.brekkevold@uninett.no>
#          Bjørn Ove Grøtan <bgrotan@itea.ntnu.no>
#
"""
Contains ldap authentication functionality for NAV web.
"""
import sys
import logging
import ConfigParser
from os.path import join
from StringIO import StringIO

from nav.path import sysconfdir
import nav.errors

logger = logging.getLogger("nav.web.ldapAuth")
# Set default config params and read rest from file
_default_config = StringIO("""
[ldap]
enabled=no
port=389
encryption=none
uid_attr=uid
name_attr=cn
require_group=
timeout=2
debug=no
""")
config = ConfigParser.SafeConfigParser()
config.readfp(_default_config)
_default_config.close()
config.read(join(sysconfdir, 'webfront', 'webfront.conf'))

try:
    import ldap
    available = 1
except ImportError,e:
    available = 0
    ldap = None
    logger.warning("Python LDAP module is not available (%s) ", e)
else:
    # Determine whether the config file enables ldap functionality or not
    available = config.getboolean('ldap', 'enabled')



#
# Function definitions
#


def openLDAP():
    """
    Returns a freshly made LDAP object, according to the settings
    configured in webfront.conf.
    """
    # Get config settings
    server = config.get('ldap', 'server')
    port = config.getint('ldap', 'port')
    encryption = config.get('ldap', 'encryption').lower()
    timeout = config.getfloat('ldap', 'timeout')
    # Revert to no encryption if none of the valid settings are found
    if encryption not in ('ssl', 'tls', 'none'):
        logger.warning('Unknown encryption setting %s in config file, '
                       'using no encryption instead',
                       repr( config.get('ldap', 'encryption') ))
        encryption = 'none'

    # Debug tracing from python-ldap/openldap to stderr
    if config.getboolean('ldap', 'debug'):
        ldap.set_option(ldap.OPT_DEBUG_LEVEL, 255)

    # Use STARTTLS if enabled, then fail miserably if the server
    # does not support it
    if encryption == 'tls':
        logger.debug("Using STARTTLS for ldap connection")
        l = ldap.open(server, port)
        l.timeout = timeout
        try:
            l.start_tls_s()
        except ldap.PROTOCOL_ERROR, e:
            logger.error('LDAP server %s does not support the STARTTLS '
                         'extension.  Aborting.', server)
            raise NoStartTlsError, server
        except (ldap.SERVER_DOWN, ldap.CONNECT_ERROR), e:
            logger.exception("LDAP server is down")
            raise NoAnswerError, server
    else:
        scheme = encryption == 'ssl' and 'ldaps' or 'ldap'
        uri = '%s://%s:%s' % (scheme, server, port)
        l = ldap.initialize(uri)
        l.timeout = timeout

    return l

def authenticate(login, password):
    """
    Attempt to authenticate the login name with password against the
    configured LDAP server.  If the user is authenticated, required
    group memberships are also verified.
    """
    l = openLDAP()
    server = config.get('ldap', 'server')
    user_dn = getUserDN(login)
    # Bind to user_dn using the supplied password
    try:
        logger.debug("Attempting authenticated bind to %s", user_dn)
        l.simple_bind_s(user_dn, password)
    except (ldap.SERVER_DOWN, ldap.CONNECT_ERROR), e:
        logger.exception("LDAP server is down")
        raise NoAnswerError, server
    except ldap.INVALID_CREDENTIALS, e:
        logger.warning("Server %s reported invalid credentials for user %s",
                       server, login)
        return False
    except ldap.TIMEOUT, e:
        logger.error("Timed out waiting for LDAP bind operation")
        raise TimeoutError, e
    except ldap.LDAPError,e:
        logger.exception("An LDAP error occurred when authenticating user %s "
                         "against server %s", login, server)
        return False

    logger.debug("LDAP authenticated user %s", login)
    
    # If successful so far, verify required group memberships before
    # the final verdict is made
    group_dn = config.get('ldap', 'require_group')
    if group_dn:
        if isGroupMember(l, login, group_dn):
            logger.info("%s is verified to be a member of %s",
                        login, group_dn)
            return True
        else:
            logger.warning("Could NOT verify %s as a member of %s",
                           login, group_dn)
            return False

    # If no group matching was needed, we are already authenticated,
    # so return that.
    return True

def getUserDN(uid):
    """
    Given a user id (login name), return a fully qualified DN to
    identify this user, using the configured settings from
    webfront.conf.
    """
    uid_attr = config.get('ldap', 'uid_attr')
    basedn = config.get('ldap', 'basedn')
    user_dn = '%s=%s,%s' % (uid_attr, uid, basedn)
    return user_dn

def isGroupMember(l, uid, group_dn):
    """
    Verify that uid is a member in the group object identified by
    group_dn, using the pre-initialized ldap object l.

    The full user DN will be attempted matched against the member
    attribute of the group object.  If no match is found, the user uid
    will be attempted matched against the memberUid attribute.  The
    former should work well for groupOfNames and groupOfUniqueNames
    objects, the latter should work for posixGroup objects.
    """
    user_dn = getUserDN(uid)
    # Match groupOfNames/groupOfUniqueNames objects
    try:
        filterstr = '(member=%s)' % user_dn
        result = l.search_s(group_dn, ldap.SCOPE_BASE, filterstr)
        logger.debug("groupOfNames results: %s", result)
        if len(result) < 1:
            # If no match, match posixGroup objects
            filterstr = '(memberUid=%s)' % uid
            result = l.search_s(group_dn, ldap.SCOPE_BASE, filterstr)
            logger.debug("posixGroup results: %s", result)
        return len(result) > 0
    except ldap.TIMEOUT, e:
        logger.error("Timed out while veryfing group memberships")
        raise TimeoutError, e

def getUserName(uid):
    """
    Attempt to retrieve the LDAP Common Name of the given login name.
    """
    l = openLDAP()
    user_dn = getUserDN(uid)
    server = config.get('ldap', 'server')
    name_attr = config.get('ldap', 'name_attr')
    try:
        res = l.search_s(user_dn, ldap.SCOPE_BASE, '(objectClass=*)',
                         [name_attr])
    except ldap.LDAPError, e:
        logger.exception("Caught exception while retrieving user name "
                         "from LDAP, returning None as name")
        return None

    # Just look at the first result record, since we are searching for
    # a specific user
    record = res[0][1]
    name = record[name_attr][0]
    return name

#
# Exception classes
#
class Error(nav.errors.GeneralException):
    """General LDAP error"""

class NoAnswerError(Error):
    """No answer from the LDAP server"""

class TimeoutError(Error):
    """Timed out waiting for LDAP reply"""

class NoStartTlsError(Error):
    """The LDAP server does not support the STARTTLS extension"""

def __test():
    """
    Test user login if module is run as script on command line.
    """
    import logging
    from getpass import getpass
    import sys
    logging.basicConfig()
    logging.getLogger('').setLevel(logging.DEBUG)
    
    print "Username: ",
    uid = sys.stdin.readline().strip()
    p = getpass('Password: ')

    if authenticate(uid, p):
        print "User was authenticated."
        uname = getUserName(uid)
        print "User's full name is %s" % uname
    else:
        print "User was not authenticated"

if __name__ == '__main__':
    __test()