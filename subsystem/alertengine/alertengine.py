#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
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
# Authors: Stein Magnus Jodal <stein.magnus.jodal@uninett.no>
#

"""
The NAV Alert Engine daemon (alertengine)

FIXME: Description

Usage: alertengine [FIXME]

FIXME: Detailed usage
"""

__copyright__ = "Copyright 2007 UNINETT AS"
__license__ = "GPL"
__author__ = "Stein Magnus Jodal (stein.magnus.jodal@uninett.no)"
__id__ = "$Id$"

import ConfigParser
import getopt
import logging
import logging.handlers
import os
import os.path
import pwd
import signal
import socket
import sys
import time

import nav.config
import nav.daemon
import nav.logs
import nav.path
#import nav.alertengine.FIXME


### PATHS

configfile = os.path.join(nav.path.sysconfdir, 'alertengine.conf')
logfile = os.path.join(nav.path.localstatedir, 'log', 'alertengine.log')
pidfile = os.path.join(nav.path.localstatedir, 'run', 'alertengine.pid')


### MAIN FUNCTION

def main(args):
    # Get command line arguments
    try:
        opts, args = getopt.getopt(args, 'h', ['help'])
    except getopt.GetoptError, e:
        print >> sys.stderr, "%s\nTry `%s --help' for more information." % \
            (e, sys.argv[0])
        sys.exit(1)
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(0)

    # Set config defaults
    defaults = {
        'username': 'navcron',
        'delay': '30',
        'loglevel': 'INFO',
        'mailwarnlevel': 'ERROR',
        'mailserver': 'localhost',
        'mailaddr': nav.config.readConfig('nav.conf')['ADMIN_MAIL']
    }

    # Read config file
    config = getconfig(defaults)

    # Set variables based on config
    username = config['main']['username']
    delay = int(config['main']['delay'])
    loglevel = eval('logging.' + config['main']['loglevel'])
    mailwarnlevel = eval('logging.' + config['main']['mailwarnlevel'])
    mailserver = config['main']['mailserver']
    mailaddr = config['main']['mailaddr']

    # Initialize logger
    global logger
    logger = logging.getLogger('nav.alertengine')
    logger.setLevel(1) # Let all info through to the root node
    loginitstderr(loglevel)

    # Switch user to navcron (only works if we're root)
    try:
        nav.daemon.switchuser(username)
    except nav.daemon.DaemonError, e:
        logger.error("%s Run as root or %s to enter daemon mode. " \
            + "Try `%s --help' for more information.",
            e, username, sys.argv[0])
        sys.exit(1)

    # Init daemon loggers
    if not loginitfile(loglevel, logfile):
        sys.exit(1)
    if not loginitsmtp(mailwarnlevel, mailaddr, mailserver):
        sys.exit(1)

    # Check if already running
    try:
        nav.daemon.justme(pidfile)
    except nav.daemon.DaemonError, e:
        logger.error(e)
        sys.exit(1)

    # Daemonize
    try:
        nav.daemon.daemonize(pidfile)
    except nav.daemon.DaemonError, e:
        logger.error(e)
        sys.exit(1)

    # Reopen log files on SIGHUP
    signal.signal(signal.SIGHUP, signalhandler)

    # Loop forever
    while True:
        logger.debug('Starting loop.')

        # FIXME refactor contents of this loop

        for account in Account.objects.all():
            account.check_alerts()

        # Sleep a bit before the next run
        logger.debug('Sleeping for %d seconds.', delay)
        time.sleep(delay)

        # Devel only
        break

    # Exit nicely
    sys.exit(0)


### HELPER FUNCTIONS

def signalhandler(signum, _):
    """Signal handler to close and reopen log file(s) on HUP."""

    if signum == signal.SIGHUP:
        logger.info('SIGHUP received; reopening log files.')
        nav.logs.reopen_log_files()
        logger.info('Log files reopened.')

def getconfig(defaults = None):
    """
    Read whole config from file.

    Arguments:
        ``defaults'' are passed on to configparser before reading config.

    Returns:
        Returns a dict, with sections names as keys and a dict for each
        section as values.
    """

    config = ConfigParser.RawConfigParser(defaults)
    config.read(configfile)

    sections = config.sections()
    configdict = {}

    for section in sections:
        configsection = config.items(section)
        sectiondict = {}
        for opt, val in configsection:
            sectiondict[opt] = val
        configdict[section] = sectiondict

    return configdict

def loginitfile(loglevel, filename):
    """Initalize the logging handler for logfile."""

    try:
        filehandler = logging.FileHandler(filename, 'a')
        fileformat = '[%(asctime)s] [%(levelname)s] [pid=%(process)d %(name)s] %(message)s'
        fileformatter = logging.Formatter(fileformat)
        filehandler.setFormatter(fileformatter)
        filehandler.setLevel(loglevel)
        logger = logging.getLogger()
        logger.addHandler(filehandler)
        return True
    except IOError, error:
        print >> sys.stderr, \
         "Failed creating file loghandler. Daemon mode disabled. (%s)" \
         % error
        return False

def loginitstderr(loglevel):
    """Initalize the logging handler for stderr."""

    try:
        stderrhandler = logging.StreamHandler(sys.stderr)
        stderrformat = '%(levelname)s %(message)s'
        stderrformatter = logging.Formatter(stderrformat)
        stderrhandler.setFormatter(stderrformatter)
        stderrhandler.setLevel(loglevel)
        logger = logging.getLogger()
        logger.addHandler(stderrhandler)
        return True
    except IOError, error:
        print >> sys.stderr, \
         "Failed creating stderr loghandler. Daemon mode disabled. (%s)" \
         % error
        return False

def loginitsmtp(loglevel, mailaddr, mailserver):
    """Initalize the logging handler for SMTP."""

    try:
        # localuser will be root if smsd was started as root, since
        # switchuser() is first called at a later time
        localuser = pwd.getpwuid(os.getuid())[0]
        hostname = socket.gethostname()
        fromaddr = localuser + '@' + hostname

        mailhandler = logging.handlers.SMTPHandler(mailserver, fromaddr,
         mailaddr, 'NAV smsd warning from ' + hostname)
        mailformat = '[%(asctime)s] [%(levelname)s] [pid=%(process)d %(name)s] %(message)s'
        mailformatter = logging.Formatter(mailformat)
        mailhandler.setFormatter(mailformatter)
        mailhandler.setLevel(loglevel)
        logger = logging.getLogger()
        logger.addHandler(mailhandler)
        return True
    except Exception, error:
        print >> sys.stderr, \
         "Failed creating SMTP loghandler. Daemon mode disabled. (%s)" \
         % error
        return False

def usage():
    """Print a usage screen to stderr."""
    print >> sys.stderr, __doc__

def setdelay(sec):
    """Set delay (in seconds) between queue checks."""
    global delay
    if sec.isdigit():
        sec = int(sec)
        delay = sec
        logger.info("Setting delay to %d seconds.", sec)
        return True
    else:
        logger.warning("Given delay not a digit. Using default.")
        return False


### BEGIN
if __name__ == '__main__':
    main(sys.argv[1:])