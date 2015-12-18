#!/usr/bin/env python
#
# Copyright (C) 2015 UNINETT
#
# This file is part of Network Administration Visualized (NAV).
#
# NAV is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.  You should have received a copy of the GNU General Public License
# along with NAV. If not, see <http://www.gnu.org/licenses/>.
#
"""
Retrieves IANAs current list of assigned enterprise numbers, and outputs
the data NAV wants, as Python code.
"""
from __future__ import print_function
import sys
import os
from collections import namedtuple, Counter
import urllib2
import re
import string
from datetime import datetime

from nav import enterprise

IANA_URL = "http://www.iana.org/assignments/enterprise-numbers"
Enterprise = namedtuple('Enterprise', 'decimal organization contact email')

VENDOR_MAP = {value: constant for constant, value in vars(enterprise).items()
              if constant.startswith('VENDOR_ID_')}
_used_names = Counter(VENDOR_MAP)

REPLACE_PATTERN = re.compile(r'[/_-]', re.UNICODE)
STRIP_UNDERSCORES = re.compile(r'(^_+|_+$)')
STRIP_MULTI_UNDERSCORES = re.compile(r'__+')


def main():
    req = urllib2.urlopen(IANA_URL)
    enterprises = list(parse_enterprises(req))
    print("# IANA assigned enterprise numbers")
    print("# As published at {}".format(IANA_URL))
    print("# Generated by {} on {}".format(os.path.basename(sys.argv[0]),
                                           datetime.now()))
    print("#")

    entmap = {}
    for ent in enterprises:
        var = get_vendor_variable(ent)
        if var:
            entmap[ent] = var
            print("{} = {}".format(var, ent.decimal))

    print("\n# Name map\n")
    print("VENDOR_NAMES = {")

    for ent in enterprises:
        if ent in entmap:
            print("    {}: {!r},".format(entmap[ent], ent.organization))

    print("}")


def parse_enterprises(filehandle):
    """Extracts Enterprise tuples from the given filehandle"""
    line = filehandle.readline()
    while line != "":
        if line.rstrip().isdigit():
            decimal = int(line.strip())
            organization = filehandle.readline().decode('utf-8').strip()
            contact = filehandle.readline().decode('utf-8').strip()
            email = filehandle.readline().decode('utf-8'
                                                 ).strip().replace('&', '@')
            if email == u'---none---':
                email = None
            yield Enterprise(decimal, organization, contact, email)

        line = filehandle.readline()


def get_vendor_variable(ent):
    """Returns a suitable vendor id variable name for the given ent"""
    if ent.decimal in VENDOR_MAP:
        # Keep existing variable names from NAV for, stability and glory!
        name = VENDOR_MAP[ent.decimal]
        return name

    if not ent.organization:
        return

    name = REPLACE_PATTERN.sub(' ', ent.organization.upper())
    name = ''.join(c for c in name if c not in string.punctuation)
    name = name.encode('ascii', errors='ignore').replace(' ', '_')
    name = STRIP_UNDERSCORES.sub('', name)
    name = STRIP_MULTI_UNDERSCORES.sub('_', name)
    name = "VENDOR_ID_{}".format(name)

    _used_names.update([name])
    if _used_names[name] > 1:
        name = "{}_{}".format(name, _used_names[name])

    return name


if __name__ == '__main__':
    main()
