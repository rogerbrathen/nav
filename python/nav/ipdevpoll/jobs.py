#
# Copyright (C) 2009, 2010 UNINETT AS
#
# This file is part of Network Administration Visualized (NAV).
#
# NAV is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.  You should have received a copy of the GNU General Public
# License along with NAV. If not, see <http://www.gnu.org/licenses/>.
#
"""Job handling."""
import time
import datetime
import pprint
import logging

from twisted.internet import defer, threads
from twistedsnmp import snmpprotocol, agentproxy

from nav.util import round_robin
from nav import toposort

from nav import ipdevpoll
import storage
import shadows
from plugins import plugin_registry
import utils

logger = logging.getLogger(__name__)
ports = round_robin([snmpprotocol.port() for i in range(10)])

class AbortedJobError(Exception):
    """Signals an aborted collection job."""
    def __init__(self, msg, cause=None):
        Exception.__init__(self, msg, cause)
        self.cause = cause


class JobHandler(object):

    """Handles a single polling job against a single netbox.

    An instance of this class performs a polling job, as described by
    a job specification in the config file, for a single netbox.  It
    will handle the dispatch of polling plugins, and contain state
    information for the job.

    """

    def __init__(self, name, netbox, plugins=None):
        self.name = name
        self.netbox = netbox
        self.cancelled = False

        instance_name = (self.name, "(%s)" % netbox.sysname)
        instance_queue_name = ("queue",) + instance_name
        self.logger = \
            ipdevpoll.get_instance_logger(self, ".".join(instance_name))
        self.queue_logger = \
            ipdevpoll.get_instance_logger(self, ".".join(instance_queue_name))

        self.plugins = plugins or []
        self.logger.debug("Job %r initialized with plugins: %r",
                          self.name, self.plugins)
        self.containers = storage.ContainerRepository()
        self.storage_queue = []

        # Initialize netbox in container
        nb = self.container_factory(shadows.Netbox, key=None)
        nb.id = netbox.id

        port = ports.next()

        self.agent = agentproxy.AgentProxy(
            self.netbox.ip, 161,
            community = self.netbox.read_only,
            snmpVersion = 'v%s' % self.netbox.snmp_version,
            protocol = port.protocol,
        )
        self.logger.debug("AgentProxy created for %s: %s",
                          self.netbox.sysname, self.agent)


    def find_plugins(self):
        """Populate the internal plugin list with plugin class instances."""

        plugins = []

        for plugin_name in self.plugins:
            if plugin_name not in plugin_registry:
                self.logger.error("A non-existant plugin %r is configured "
                                  "for job %r", plugin_name, self.name)
                continue
            plugin_class = plugin_registry[plugin_name]

            # Check if plugin wants to handle the netbox at all
            if plugin_class.can_handle(self.netbox):
                plugin = plugin_class(self.netbox, agent=self.agent,
                                      containers=self.containers)
                plugins.append(plugin)
            else:
                self.logger.debug("Plugin %s wouldn't handle %s",
                                  plugin_name, self.netbox.sysname)

        if not plugins:
            self.logger.debug("No plugins for this job")
            return

        self.logger.debug("Plugins to call: %s",
                          ",".join([p.name() for p in plugins]))

        return plugins

    def _iterate_plugins(self, plugins):
        """Iterates plugins."""
        plugins = iter(plugins)

        def log_plugin_failure(failure, plugin_instance):
            if failure.check(defer.TimeoutError):
                self.logger.error("Plugin %s reported a timeout",
                                  plugin_instance)
            else:
                self.logger.error("Plugin %s reported an unhandled failure:"
                                  "\n%s",
                                  plugin_instance, failure.getTraceback())
            return failure

        def next_plugin(result=None):
            if self.cancelled:
                return
            try:
                plugin_instance = plugins.next()
            except StopIteration:
                return result

            self.logger.debug("Now calling plugin: %s", plugin_instance)
            self._start_plugin_timer(plugin_instance)

            df = plugin_instance.handle()
            df.addErrback(self._stop_plugin_timer)
            df.addErrback(log_plugin_failure, plugin_instance)
            df.addCallback(self._stop_plugin_timer)
            df.addCallback(next_plugin)
            return df

        return next_plugin()

    def run(self):
        """Starts a polling job for netbox and returns a Deferred."""
        plugins = self.find_plugins()
        self._reset_timers()
        if not plugins:
            return defer.succeed(None)

        self.logger.info("Starting job %r for %s",
                         self.name, self.netbox.sysname)

        def wrap_up_job(result):
            self.logger.info("Job %s for %s done.", self.name,
                             self.netbox.sysname)
            self._log_timings()
            return result

        def plugin_failure(failure):
            self._log_timings()
            raise AbortedJobError("Job aborted due to plugin failure",
                                  cause=failure.value)

        def save_failure(failure):
            self.logger.error("Save stage failed with unhandled error:\n%s",
                              failure.getTraceback())
            self._log_timings()
            raise AbortedJobError("Job aborted due to save failure",
                                  cause=failure.value)

        def log_abort(failure):
            if failure.check(AbortedJobError):
                self.logger.error("Job %r for %s aborted.",
                                  self.name, self.netbox.sysname)
            return failure

        def save(result):
            if self.cancelled:
                return wrap_up_job(result)

            df = self.save_container()
            df.addErrback(save_failure)
            df.addCallback(wrap_up_job)
            return df

        # The action begins here
        df = self._iterate_plugins(plugins)
        df.addErrback(plugin_failure)
        df.addCallback(save)
        df.addErrback(log_abort)
        return df

    def cancel(self):
        """Cancels a running job.

        Job stops at the earliest convenience.
        """
        self.cancelled = True
        self.logger.warning("Cancelling running job")

    def _reset_timers(self):
        self._start_time = datetime.datetime.now()
        self._plugin_times = []

    def _start_plugin_timer(self, plugin):
        timings = [plugin.__class__.__name__, datetime.datetime.now()]
        self._plugin_times.append(timings)

    def _stop_plugin_timer(self, result=None):
        timings = self._plugin_times[-1]
        timings.append(datetime.datetime.now())
        return result

    def _log_timings(self):
        stop_time = datetime.datetime.now()
        job_total = stop_time-self._start_time

        times = [(plugin, stop-start)
                 for (plugin, start, stop) in self._plugin_times]
        plugin_total = sum((i[1] for i in times), datetime.timedelta(0))

        times.append(("Plugin total", plugin_total))
        times.append(("Job total", job_total))
        times.append(("Job overhead", job_total - plugin_total))

        log_text = []
        longest_label = max(len(i[0]) for i in times)
        format = "%%-%ds: %%s" % longest_label

        for plugin, delta in times:
            log_text.append(format % (plugin, delta))

        dashes = "-" * max(len(i) for i in log_text)
        log_text.insert(-3, dashes)
        log_text.insert(-2, dashes)

        log_text.insert(0, "Job %r timings for %s:" %
                        (self.name, self.netbox.sysname))

        log = ipdevpoll.get_instance_logger(self, "timings")
        log.debug("\n".join(log_text))

    def get_current_runtime(self):
        """Returns time elapsed since the start of the job as a timedelta."""
        return datetime.datetime.now() - self._start_time

    def save_container(self):
        """
        Parses the container and finds a sane storage order. We do this
        so we get ForeignKeys stored before the objects that are using them
        are stored.
        """
        @utils.autocommit
        @utils.cleanup_django_debug_after
        def complete_save_cycle():
            # Prepare all shadow objects for storage.
            self.prepare_containers_for_save()
            # Traverse all the objects in the storage container and generate
            # the storage queue
            self.populate_storage_queue()
            # Actually save to the database
            result = self.perform_save()
            self.log_timed_result(result, "Storing to database complete")
            # Do cleanup for the known container classes.
            self.cleanup_containers_after_save()

        df = threads.deferToThread(complete_save_cycle)
        return df

    def prepare_containers_for_save(self):
        """Execute the prepare_for_save-method on all shadow classes with known
        instances.

        """
        for cls in self.containers.keys():
            cls.prepare_for_save(self.containers)

    def cleanup_containers_after_save(self):
        """Execute the cleanup_after_save-method on all shadow classes with
        known instances.

        """
        self.logger.debug("Running cleanup routines for %d classes (%r)",
                          len(self.containers), self.containers.keys())
        try:
            for cls in self.containers.keys():
                cls.cleanup_after_save(self.containers)
        except Exception:
            self.logger.exception("Caught exception during cleanup. "
                                  "Last class = %s",
                                  cls.__name__)
            import django.db
            if django.db.connection.queries:
                self.logger.error("The last query was: %s",
                                  django.db.connection.queries[-1])
            raise

    def log_timed_result(self, res, msg):
        self.logger.debug(msg + " (%0.3f ms)" % res)

    def perform_save(self):
        start_time = time.time()
        obj_model = None
        try:
            self.storage_queue.reverse()
            if self.queue_logger.getEffectiveLevel() <= logging.DEBUG:
                self.queue_logger.debug(pprint.pformat(
                        [(id(o), o) for o in self.storage_queue]))

            while self.storage_queue:
                obj = self.storage_queue.pop()
                obj_model = obj.convert_to_model(self.containers)
                if obj.delete and obj_model:
                    obj_model.delete()
                else:
                    try:
                        # Skip if object exists in database and no fields
                        # are touched
                        if obj.getattr(obj, obj.get_primary_key().name) \
                            and not obj.get_touched():
                            continue
                    except AttributeError:
                        pass
                    if obj_model:
                        obj_model.save()
                        # In case we saved a new object, store a reference to
                        # the newly allocated primary key in the shadow object.
                        # This is to ensure that other shadows referring to
                        # this shadow will know about this change.
                        if not obj.get_primary_key():
                            obj.set_primary_key(obj_model.pk)
                        obj._touched.clear()

            end_time = time.time()
            total_time = (end_time - start_time) * 1000.0

            if self.queue_logger.getEffectiveLevel() <= logging.DEBUG:
                self.queue_logger.debug("containers after save: %s",
                                        pprint.pformat(self.containers))

            return total_time
        except Exception:
            self.logger.exception("Caught exception during save. "
                                  "Last object = %s. Last model: %s",
                                  obj, obj_model)
            import django.db
            if django.db.connection.queries:
                self.logger.error("The last query was: %s",
                                  django.db.connection.queries[-1])
            raise

    def populate_storage_queue(self):
        """Naive population of the storage queue.

        Assuming there are no inter-dependencies between instances of a single
        shadow class, the only relevant ordering is the one between the
        container types themselves.  This method will only order instances
        according to the dependency (topological) order of their classes.

        """
        for shadow_class in sorted_shadow_classes:
            if shadow_class in self.containers:
                shadows = self.containers[shadow_class].values()
                self.storage_queue.extend(shadows)

    def container_factory(self, container_class, key):
        """Container factory function"""
        return self.containers.factory(key, container_class)


def get_shadow_sort_order():
    """Return a topologically sorted list of shadow classes."""
    def get_dependencies(shadow_class):
        return shadow_class.get_dependencies()

    shadow_classes = storage.shadowed_classes.values()
    graph = toposort.build_graph(shadow_classes, get_dependencies)
    sorted_classes = toposort.topological_sort(graph)
    return sorted_classes


# As this module is loaded, we want to build a list of shadow classes
# sorted in topological order.  This only needs to be done once.  The
# list is used to find the correct order in which to store shadow
# objects at the end of a job.
sorted_shadow_classes = get_shadow_sort_order()