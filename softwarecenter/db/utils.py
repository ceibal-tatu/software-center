# Copyright (C) 2011-2013 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import logging
import os

from gi import version_info as gi_version
from gi.repository import GObject, GLib

import softwarecenter.paths

LOG = logging.getLogger(__name__)


def run_software_center_agent(db):
    """ Helper that triggers the update-software-center-agent helper
        and will also reopen the database on success
    """
    def _on_update_software_center_agent_finished(pid, condition):
        LOG.info("software-center-agent finished with status %i" %
            os.WEXITSTATUS(condition))
        if os.WEXITSTATUS(condition) == 0:
            db.reopen()
    # run the update
    sc_agent_update = os.path.join(
        softwarecenter.paths.datadir, "update-software-center-agent")
    (pid, stdin, stdout, stderr) = GLib.spawn_async(
        [sc_agent_update, "--datadir", softwarecenter.paths.datadir],
        flags=GObject.SPAWN_DO_NOT_REAP_CHILD)
    # python-gobject >= 3.7.3 has changed some API in incompatible
    # ways, so we need to check the version for which one to use.
    if gi_version < (3, 7, 3):
        GLib.child_watch_add(
            pid, _on_update_software_center_agent_finished)
    else:
        GLib.child_watch_add(
            GLib.PRIORITY_DEFAULT,
            pid, _on_update_software_center_agent_finished)


def get_installed_apps_list(db):
    """ return a list of installed applications """
    apps = set()
    for doc in db:
        if db.get_appname(doc):
            pkgname = db.get_pkgname(doc)
            if (pkgname in db._aptcache and
                    db._aptcache[pkgname].is_installed):
                apps.add(db.get_application(doc))
    return apps


def get_installed_package_list():
    """ return a set of all of the currently installed packages """
    from softwarecenter.db.pkginfo import get_pkg_info
    installed_pkgs = set()
    cache = get_pkg_info()
    for pkg in cache:
        if pkg.is_installed:
            installed_pkgs.add(pkg.name)
    return installed_pkgs
