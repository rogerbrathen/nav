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
# Authors: Magnus Motzfeldt Eide <magnus.eide@uninett.no>
#

"""Utility methods for Alert Profiles"""

__copyright__ = "Copyright 2008 UNINETT AS"
__license__ = "GPL"
__author__ = "Magnus Motzfeldt Eide (magnus.eide@uninett.no)"
__id__ = "$Id$"

import dircache
# md5 is deprecated in python 2.5.
# If one wish to bump python requirement to 2.5, one can s/md5 as //
import md5 as hashlib
import os

from django.db import transaction

import nav.config
import nav.path
from nav.django.utils import get_account, is_admin
from nav.models.profiles import Filter, FilterGroup, FilterGroupContent, \
    Account, AlertSubscription, TimePeriod

ADMINGROUP = 1
CONFIGDIR = 'alertprofiles/'
TIME_PERIOD_TEMPLATES_DIR = CONFIGDIR + 'periodtemplates/'

def account_owns_filters(account, *filters):
    """Checks if account have access to edit/remove filters and/or filter groups."""

    # Check if user is admin
    groups = account.accountgroup_set.filter(pk=ADMINGROUP).count()
    if groups > 0:
        # User is admin
        return True
    else:
        # User is not admin, check each filter
        for filter in filters:
            try:
                if isinstance(filter, Filter) or isinstance(filter, FilterGroup):
                    owner = filter.owner
                else:
                    owner = filter.get().owner
            except Account.DoesNotExist:
                # This is a public filter, and we already know that this user
                # is not an admin
                return False
            else:
                if owner == account:
                    return True
                else:
                    return False

def resolve_account_admin_and_owner(request):
    """Primarily used before saving filters and filter groups.
    Gets account, checks if user is admin, and sets owner to a appropriate
    value.
    """
    account = get_account(request)
    admin = is_admin(account)

    owner = Account()
    if request.POST.get('owner') or not admin:
        owner = account

    return (account, admin, owner)

@transaction.commit_on_success
def order_filter_group_content(filter_group):
    """Filter group content is ordered by priority where each filters priority
    is the previous filters priority incremented by one, starting at 1. Here we
    loop through all the filters and check if they are ordered that way, and if
    they are not, we order them that way.

    Returns the last filters priority (0 if there are no filters)
    """
    filter_group_content = FilterGroupContent.objects.filter(
            filter_group=filter_group.id
        ).order_by('priority')

    if len(filter_group_content) > 0:
        prev_priority = 0
        for f in filter_group_content:
            priority = f.priority
            if priority - prev_priority != 1:
                f.priority = prev_priority + 1
                f.save()
            prev_priority = f.priority

        return prev_priority
    else:
        return 0

def read_time_period_templates():
    templates = {}
    template_dir = os.path.join(nav.path.sysconfdir, TIME_PERIOD_TEMPLATES_DIR)
    template_configs = dircache.listdir(template_dir)

    for template_file in template_configs:
        if '.conf' in template_file:
            file = os.path.join(template_dir, template_file)
            key = hashlib.md5(file).hexdigest()
            config = nav.config.getconfig(file)
            templates[key] = config

    return templates

def alert_subscriptions_table(periods):
    weekday_subscriptions = []
    weekend_subscriptions = []
    shared_class_id = 0

    for p in periods:
        # TimePeriod is a model.
        # We transform it to a dictionary so we can add additinal information
        # to it, such as end_time (which does not really exist, it's just the
        # start time for the next period.
        period = {
            'id': p.id,
            'profile': p.profile,
            'start': p.start,
            'end': None,
            'valid_during': p.get_valid_during_display(),
            'class': None,
        }
        valid_during = p.valid_during
        alert_subscriptions = AlertSubscription.objects.filter(time_period=p)

        # This little snippet magically assigns a class to shared time periods
        # so they appear with the same highlight color.
        if valid_during == TimePeriod.ALL_WEEK:
            period['class'] = 'shared' + unicode(shared_class_id)
            shared_class_id += 1
            if shared_class_id > 7:
                shared_class_id = 0

        # For usability we change 'all days' periods to one weekdays and one
        # weekends period.
        # Because we might add the same period to both weekdays and weekends we
        # must make sure at least one of them is a copy, so changes to one of
        # them don't apply to both.
        if valid_during in (TimePeriod.WEEKDAYS, TimePeriod.ALL_WEEK):
            weekday_subscriptions.append({
                'time_period': period.copy(),
                'alert_subscriptions': alert_subscriptions,
            })
        if valid_during in (TimePeriod.WEEKENDS, TimePeriod.ALL_WEEK):
            weekend_subscriptions.append({
                'time_period': period,
                'alert_subscriptions': alert_subscriptions,
            })

    subscriptions = [
        {'title': 'Weekdays', 'subscriptions': weekday_subscriptions},
        {'title': 'Weekends', 'subscriptions': weekend_subscriptions},
    ]

    # There's not stored any information about a end time in the DB, only start
    # times, so the end time of one period is the start time of the next
    # period.
    for type in subscriptions:
        subscription = type['subscriptions']
        for i, s in enumerate(subscription):
            if i < len(subscription) - 1:
                end_time = subscription[i+1]['time_period']['start']
            else:
                end_time = subscription[0]['time_period']['start']
            s['time_period']['end'] = end_time

    return subscriptions