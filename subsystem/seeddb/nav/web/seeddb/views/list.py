# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 UNINETT AS
#
# This file is part of Network Administration Visualized (NAV).
#
# NAV is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 2 as published by the Free
# Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.  You should have received a copy of the GNU General Public License
# along with NAV. If not, see <http://www.gnu.org/licenses/>.
#

from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, InvalidPage
from django.shortcuts import render_to_response
from django.template import RequestContext

from nav.django.utils import get_verbose_name
from nav.models.cabling import Cabling, Patch
from nav.models.manage import Netbox, NetboxType, Room, Location, Organization
from nav.models.manage import Usage, Vendor, Subcategory, Vlan, Prefix
from nav.models.service import Service

from nav.web.seeddb.utils.list import render_list
from nav.web.seeddb.forms import NetboxFilterForm, RoomFilterForm,\
    OrganizationFilterForm, NetboxTypeFilterForm, SubcategoryFilterForm,\
    VlanFilterForm, CablingFilterForm

TITLE_DEFAULT = 'NAV - Seed Database'
NAVPATH_DEFAULT = [('Home', '/'), ('Seed DB', '/seeddb/')]

def netbox_list(request):
    qs = Netbox.objects.all()
    filter = NetboxFilterForm(request.GET)
    value_list = (
        'sysname', 'room', 'ip', 'category', 'organization', 'read_only',
        'read_write', 'type__name', 'device__serial')
    extra = {
        'active': {'netbox': True},
        'title': TITLE_DEFAULT + ' - IP Devices',
        'caption': 'IP Devices',
        'navpath': NAVPATH_DEFAULT + [('IP Devices', None)],
        'tab_template': 'seeddb/tabs_netbox.html',
    }
    return render_list(request, qs, value_list, 'seeddb-netbox-edit',
        edit_url_attr='sysname',
        filter_form=filter,
        extra_context=extra)

def service_list(request):
    qs = Service.objects.all()
    value_list = ('netbox__sysname', 'handler', 'version')
    extra = {
        'active': {'service': True},
        'title': TITLE_DEFAULT + ' - Services',
        'caption': 'Services',
        'navpath': NAVPATH_DEFAULT + [('Services', None)],
        'tab_template': 'seeddb/tabs_service.html',
    }
    return render_list(request, qs, value_list, 'seeddb-service-edit',
        extra_context=extra)

def room_list(request):
    qs = Room.objects.all()
    filter = RoomFilterForm(request.GET)
    value_list = (
        'id', 'location', 'description', 'optional_1', 'optional_2',
        'optional_3', 'optional_4')
    extra = {
        'active': {'room': True},
        'title': TITLE_DEFAULT + ' - Rooms',
        'caption': 'Rooms',
        'navpath': NAVPATH_DEFAULT + [('Rooms', None)],
        'tab_template': 'seeddb/tabs_room.html',
    }
    return render_list(request, qs, value_list, 'seeddb-room-edit',
        filter_form=filter,
        extra_context=extra)

def location_list(request):
    qs = Location.objects.all()
    value_list = ('id', 'description')
    extra = {
        'active': {'location': True},
        'title': TITLE_DEFAULT + ' - Locations',
        'caption': 'Locations',
        'navpath': NAVPATH_DEFAULT + [('Locations', None)],
        'tab_template': 'seeddb/tabs_location.html',
        'hide_move': True,
    }
    return render_list(request, qs, value_list, 'seeddb-location-edit',
        extra_context=extra)

def organization_list(request):
    qs = Organization.objects.all()
    filter = OrganizationFilterForm(request.GET)
    value_list = (
        'id', 'parent', 'description', 'optional_1', 'optional_2',
        'optional_3')
    extra = {
        'active': {'organization': True},
        'title': TITLE_DEFAULT + ' - Organizations',
        'caption': 'Organizations',
        'navpath': NAVPATH_DEFAULT + [('Organizations', None)],
        'tab_template': 'seeddb/tabs_organization.html',
    }
    return render_list(request, qs, value_list, 'seeddb-organization-edit',
        filter_form=filter,
        extra_context=extra)

def usage_list(request):
    qs = Usage.objects.all()
    value_list = ('id', 'description')
    extra = {
        'active': {'usage': True},
        'title': TITLE_DEFAULT + ' - Usage categories',
        'caption': 'Usage categories',
        'navpath': NAVPATH_DEFAULT + [('Usage categories', None)],
        'tab_template': 'seeddb/tabs_usage.html',
    }
    return render_list(request, qs, value_list, 'seeddb-usage-edit',
        extra_context=extra)

def netboxtype_list(request):
    qs = NetboxType.objects.all()
    filter = NetboxTypeFilterForm(request.GET)
    value_list = (
        'name', 'vendor', 'description', 'sysobjectid', 'frequency', 'cdp',
        'tftp')
    extra = {
        'active': {'type': True},
        'title': TITLE_DEFAULT + ' - Types',
        'caption': 'Types',
        'navpath': NAVPATH_DEFAULT + [('Types', None)],
        'tab_template': 'seeddb/tabs_type.html',
    }
    return render_list(request, qs, value_list, 'seeddb-type-edit',
        filter_form=filter,
        extra_context=extra)

def vendor_list(request):
    qs = Vendor.objects.all()
    value_list = ('id',)
    extra = {
        'active': {'vendor': True},
        'title': TITLE_DEFAULT + ' - Vendors',
        'caption': 'Vendors',
        'navpath': NAVPATH_DEFAULT + [('Vendors', None)],
        'tab_template': 'seeddb/tabs_vendor.html',
    }
    return render_list(request, qs, value_list, 'seeddb-vendor-edit',
        extra_context=extra)

def subcategory_list(request):
    qs = Subcategory.objects.all()
    filter = SubcategoryFilterForm(request.GET)
    value_list = ('id', 'category', 'description')
    extra = {
        'active': {'subcategory': True},
        'title': TITLE_DEFAULT + ' - Subcategories',
        'caption': 'Subcategories',
        'navpath': NAVPATH_DEFAULT + [('Subcategories', None)],
        'tab_template': 'seeddb/tabs_subcategory.html',
    }
    return render_list(request, qs, value_list, 'seeddb-subcategory-edit',
        filter_form=filter,
        extra_context=extra)

def vlan_list(request):
    qs = Vlan.objects.all()
    filter = VlanFilterForm(request.GET)
    value_list = (
        'id', 'vlan', 'net_type', 'organization', 'usage', 'net_ident',
        'description')
    extra = {
        'active': {'vlan': True},
        'title': TITLE_DEFAULT + ' - Vlan',
        'caption': 'Vlan',
        'navpath': NAVPATH_DEFAULT + [('Vlan', None)],
        'tab_template': 'seeddb/tabs_vlan.html',
    }
    return render_list(request, qs, value_list, 'seeddb-vlan-edit',
        filter_form=filter,
        extra_context=extra)

def prefix_list(request):
    qs = Prefix.objects.filter(vlan__net_type__edit=True)
    value_list = (
        'net_address', 'vlan__net_type', 'vlan__organization',
        'vlan__net_ident', 'vlan__usage', 'vlan__description', 'vlan__vlan')
    extra = {
        'active': {'prefix': True},
        'title': TITLE_DEFAULT + ' - Prefix',
        'caption': 'Prefix',
        'navpath': NAVPATH_DEFAULT + [('Prefix', None)],
        'tab_template': 'seeddb/tabs_prefix.html',
    }
    return render_list(request, qs, value_list, 'seeddb-prefix-edit',
        extra_context=extra)

def cabling_list(request):
    qs = Cabling.objects.all()
    filter = CablingFilterForm(request.GET)
    value_list = (
        'room', 'jack', 'building', 'target_room', 'category', 'description')
    extra = {
        'active': {'cabling': True},
        'title': TITLE_DEFAULT + ' - Cabling',
        'caption': 'Cabling',
        'navpath': NAVPATH_DEFAULT + [('Cabling', None)],
        'tab_template': 'seeddb/tabs_cabling.html',
    }
    return render_list(request, qs, value_list, 'seeddb-cabling-edit',
        filter_form=filter,
        extra_context=extra)

def patch_list(request):
    qs = Patch.objects.all()
    value_list = (
        'interface__netbox', 'interface__module', 'interface__baseport',
        'cabling__room', 'cabling__jack', 'split')
    extra = {
        'active': {'patch': True},
        'title': TITLE_DEFAULT + ' - Patch',
        'caption': 'Patch',
        'navpath': NAVPATH_DEFAULT + [('Patch', None)],
        'tab_template': 'seeddb/tabs_patch.html',
    }
    return render_list(request, qs, value_list, 'seeddb-patch-edit',
        extra_context=extra)
