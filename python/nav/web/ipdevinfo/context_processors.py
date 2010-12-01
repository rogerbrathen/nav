# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2008 UNINETT AS
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

from django.conf import settings

from nav.web.ipdevinfo.forms import SearchForm

def search_form_processor(request):
    """Add populated search form to context"""
    context_extras = {}
    # FIXME Use request.REQUEST?
    if request.method == 'GET':
        context_extras['search_form'] = SearchForm(request.GET, auto_id=False)
    elif request.method == 'POST':
        context_extras['search_form'] = SearchForm(request.POST, auto_id=False)
    return context_extras