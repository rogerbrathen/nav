#
# $Id$
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
# Authors: Sigurd Gartmann <sigurd-nav@brogar.org>
#
from mod_python import apache

from pprint import pprint,pformat
from mx import DateTime
from nav import db
from nav.web.URI import URI
from nav.web.templates.MachineTrackerTemplate import MachineTrackerTemplate
from socket import gethostbyaddr,gethostbyname,herror

import re

connection = db.getConnection('webfront', 'manage')
database = connection.cursor()

def handler(req):
    args = URI(req.unparsed_uri) 
    
    section = ""
    s = re.search("\/(\w+?)(?:\/$|\?|\&|$)",req.uri)
    if s:   
            section = s.group(1)

    page = MachineTrackerTemplate()
    page.table = None
    tracker = None

    if section.lower() == "mac":
        page.form = MACForm(args.get("mac"),args.get("days"),args.get("dns"),args.get("aip"),args.get("naip"))
        if args.get("mac"):
            tracker = MACSQLQuery(args.get("mac"),args.get("days"))
    elif section.lower() == "switchports" or section.lower() == "switchport" or section.lower() == "swport" or section.lower() == "port" or section.lower() == "swp": 
        page.form = SwPortForm(args.get("switch"),args.get("module"),args.get("port"),args.get("days"),args.get("dns"),args.get("aip"),args.get("naip"))
        if args.get("switch"):
            tracker = SwPortSQLQuery(args.get("switch"),args.get("module"),args.get("port"),args.get("days"))
    else:
        
        prefixid = args.get("prefixid")
        if prefixid:
            sql = "select netaddr from prefix where prefixid=%s"%prefixid
            database.execute(sql)
            (host,mask) = database.fetchone()[0].split("/")
            from_ip = IP(host).toIP()
            to_ip = IP(IP(host)+pow(2,32-int(mask)+1)-1).toIP()
            
        else:
            from_ip = args.get("from_ip")
            to_ip = args.get("to_ip")

        page.form = IPForm(from_ip,to_ip,args.get("days"),args.get("dns"),args.get("aip"),args.get("naip"))
                
        if from_ip or to_ip:
            if from_ip and not to_ip:#ved bare en ip, sett ip2 lik ip1
                to_ip = from_ip
            elif to_ip and not from_ip:#vice versa
                from_ip = to_ip
            elif IP(from_ip)>IP(to_ip):#snur hvis fra_ip er st�rre enn til_ip
                temp_ip = to_ip
                to_ip = from_ip
                from_ip = temp_ip
                temp_ip = None
            
            tracker = IPSQLQuery(from_ip,to_ip,args.get("days"))

    if tracker:
        result = tracker.getTable(args.get("dns"),args.get("aip"),args.get("naip"))

        perty = pformat(result)

        page.table = result

    req.content_type = "text/html"
    req.send_http_header()

    req.write(page.respond())
    return apache.OK


class MachineTrackerSQLQuery:

    def __init__(self,days="7",extra="",order_by=""):

        self.host = {}

        if not days:
            days = 7
            fra = DateTime.today()-(int(days)*DateTime.oneDay)
            fra = fra.strftime("%Y-%m-%d")

        # the infinity part is not needed after kristian's rewrite
            #tidstreng = "(arp.end_time > '" + fra + "' or arp.end_time='infinity')"
        tidstreng = "(arp.end_time  > '" + fra + "')"
    
        if extra:
            extra = "and " + extra

        if not order_by:
            order_by = "arp.ip,arp.mac,cam.sysname,module,port,start"
        order_by = "order by " + order_by
            
#       self.sql = "select distinct arp.ip,cam.mac,cam.sysname,module,port,cam.start_time,cam.end_time from arp left join cam using (mac),netbox where " + tidstreng + " and netbox.prefixid=arp.prefixid " + extra + " order by start_time"
#               self.sql = "select distinct arp.ip,cam.mac,cam.sysname as switch,module,port,arp.start_time as start, arp.end_time as end from arp left join cam using (mac) where " + tidstreng + " " + extra + " " + order_by

# kristian's rewrite
        self.sql = "SELECT arp.ip, arp.mac, cam.sysname AS switch, module, port, arp.start_time AS start, arp.end_time AS end FROM arp LEFT JOIN cam ON (camid=(SELECT camid FROM cam WHERE arp.mac=cam.mac ORDER BY ABS(EXTRACT (epoch FROM (arp.start_time-cam.start_time))) LIMIT 1)) WHERE " + tidstreng + " " + extra + " " + order_by

        #kristian's rewrite
        #(arp.end_time > '2004-10-07')  AND ip BETWEEN '129.241.23.40' AND '129.241.23.50' ORDER BY arp.ip, cam.sysname, module, mac, port, start;
 

            

    def getTable(self, dns="",aip="",naip=""):

        sql = self.sql

        if not aip and not naip:
            aip = True

        database.execute(sql)

        newresult = []
        result = database.fetchall()

        if result:

            if naip and self.ip_from:
                lowestIP = IP(self.ip_from)
                ipt = IP(self.ip_from)

            else:
                lowestIP = IP(result[0][0])
                ipt = IP(result[0][0])
            if naip and self.ip_to:
                highestIP = IP(self.ip_to)
            else:
                highestIP = IP(result[len(result)-1][0])

            newresult = []

            line = 0

            #try:
            while ipt <= highestIP and line <= len(result):

                    if line >= len(result):
                        ip = highestIP
                    else:
                        ip = IP(result[line][0])

                    if ip > ipt or line >= len(result):
                        if naip:
                            if dns:
                                dnsname = self.hostname(ipt.toIP())
                                newline = ResultRow(ipt.toIP(),None,None,None,None,None,None,dnsname)
                            else:
                                newline = ResultRow(ipt.toIP(),None,None,None,None,None,None)

                            newresult.append(newline)

                        ipt += 1
                    #elif ipt == ip:
                    #   ipt += 1

                    else:
                        if ipt == ip:
                            ipt += 1

                        if aip:

                            #funker ikke s� bra, nei datetime(ip,mac,netbox,module,port,start_time,end_time) = [str(l) for l in result[line][:4]]
                            start_time = result[line][5].strftime("%Y-%m-%d %H:%M")
                            end_time = result[line][6]
                            if end_time.year>DateTime.now().year+1:
                                end_time = "infinity"
                            else:
                                end_time = end_time.strftime("%Y-%m-%d %H:%M")
                            #start_time = result[line][5].strftime("%Y-%m-%d %H:%M:%S") #'2003-09-19 13:11:48
                            #end_time = result[line][6].strftime("%Y-%m-%d %H:%M:%S")
                            ipaddr = ip.toIP()                  
                            mac = result[line][1]
                            switch = result[line][2]
                            module = result[line][3]
                            port = result[line][4]

                            if line>0:
                                if str(result[line-1][0]) == ip.toIP() and str(result[line][1]) == str(result[line-1][1]) and str(result[line][2]) == str(result[line-1][2]) and str(result[line][3]) == str(result[line-1][3]) and str(result[line][4]) == str(result[line-1][4]): 
                                    ipaddr = None
                                    mac = None
                                    switch = None
                                    module = None
                                    port = None

                            if dns:
                                if ipaddr:
                                    dnsname = self.hostname(ip.toIP())
                                else:
                                    dnsname = None

                                newline = ResultRow(ipaddr,mac,switch,module,port,start_time,end_time,dnsname)
                            else:
                                newline = ResultRow(ipaddr,mac,switch,module,port,start_time,end_time)

                            newresult.append(newline)

                        line += 1
        else:
            newresult = []

        return newresult


    def hostname(self,ip):

            host = self.host

            if not host.has_key(ip):
                    try:
                            host[ip] = gethostbyaddr(ip)[0]
                    except herror:
                            host[ip] = "--"

            return host[ip]

class ResultRow:
    def __init__(self,ipaddr,mac,switch,module,port,start_time,end_time,dnsname=""):
        self.ipaddr = ipaddr
        self.mac = mac
        self.switch = switch
        self.module = module
        self.port = port
        
        self.start_time = start_time
        self.end_time = end_time
        self.dnsname = dnsname

class MACSQLQuery (MachineTrackerSQLQuery):

    def __init__(self,mac,days="7"):
        mac = re.sub("[^0-9a-fA-F]+","",mac)
        #mac = mac.replace(":", "")
        mac = mac.lower()
        if mac.startswith("*") or mac.endswith("*"):
            extra = "arp.mac ilike '%s'"%mac.replace("*","%")
        else:
            extra = "arp.mac='%s'"%mac
        order_by = "arp.mac,cam.sysname,module,port,arp.ip,start"
        MachineTrackerSQLQuery.__init__(self,days,extra,order_by)

class IPSQLQuery (MachineTrackerSQLQuery):

    def __init__(self,ip_from,ip_to,days="7"):
        ip_from = re.sub("[^0-9.]+","",ip_from)
        ip_to = re.sub("[^0-9.]+","",ip_to)
        self.ip_from = ip_from
        self.ip_to = ip_to
        order_by = "arp.ip,arp.mac,cam.sysname,module,port,start"
        extra = "ip between '%s' and '%s'"%(ip_from,ip_to)
        MachineTrackerSQLQuery.__init__(self,days,extra,order_by)

class SwPortSQLQuery (MachineTrackerSQLQuery):

    def __init__(self,ip,module,port,days="7"):

        #oversetter en evt fra hostname til ip
        #try:
        #   ip = gethostbyname(ip)
        #except:
        #   pass

        order_by = "cam.sysname,module,port,arp.ip,arp.mac,start"
        
        if not module or module=="*":
            modulesql = "cam.module like '%'"
        else:
            modulesql = "cam.module = '%s'"%module

        if not port or port=="*":
            portsql = "cam.port like '%'"
        else:
            portsql = "cam.port = '%s'"%port

        extra = "cam.sysname = '%s' and %s and %s"%(ip,modulesql,portsql)

        MachineTrackerSQLQuery.__init__(self,days,extra,order_by)

class MachineTrackerForm:

    def __init__(self,days="",dns="",aip="",naip=""):
        self.dns = dns
        self.days = days

        if not aip and not naip:
            aip = True
        self.aip = aip
        self.naip = naip
        self.search = ""

class IPForm (MachineTrackerForm):

    def __init__(self,ip_from,ip_to,days,dns,aip,naip): 
        MachineTrackerForm.__init__(self,days,dns,aip,naip)
        self.ip_from = ip_from
        self.ip_to = ip_to
        self.search = "ip"

class MACForm (MachineTrackerForm):
    
    def __init__(self,mac,days,dns,aip,naip):
        MachineTrackerForm.__init__(self,days,dns,aip,naip)
        self.mac = mac
        self.search = "mac"

class SwPortForm (MachineTrackerForm):

    def __init__(self,switch,module="*",port="*",days="",dns="",aip="",naip=""):
        MachineTrackerForm.__init__(self,days,dns,aip,naip)
        self.switch = switch
        self.module = module
        self.port = port
        self.search = "swp" 

class IP(long):
    def __new__(cls, value):
        if type(value) == str and value.count('.') == 3:
            return cls.fromIP(value)
        return long.__new__(cls, value)

    def fromIP(cls, value):
        splitted = value.split('.')
        result = 0
        for part in splitted:
            # Shift 1 byte
            result <<= 8      
            result += long(part)
        return long.__new__(cls, result)

    fromIP = classmethod(fromIP)

    def toIP(self):
        number = self        
        result = []
        while number >0:
            result.append(str(number % 256))
            number >>= 8
        # Ok -- extend with 0s
        result.extend(["0"] * (4-len(result)))
        result.reverse()
        return '.'.join(result)
    def __repr__(self):
        return self.toIP()
    def __add__(self, value):
        return IP(long.__add__(self, value))
    def __sub__(self, value):
        return IP(long.__sub__(self, value))
        return IP(long.__add__(self, value))
