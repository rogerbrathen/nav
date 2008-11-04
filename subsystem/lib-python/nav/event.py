#
# Copyright 2005 Norwegian University of Science and Technology
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
# Authors: Morten Vold <morten.vold@ntnu.no>
#
"""Simple API to interface with NAVs event queue.
"""
import nav.db
from nav.errors import GeneralException
from UserDict import UserDict

class Event(UserDict):
    """Represents a single event on or off the queue.

    Use like a dictionary to manipulate event variables (in eventqvar).
    Otherwise, this is just a dumb storage class (any database activity
    performed by this class is done using the EventQ class as proxy)
    """
    def __init__(self, source=None, target=None, deviceid=None, netboxid=None,
                 subid=None, time=None, eventtypeid=None, state=None,
                 value=None, severity=None):
        UserDict.__init__(self)
        self.eventqid = None

        self.source = source
        self.target = target
        self.deviceid = deviceid
        self.netboxid = netboxid
        self.subid = subid
        self.time = time
        self.eventtypeid = eventtypeid
        self.state = state
        self.value = value
        self.severity = severity

    def __repr__(self):
        attrList = ["%s=%s" % (attr, getattr(self, attr))
                    for attr in ('eventqid', 'source', 'target', 'deviceid',
                                 'netboxid', 'subid', 'time', 'eventtypeid',
                                 'state', 'value', 'severity')
                    if getattr(self, attr)]
        attrList = ", ".join(attrList)
        return "<Event %s / %s>" % (attrList, UserDict.__repr__(self))

    def post(self):
        "Post this event to the eventq"
        return EventQ.postEvent(self)

    def delete(self):
        """Delete this event from the event queue

        This should normally only be done when an event has been consumed and
        processed by its target.
        """
        if not self.eventqid:
            raise EventNotPostedError, "source=%s, target=%s, type=%s" % \
                  (self.source, self.target, self.eventtypeid)
        else:
            result = EventQ.deleteEvent(self.eventqid)
            self.eventqid = None
            return result
    # Alias the delete member function as dispose
    dispose = delete
        

class EventQ:
    "Static class to manipulate the event queue"
    def _getConnection(cls):
        conn = nav.db.getConnection('default', 'manage')
        # Make sure the connection doesn't autocommit: Posting an event
        # consists of several SQL statements that should go into a single
        # transaction.
        conn.autocommit(0)
        conn.set_isolation_level(1)
        return conn
    _getConnection = classmethod(_getConnection)

    def allocateId(cls):
        sql = "SELECT NEXTVAL('eventq_eventqid_seq')"
        conn = cls._getConnection()
        cursor = conn.cursor()
        cursor.execute(sql)
        if cursor.rowcount > 0:
            return cursor.fetchone()[0]
        else:
            raise EventIdAllocationError
    allocateId = classmethod(allocateId)
        
    def postEvent(cls, event):
        if event.eventqid:
            raise EventAlreadyPostedError, event.eventqid

        # First post the relevant fields to eventq
        fields = []
        values = []
        for attr in ('source', 'target', 'deviceid', 'netboxid', 'subid',
                     'time', 'eventtypeid', 'state', 'value', 'severity'):
            if hasattr(event, attr) and getattr(event, attr):
                fields.append(attr)
                values.append(getattr(event, attr))
        if len(fields) == 0:
            raise EventIncompleteError
        fieldString = ','.join(fields)
        placeHolders = ', %s' * len(values)
        eventSQL = "INSERT INTO eventq (eventqid, " + fieldString + ") " + \
                   "VALUES (%s" + placeHolders + ")"
        eventqid = cls.allocateId()
        conn = cls._getConnection()
        cursor = conn.cursor()
        cursor.execute(eventSQL, (eventqid,) + tuple(values))

        # Prepare an SQL statement to post the variables, if any
        if len(event) > 0:
            varSQL = "INSERT INTO eventqvar (eventqid, var, val)" + \
                     "VALUES (%s, %s, %s)"
            values = [(eventqid,) + i for i in event.items()]
            cursor.executemany(varSQL, values)

        # If we got this far, commit the transaction and update the event
        # object with the allocated id

        conn.commit()
        event.eventqid = eventqid
        return cursor.statusmessage
    postEvent = classmethod(postEvent)

    def consumeEvents(cls, target):
        """Consume and return a list of Event objects queued for this target.

        Events that are processed should be deleted from the queue afterwards.
        """
        eventSQL = """SELECT eventqid, source, target, deviceid, netboxid,
                             subid, time, eventtypeid, state, value, severity
                      FROM eventq
                      WHERE target = %s"""
        conn = cls._getConnection()
        conn.commit()
        cursor = conn.cursor()

        def loadVars(event):
            varSQL = "SELECT var, val FROM eventqvar WHERE eventqid=%s"
            curs = conn.cursor()
            curs.execute(varSQL, (event.eventqid,))
            if curs.rowcount > 0:
                for var, val in curs.fetchmany():
                    event[var] = val
        
        events = []
        cursor.execute(eventSQL, (target,))
        if cursor.rowcount > 0:
            for eventRow in cursor.fetchall():
                event = Event()
                (event.eventqid, event.source, event.target, event.deviceid,
                 event.netboxid, event.subid, event.time, event.eventtypeid,
                 event.state, event.value, event.severity) = eventRow
                loadVars(event)
                events.append(event)
        return events
    consumeEvents = classmethod(consumeEvents)
    
    def deleteEvent(cls, eventqid):
        """Delete the event with the specified id from the queue.

        This should normally only be done when an event has been consumed and
        processed by its target.
        """
        sql = "DELETE FROM eventq WHERE eventqid = %s"
        conn = cls._getConnection()
        cursor = conn.cursor()
        cursor.execute(sql, (eventqid,))
        conn.commit()
        return cursor.statusmessage
    deleteEvent = classmethod(deleteEvent)
    
class EventIdAllocationError(GeneralException):
    "Error allocating a new event ID from the queue"
    pass

class EventAlreadyPostedError(GeneralException):
    "Event was already posted"
    pass

class EventIncompleteError(GeneralException):
    "Incomplete event cannot be posted"
    pass

class EventNotPostedError(GeneralException):
    "Cannot perform this operation on an unposted event"
    pass