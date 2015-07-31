
from gi.repository import GLib
import sys
import os
import apt
import xapian
import softwarecenter.plugin
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.db.update import update_from_json_string

class CeibalAppsPlugin(softwarecenter.plugin.Plugin):
    """ example plugin that will hide the exhibits banner """

    def _update_ceibal_apps(self):
        if not self.app.available_pane.view_initialized:
            # wait for the pane to fully initialize
            return True
        cache = apt.Cache()
        pathname = os.path.join(XAPIAN_BASE_PATH,'xapian')
        try:
            db = xapian.WritableDatabase(pathname, xapian.DB_CREATE_OR_OVERWRITE)
            p = os.path.join("/home/gustavo/devel/software-center/software-center/tests/data", "app-info-json", "ceibal-apps.json")
            update_from_json_string(db, cache, open(p).read(), origin=p)
        except xapian.DatabaseLockError:
            sys.stderr.write("ceibal: Another instance of the update agent already holds "
                     "a write lock on %s" % pathname)
        return False

    def init_plugin(self):
        sys.stderr.write("init_plugin\n")

        GLib.timeout_add(100, self._update_ceibal_apps)
