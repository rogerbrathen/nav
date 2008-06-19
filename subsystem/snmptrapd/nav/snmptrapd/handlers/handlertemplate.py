import logging
import nav.errors
import re
from nav.db import getConnection
from nav.event import Event


# Create logger with modulename here
logger = logging.getLogger('nav.snmptrapd.template')

#__copyright__ = "Copyright 2007 Norwegian University of Science and Technology"
#__license__ = "GPL"
#__author__ = "John-Magne Bredal (john.m.bredal@ntnu.no)"


# If you need to contact database.
global db
db = getConnection('default')


def handleTrap(trap, config=None):
    """
    handleTrap is run by snmptrapd every time it receives a
    trap. Return False to signal trap was discarded, True if trap was
    accepted.
    """

    # Use the trap-object to access trap-variables and do stuff.
    if trap.genericType in ['LINKUP','LINKDOWN']:
        logger.debug ("This is a linkState trap")

    # config may be fetched like this
    variable = config.get('template','variable')


    if doSomething:

        # Events are posted like this. For more information about the
        # event-module see "pydoc nav.event"

        # Create eventobject.
        e = Event(source=source, target=target, netboxid=netboxid, deviceid=deviceid,
                  subid=subid, eventtypeid=eventtypeid, state=state)

        # These go to eventqvar.
        e['alerttype'] = 'linkUp'
        e['module'] = module

        try:
            e.post()
        except nav.errors.GeneralException, why:
            logger.error(why)
            return False

        # Return True if trap was processed.
        return True
    else:
        # Return False if this trap was not interesting.
        return False


# This function is a nice to run to make sure the event and alerttypes
# exist in the database if you post events for alerting.

def verifyEventtype ():
    """
    Safe way of verifying that the event- and alarmtypes exist in the
    database. Should be run when module is imported.
    """

    c = db.cursor()

    # NB: Remember to replace the values with the one you need. 

    sql = """
    INSERT INTO eventtype (
    SELECT 'linkState','Tells us whether a link is up or down.','y' WHERE NOT EXISTS (
    SELECT * FROM eventtype WHERE eventtypeid = 'linkState'));

    INSERT INTO alertType (
    SELECT nextval('alerttype_alerttypeid_seq'), 'linkState', 'linkUp', 'Link active' WHERE NOT EXISTS (
    SELECT * FROM alerttype WHERE alerttype = 'linkUp'));

    INSERT INTO alertType (
    SELECT nextval('alerttype_alerttypeid_seq'), 'linkState', 'linkDown', 'Link inactive' WHERE NOT EXISTS (
    SELECT * FROM alerttype WHERE alerttype = 'linkDown'));
    """

    queries = sql.split(';')
    for q in queries:
        if len(q.rstrip()) > 0:
            c.execute(q)

    db.commit()
        

# Run verifyeventtype at import
verifyEventtype()