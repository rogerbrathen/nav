# -*- coding: ISO8859-1 -*-
#
# Copyright 2003, 2004 Norwegian University of Science and Technology
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
# Authors: Magnus Nordseth <magnun@itea.ntnu.no>
#

from nav.statemon.abstractChecker import AbstractChecker
from nav.statemon.event import Event
from nav.statemon import DNS
class DnsChecker(AbstractChecker):
    """
    Valid argument(s): request
    """
    def __init__(self,service, **kwargs):
        AbstractChecker.__init__(self,"dns",service,port=42, **kwargs)
        # Please note that this handler doesn't obey the port directive
    def execute(self):
        ip, port = self.getAddress()
        d = DNS.DnsRequest(server=ip, timeout=self.getTimeout())
        args = self.getArgs()
        #print "Args: ", args
        request = args.get("request","").strip()
        timeout=0
        if not request:
            #print "valid debug message :)"
            return Event.UP, "Argument request must be supplied"
        else:
            answer  = ""
            #print "request: %s"%request[i]
            try:
                reply = d.req(name=request)
            except DNS.Error:
                timeout = 1
                #print "%s timed out..." %request[i]
                    
            if not timeout and len(reply.answers) > 0 :
                answer=1
                #print "%s -> %s"%(request[i], reply.answers[0]["data"])
            elif not timeout and len(reply.answers)==0:
                answer=0

            # This breaks on windows dns servers and probably other not bind servers
            # We just put a exception handler around it, and ignore the resulting
            # timeout.
            try:
                ver = d.req(name="version.bind",qclass="chaos", qtype='txt').answers
                if len(ver) > 0:
                    self.setVersion(ver[0]['data'][0])
            except DNS.Base.DNSError, e:
                if str(e) == 'Timeout':
                    pass  # Ignore timeout
                else:
                    raise            

            if not timeout and answer == 1:
                return Event.UP, "Ok"
            elif not timeout and answer == 1:
                return Event.UP, "No record found, request=%s" % request
            else:
                return Event.DOWN, "Timeout while requesting %s" % request


def getRequiredArgs():
    """
    Returns a list of required arguments
    """
    requiredArgs = ['request']
    return requiredArgs

def provides():
    """
    Returns a string, telling what test this module provides
    """
    return "dns"