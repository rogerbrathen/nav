# -*- coding: utf-8 -*-
#
# Copyright 2007-2008 UNINETT AS
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
# Authors: Kristian Klette <kristian.klette@uninett.no>
#

__copyright__ = "Copyright 2007-2008 UNINETT AS"
__license__ = "GPL"
__author__ = "Kristian Klette (kristian.klette@uninett.no)"
__id__ = "$Id$"

from django.core import serializers
from django.core import serializers
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response as render_to_response_orig
from django.template import Context, Template
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils import simplejson
from django.db.models import Q

import datetime
import socket
import sys

from nav.django.shortcuts import render_to_response, object_list
from nav.models.cabling import Cabling, Patch
from nav.models.manage import Netbox, Module, SwPort, GwPort, Cam, Arp, GwPortPrefix, SwPortVlan
from nav.models.service import Service

from nav.web.templates.NetworkExplorerTemplate import NetworkExplorerTemplate

import nav.natsort

from search import *

def index(request):
    """Basic view of the network"""

    routers = Netbox.objects.all().filter(category__in=['GW', 'GSW'])
    for router in routers:
        if len(router.get_gwports()) > 0:
            router.has_children = True
    return render_to_response(NetworkExplorerTemplate, 'networkexplorer/base.html',
        {
            'routers': routers,
        })

def expand_router(request):
    """
    Returns children of an router according to spec
    """
    router = get_object_or_404(Netbox, id=request.REQUEST['netboxid'])
    gwports = router.get_gwports()
    interface_names = [p.interface for p in gwports]
    unsorted = dict(zip(interface_names, gwports))
    interface_names.sort(key=nav.natsort.split)
    sorted_ports = [unsorted[i] for i in interface_names]

    for gwport in sorted_ports:
        gwport.prefixes = []
        # Check if the port is expandable
        gpp = GwPortPrefix.objects.filter(gwport__id=gwport.id).exclude(prefix__vlan__net_type='static')
        for prefix in gpp:
            netmask_pos = prefix.prefix.net_address.find('/')
            netmask = prefix.prefix.net_address[netmask_pos:]
            prefix.display_addr = prefix.gw_ip + netmask
            gwport.prefixes.append(prefix)

            vlans = prefix.prefix.vlan.swportvlan_set.exclude(vlan__net_type='static').filter(swport__module__netbox=gwport.module.netbox)
            for vlan in vlans:
                if vlan.swport.swportblocked_set.filter(vlan=vlan.vlan.vlan).count() < 1:
                    gwport.has_children = True

        gwport.prefixes.sort()
        if gwport.to_netbox:
            continue
        if gwport.to_swport and gwport.to_swport.module.netbox:
            gwport.to_netbox = gwport.to_swport.module.netbox
            continue
        # Find connection trough prefixes
        try:
            for gwprefix in gwport.gwportprefix_set.exclude(prefix__vlan__net_type='static'):
                for prefix in prefix.gwportprefix_set.all().exclude(
                        gwport=gwport, prefix__vlan_net_type='static'):
                    gwport.to_netbox = prefix.gwport.module.netbox
                    raise StopIteration # Ugly hack since python doesnt support labeled breaks
        except:
            continue

    return render_to_response_orig('networkexplorer/expand_router.html',
        {
            'sysname': router.sysname,
            'ports': sorted_ports,
        })

def expand_gwport(request):
    """
    """
    gwport = get_object_or_404(GwPort, id=request.REQUEST['gwportid'])
    sys.stderr.write("Expanding gwport %s\n" % gwport)
    sys.stderr.flush()
    vlans = []
    foreign_netboxes = []
    prefixes = gwport.gwportprefix_set.all().exclude(prefix__vlan__net_type='static')
    sys.stderr.write("- Found %s gwportprefixes\n" % len(prefixes))
    sys.stderr.flush()
    for prefix in prefixes:
        sys.stderr.write("-- Scanning prefix %s\n" % prefix)
        sys.stderr.flush()
        for vlan in prefix.prefix.vlan.swportvlan_set.all().filter(
                        swport__module__netbox=gwport.module.netbox
                        ).order_by('swport__interface'):

            sys.stderr.write("--- Checking vlan %s\n" % vlan)
            sys.stderr.flush()
            # Check if port is spanningtreeblocked
            sys.stderr.write("---- Blocked: ")
            if vlan.swport.swportblocked_set.filter(vlan=vlan.vlan.vlan).count() > 0:
                sys.stderr.write(" yes. skipping this vlan\n")
                sys.stderr.flush()
                continue
            sys.stderr.write(" no.\n")
            sys.stderr.flush()
            if vlan and not vlan in vlans:
                vlan.swport.has_children = False
                sys.stderr.write("---- Checking for services\n")
                sys.stderr.flush()
                if vlan.swport.to_netbox and vlan.swport.to_netbox.service_set.all().count() > 0:
                    sys.stderr.write("----- Netbox %s has services\n" % vlan.swport.to_netbox)
                    sys.stderr.flush()
                    vlan.swport.has_children = True
                    vlan.swport.has_services = True
                sys.stderr.write("---- Checking for cam-entries\n")
                sys.stderr.flush()
                a= Cam.objects.filter(\
                        netbox=vlan.swport.module.netbox,\
                        ifindex=vlan.swport.ifindex,\
                        end_time__gt=datetime.datetime.max)
                if a.count() > 0:

                    sys.stderr.write("----- Found cam-entry\n\n %s \n\n" % a.query)
                    sys.stderr.flush()
                    vlan.swport.has_children = True
                sys.stderr.write("---- Checking for connected swport\n")
                sys.stderr.flush()
                if vlan.swport.to_swport:
                    sys.stderr.write("----- Found swport %s\n" % vlan.swport.to_swport)
                    sys.stderr.flush()
                    if vlan.swport.to_swport.module.netbox.category.id in ('SW','GSW','EDGE'):
                        vlan.swport.has_children = True
                        vlan.swport.connected_to_switch = True
                    if vlan.swport.to_swport.module.netbox.service_set.all().count() > 0:
                        vlan.swport.has_children = True
                    if Cam.objects.filter( \
                                                netbox=vlan.swport.to_swport.module.netbox, \
                                                ifindex=vlan.swport.to_swport.ifindex,\
                                                end_time__gt=datetime.datetime.max \
                                                ).count() > 0:
                        vlan.swport.has_children = True
                sys.stderr.write("vlan %s has_children = %s\n" % (vlan, vlan.swport.has_children))
                sys.stderr.flush()
                vlans.append(vlan)
                sys.stderr.write("Appended vlan %s to vlans - current len: %s\n" %(vlan, len(vlans)))
                sys.stderr.flush()
                foreign_netboxes.append(vlan.swport.module.netbox)
                sys.stderr.write("Appended netbox %s to f.netboxes - current len: %s\n" %(vlan.swport.module.netbox, len(foreign_netboxes)))
                sys.stderr.flush()
    sys.stderr.write("Sorting swports by interface\n")
    sys.stderr.flush()
    interface_names = [p.swport.interface for p in vlans]
    unsorted = dict(zip(interface_names, vlans))
    interface_names.sort(key=nav.natsort.split)
    vlans = [unsorted[i] for i in interface_names]

    return render_to_response_orig('networkexplorer/expand_gwport.html',
        {
            'gwport': gwport,
            'vlans': vlans,
        }, context_instance=RequestContext(request))

def expand_switch(request):
    """
    """
    switch = get_object_or_404(Netbox, id=request.REQUEST['netboxid'])
    vlan = request.REQUEST['vlanid'] or None
    swports = SwPort.objects.filter(module__netbox=switch)
    swportvlans = SwPortVlan.objects.filter(swport__in=swports,vlan__id=vlan)

    for swportvlan in swportvlans:
        if swportvlan.swport.to_swport:
            if swportvlan.swport.module.netbox.service_set.all().count() > 0:
                swportvlan.swport.has_children = True
                continue
        if Cam.objects.filter(
            netbox=swportvlan.swport.module.netbox,
            ifindex=swportvlan.swport.ifindex,
            end_time__gt=datetime.datetime.max).count() > 0:
            swportvlan.swport.has_children = True

    interface_names = [p.swport.interface for p in swportvlans]
    unsorted = dict(zip(interface_names, swportvlans))
    interface_names.sort(key=nav.natsort.split)
    vlans = [unsorted[i] for i in interface_names]

    return render_to_response_orig('networkexplorer/expand_switch.html',
        {
            'swportvlans': vlans,
        }, context_instance=RequestContext(request))


def expand_swport(request):
    """
    """
    swport = get_object_or_404(SwPort, id=request.REQUEST['swportid'])
    if swport.to_netbox:
        to_netbox = swport.to_netbox
    elif swport.to_swport:
        to_netbox = swport.to_swport.module.netbox
    else:
        to_netbox = None

    if to_netbox:
        services = to_netbox.service_set.all()
    else:
        services = []

    active_macs = Cam.objects.filter(netbox=swport.module.netbox, ifindex=swport.ifindex, end_time__gt=datetime.datetime.max)
    hosts_behind_port = []
    for mac in active_macs:
        arp_entries = Arp.objects.filter(mac=mac.mac, end_time__gt=datetime.datetime.max)
        for arp_entry in arp_entries:
            try:
                hostname = socket.gethostbyaddr(arp_entry.ip)[0]
            except:
                hostname = None
            if hostname:
                host_string = "%s (%s) [<a href=\"/machinetracker/mac?mac=%s&days=7\" target=\"_blank\">%s</a>]" % (hostname, arp_entry.ip, mac.mac, mac.mac)
            else:
                host_string = " %s [<a href=\"/machinetracker/mac?mac=%s&days=7\" target=\"_blank\">%s</a>]" % (arp_entry.ip, mac.mac, mac.mac)
            if host_string not in hosts_behind_port:
                hosts_behind_port.append(host_string)
        if len(arp_entries) < 1 and mac.mac not in hosts_behind_port:
            hosts_behind_port.append(mac.mac)
    hosts_behind_port.sort()


    return render_to_response_orig('networkexplorer/expand_swport.html',
        {
            'netbox': to_netbox,
            'services': services,
            'active_hosts': hosts_behind_port,
        })


def search(request):
    """
    """
    # Raise 404 if no parameters are given
    if 'lookup_field' not in request.REQUEST:
        raise Http404

    router_matches = []
    gwport_matches = []
    swport_matches = []

    if request.REQUEST['lookup_field'] == 'sysname':
        result = sysname_search(request.REQUEST['query'])
        router_matches = result[0]
        gwport_matches = result[1]
        swport_matches = result[2]

    if request.REQUEST['lookup_field'] == 'ip':
        result = ip_search(request.REQUEST['query'])
        router_matches = result[0]
        gwport_matches = result[1]
        swport_matches = result[2]

    if request.REQUEST['lookup_field'] == 'mac':
        result = mac_search(request.REQUEST['query'])
        router_matches = result[0]
        gwport_matches = result[1]
        swport_matches = result[2]
    
    if request.REQUEST['lookup_field'] == 'room':
        result = room_search(request.REQUEST['query'])
        router_matches = result[0]
        gwport_matches = result[1]
        swport_matches = result[2]
    
    if request.REQUEST['lookup_field'] == 'vlan':
        result = vlan_search(request.REQUEST['query'])
        router_matches = result[0]
        gwport_matches = result[1]
        swport_matches = result[2]
    
    if request.REQUEST['lookup_field'] == 'port':
        result = portname_search(request.REQUEST['query'])
        router_matches = result[0]
        gwport_matches = result[1]
        swport_matches = result[2]


    # A bit ugly hack to remove duplicates, but simplejson doesnt seem to support sets
    router_matches = list(set(router_matches))
    gwport_matches = list(set(gwport_matches))
    swport_matches = list(set(swport_matches))

    # Get the html up-front
    routers = []
    for router in router_matches:
        req = FakeRequest()
        req.REQUEST['netboxid'] = router.id
        routers.append([router.id, expand_router(req).content])

    gwports = []
    for gwport in gwport_matches:
        req = FakeRequest()
        req.REQUEST['gwportid'] = gwport.id
        gwports.append([gwport.id, expand_gwport(req).content])

    swports = []
    for swport in swport_matches:
        req = FakeRequest()
        req.REQUEST['swportid'] = swport.id
        swports.append([swport.id, expand_swport(req).content])

    return HttpResponse(simplejson.dumps({'routers': routers, 'gwports': gwports, 'swports': swports}))

class FakeRequest:
    """Simple class for faking requests"""
    def __init__(self):
        self.REQUEST = {}
        self.GET = {}
        self.POST = {}
