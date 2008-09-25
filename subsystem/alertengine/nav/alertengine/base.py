#! /usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2008 UNINETT AS
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
# Authors: Thomas Adamcik <thomas.adamcik@uninett.no>

"""
Package placeholder. If you remove it, the package won't work.
"""

__copyright__ = "Copyright 2008 UNINETT AS"
__license__ = "GPL"
__author__ = "Thomas Adamcik (thomas.adamcik@uninett.no)"
__id__ = "$Id$"

import logging
from datetime import datetime

from django.db import transaction

from nav.models.profiles import Account, AccountAlertQueue, FilterGroupContent, AlertSubscription, AlertAddress, FilterGroup
from nav.models.event import AlertQueue

logger = logging.getLogger('nav.alertengine')

@transaction.commit_on_success
def check_alerts(debug=False):
    '''Handles all new and user queued alerts'''

    # We use transaction autocommit so that the changes we make only propogate
    # if the entire loop finishes.

    # Alot of this functionality could have been backed into the models for the
    # corresponding objects, however it seems better to keep all of this logic
    # in one place. Despite this some the simpler logic has been offloaded to
    # the models themselves.

    # Try to avoid spamming people when running tests
    if debug:
        AlertAddress.DEBUG_MODE = True

    now = datetime.now()
    accounts = []
    num_sent_alerts = 0
    num_failed_sends = 0

    # Get all alerts that aren't in alert queue due to subscription
    new_alerts = AlertQueue.objects.filter(accountalertqueue__isnull=True)

    logger.info('Starting alertengine run, checking %d new alerts' % len(new_alerts))

    if len(new_alerts):
        # Build datastructure that contains accounts and corresponding
        # filtergroupcontent_set so that we don't redo db queries to much
        for account in Account.objects.filter(alertpreference__active_profile__isnull=False):
                time_period = account.get_active_profile().get_active_timeperiod()

                if not time_period:
                    continue

                current_alertsubscriptions = time_period.alertsubscription_set.all()

                tmp = []
                for alertsubscription in current_alertsubscriptions:
                    tmp.append( (alertsubscription, alertsubscription.filter_group.filtergroupcontent_set.all()) )

                if tmp:
                    permissions = []
                    for filtergroup in FilterGroup.objects.filter(group_permissions__accounts__in=[account]):
                        permissions.append(filtergroup.filtergroupcontent_set.all())

                    accounts.append( (account, tmp, permissions) )

        # Check all acounts against all their active subscriptions
        for account, alertsubscriptions, permissions in accounts:
            logger.debug("Cheking alerts for account '%s'" % account)

            for alert in new_alerts:
                for alertsubscription, filtergroupcontents in alertsubscriptions:
                    # Check if alert matches, and if user has permission
                    if check_alert_against_filtergroupcontents(alert, filtergroupcontents):
                        sent = False
                        for permission in permissions:
                            if check_alert_against_filtergroupcontents(alert, permission, type='permission check'):

                                # Allways queue alert so that we have it incase of
                                # failed send.
                                AccountAlertQueue.objects.get_or_create(account=account, alert=alert, subscription=alertsubscription)

                                sent = True
                                break;

                        if not sent:
                            logger.warn('alert %d not: sent to %s due to lacking permissions' % (alert.id, account))
                    else:
                        logger.info('alert %d: did not match the alertsubscription %d of user %s' % (alert.id, alertsubscription.id, account))

    # Get all queued alerts.
    queued_alerts = AccountAlertQueue.objects.all()

    logger.info('Checking %d queued alerts' % len(queued_alerts))

    # We want to keep track of wether or not any weekly or daily messages have
    # been sent so that we can update the state of the users
    # last_sent_daily/weekly
    sent_weekly = []
    sent_daily = []

    if len(queued_alerts):
        for queued_alert in queued_alerts:
            try:
                subscription = queued_alert.subscription
            except AlertSubscription.DoesNotExist:
                logger.error('account queued alert %d does not have subscription, probably a legacy table row' % queued_alert.id)
                continue

            logger.info('stored alert %d: Checking if we should send alert to %s due to %s subscription' % (queued_alert.alert_id, queued_alert.account, subscription.get_type_display()) )

            if subscription.type == AlertSubscription.NOW:
                if queued_alert.send():
                    num_sent_alerts += 1
                else:
                    num_failed_sends += 1

            elif subscription.type == AlertSubscription.DAILY:
                daily_time = subscription.time_period.profile.daily_dispatch_time
                last_sent  = subscription.time_period.profile.alertpreference.last_sent_day or datetime.min

                # If the last sent date is less than the current date, and we are
                # past the daily time and the alert was added to the queue before
                # this time

                logger.debug('Tests: last sent %s, daily time %s, insertion time %s' % (last_sent.date() < now.date(), daily_time < now.time(), queued_alert.insertion_time.time() < daily_time))

                if last_sent.date() < now.date() and daily_time < now.time() and queued_alert.insertion_time.time() < daily_time:
                    if queued_alert.send():
                        num_sent_alerts += 1
                        sent_daily.append(queued_alert.account)
                    else:
                        num_failed_sends += 1

            elif subscription.type == AlertSubscription.WEEKLY:
                weekly_time = subscription.time_period.profile.weekly_dispatch_time
                weekly_day = subscription.time_period.profile.weekly_dispatch_day
                last_sent  = subscription.time_period.profile.alertpreference.last_sent_week or datetime.min

                # Check that we are at the correct weekday, and that the last sent
                # time is less than today, and that alert was inserted before the
                # weekly time.
                logger.debug('Tests: weekday %s, last sent %s, weekly time %s, insertion time %s' % (weekly_day == now.weekday(), last_sent.date() < now.date(), weekly_time < now.time(), queued_alert.insertion_time.time() < weekly_time))

                if weekly_day == now.weekday() and last_sent.date() < now.date() and weekly_time < now.time() and queued_alert.insertion_time.time() < weekly_time:
                    if queued_alert.send():
                        num_sent_alerts += 1
                        sent_weekly.append(queued_alert.account)
                    else:
                        num_failed_sends += 1

            elif subscription.type == AlertSubscription.NEXT:
                active_profile = subscription.alert_address.account.get_active_profile()

                if not active_profile:
                    # No active profile do nothing (FIXME ask if this is how we
                    # want things)
                    pass
                else:
                    current_time_period = active_profile.get_active_timeperiod()

                    insertion_time = queued_alert.insertion_time
                    queued_alert_time_period = subscription.time_period

                    # Send if we are in a different time period than the one that the
                    # message was inserted with.
                    logger.debug('Tests: different time period %s' % (queued_alert_time_period.id != current_time_period.id))

                    # Check if the message was inserted on a previous day and that the
                    # start period of the time period it was inserted in has passed.
                    # This check should catch the corner case where a user only has one
                    # timeperiod that loops.

                    if datetime.now().isoweekday() in [6,7]:
                        valid_during = [TimePeriod.ALL_WEEK,TimePeriod.WEEKENDS]
                    else:
                        valid_during = [TimePeriod.ALL_WEEK,TimePeriod.WEEKDAYS]

                    only_one_time_period = active_profile.timperiod_set.filter(valid_during__in=valid_during).count() == 1

                    logger.debug('Tests: only one time period %s, insertion time %s' % (only_one_time_period, insertion_time.time() < queued_alert_time_period.start))

                    if subscription.time_period.id != current_time_period.id:
                        if queued_alert.send():
                            num_sent_alerts += 1
                        else:
                            num_failed_sends += 1

                    elif only_one_time_period and insertion_time.time() < queued_alert_time_period.start:
                        if queued_alert.send():
                            num_sent_alerts += 1
                        else:
                            num_failed_sends += 1

            else:
                logger.error('account %s has an invalid subscription type in subscription %d' % (subscription.account, subscription.id))

    # Update the when the user last recieved daily or weekly alerts.
    if sent_daily:
        for account in sent_daily:
            account.alertpreference.last_sent_day = now
    if sent_weekly:
        for account in sent_weekly:
            account.alertpreference.last_sent_weekly = now

    alerts_in_account_queues = [a.alert_id for a in AccountAlertQueue.objects.all()]

    # Delete handeled alerts that are not in an AccountAlertQueue
    if new_alerts:
        # Get id's of alerts that have been queued for users.

        if not debug:
            to_delete = AlertQueue.objects.filter(id__in=[a.id for a in new_alerts]).exclude(id__in=alerts_in_account_queues)
            logger.info('Deleted following alerts from alert queue: %s' % ([a.id for a in to_delete]))
            to_delete.delete()
        else:
            logger.info('In testing mode: would have deleted following alerts from alert queue: %s' % ([a.id for a in new_alerts]))

    logger.info('Finished alertengine run, sent %d alerts, %d user queued alerts left in queue' % (num_sent_alerts, len(alerts_in_account_queues)))

    if num_failed_sends:
        logger.warning('Send %d alerts failed, trying again on next run.' % (num_failed_sends))


def check_alert_against_filtergroupcontents(alert, filtergroupcontents, type='match check'):
    '''Checks a given alert against an array of filtergroupcontents'''

    # Allways assume that the match will fail
    matches = False

    for content in filtergroupcontents:
        original_macthes = matches

        # If we have not matched the message see if we can match it
        if not matches and content.include:
            matches = content.filter.check(alert) == content.positive

            if matches:
                logger.debug('alert %d: got included by filter %d in %s' % (alert.id, content.filter.id, type))

        # If the alert has been matched try excluding it
        elif matches and not content.include:
            matches = content.filter.check(alert) != content.positive

            # Log that we excluded the alert
            if not matches:
                logger.debug('alert %d got: excluded by filter %d in %s' % (alert.id, content.filter.id, type))

        if original_macthes == matches:
            logger.debug('alert %d: unaffected by filter %d in %s' % (alert.id, content.filter.id, type))
    return matches