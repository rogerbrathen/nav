"""Raw SNMP SMI module dumps.

As dumped by smidump dump using the python format option.

"""
from __future__ import absolute_import
from os.path import dirname, join, basename, isfile, splitext
import glob
import importlib

_submodule_files = (
    glob.glob(join(dirname(__file__), "*.py")) +
    glob.glob(join(dirname(__file__), "*.pyc")) +
    glob.glob(join(dirname(__file__), "*.pyo"))
)

_submodules = list(set(
    splitext(basename(f))[0]
    for f in _submodule_files
    if isfile(f) and not basename(f).startswith('__init__')
))

__all__ = _submodules + ['get_mib_modules', 'get_mib']

_mib_map = {}


def get_mib_modules():
    """Returns a dict mapping MIB module names to the corresponding Python
    module containing its smidumped version.

    """
    if not _mib_map:
        for modname in _submodules:
            module = importlib.import_module('.' + modname, 'nav.smidumps')
            if hasattr(module, 'MIB') and 'moduleName' in module.MIB:
                _mib_map[module.MIB['moduleName']] = module

    return _mib_map


def get_mib(mib_module):
    """Returns the smidumped MIB definition of a named MIB module, if it exists
    in NAV.

    """
    modules = get_mib_modules()
    if mib_module in modules:
        return modules[mib_module].MIB
