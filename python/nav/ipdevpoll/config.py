# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 UNINETT AS
#
# This file is part of Network Administration Visualized (NAV).
#
# NAV is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.  You should have received a copy of the GNU General Public
# License along with NAV. If not, see <http://www.gnu.org/licenses/>.
#
"""ipdevpoll configuration management"""

import os
import logging
import ConfigParser
from StringIO import StringIO

import nav.buildconf
from nav.errors import GeneralException

logger = logging.getLogger(__name__)

ipdevpoll_conf_defaults = """
[ipdevpoll]
logfile = ipdevpolld.log

[plugins]

[jobs]
"""

class IpdevpollConfig(ConfigParser.ConfigParser):
    def __init__(self):
        ConfigParser.ConfigParser.__init__(self)
        # TODO: perform sanity check on config settings
        faked_default_file = StringIO(ipdevpoll_conf_defaults)
        self.readfp(faked_default_file)
        self.read_all()

    def read_all(self):
        """Read all known ipdevpoll.conf instances."""
        configfile = 'ipdevpoll.conf'
        filenames = [os.path.join(nav.buildconf.sysconfdir, configfile),
                     os.path.join('.', configfile)]
        files_read = self.read(filenames)

        if files_read:
            logger.debug("Read config files %r", files_read)
        else:
            logger.warning("Found no config files")
        return files_read


def get_jobs(config=None):
    if config is None:
        config = ipdevpoll_conf
    jobs = {}

    job_prefix = 'job_'
    job_sections = [s for s in config.sections() if s.startswith(job_prefix)]
    for section in job_sections:
        job_name = section[len(job_prefix):]

        interval = config.has_option(section, 'interval') and \
            parse_time(config.get(section, 'interval')) or ''
        plugins  = config.has_option(section, 'plugins') and \
            parse_plugins(config.get(section, 'plugins', '')) or ''

        if interval and plugins:
            jobs[job_name] = (interval, plugins)
            logger.debug("Registered job in registry: %s", job_name)

    return jobs

def parse_time(value):
    value = value.strip()

    if value == '':
        return 0

    if value.isdigit():
        return int(value)

    value,unit = int(value[:-1]), value[-1:].lower()

    if unit == 'd':
        return value * 60*60*24
    elif unit == 'h':
        return value * 60*60
    elif unit == 'm':
        return value * 60
    elif unit == 's':
        return value

    raise GeneralException('Invalid time format: %s%s' % (value, unit))

def parse_plugins(value):
    if value:
        return value.split()

    return []

ipdevpoll_conf = IpdevpollConfig()