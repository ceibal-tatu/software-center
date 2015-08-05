
from gi.repository import GLib
import sys
import os
import apt
import xapian
import softwarecenter.plugin
import urllib2
import logging

LOG = logging.getLogger(__name__)

from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.db.update import update_from_json_string


class CeibalAppsPlugin(softwarecenter.plugin.Plugin):

    def _update_ceibal_apps(self):
        if not self.app.available_pane.view_initialized:
            # wait for the pane to fully initialize
            return True
        cache = apt.Cache()
        pathname = os.path.join(XAPIAN_BASE_PATH,'xapian')
        try:
            LOG.debug("Ceibal, storing highlights pkgs")
            db = xapian.WritableDatabase(pathname, xapian.DB_CREATE_OR_OVERWRITE)
            p = "http://apt.ceibal.edu.uy/recommendations/list.json"
            data = urllib2.urlopen(p)
            update_from_json_string(db, cache, data.read(), origin=p)
        except xapian.DatabaseLockError:
            LOG.error("Ceibal: Another instance of the update agent already holds "
                     "a write lock on %s" % p)
            return True
        return False

    def init_plugin(self):
        LOG.debug("init_plugin\n")
        if(self._update_ceibal_apps()):
            GLib.timeout_add(100, self._update_ceibal_apps)
