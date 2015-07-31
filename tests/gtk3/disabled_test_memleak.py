import logging
import unittest

from mock import Mock

from tests.utils import (
    do_events_with_sleep,
    get_test_db,
    setup_test_env,
)
setup_test_env()


from softwarecenter.backend.installbackend import get_install_backend
from softwarecenter.db.application import Application
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.ui.gtk3.app import SoftwareCenterAppGtk3
from softwarecenter.utils import (
    TraceActiveObjectTypes,
    TraceMemoryUsage,
    )

from tests.gtk3.windows import (
    get_test_window_appdetails,
    get_test_window_catview,
    )


class MemleakTestCase(unittest.TestCase):
    """The test suite for the recommendations ."""

    ITERATIONS = 2

    def test_memleak_app_recommendations(self):
        cache = get_pkg_info()
        cache.open(blocking=True)
        win = get_test_window_appdetails()
        view = win.get_data("view")
        app = Application("", "gedit")
        # get baseline
        view.show_app(app)
        do_events_with_sleep()
        with TraceMemoryUsage("AppdetailsView.show_app()"):
            with TraceActiveObjectTypes("view.recommended_for_app.set_pkgname"):
                for i in range(self.ITERATIONS):
                    view.recommended_for_app_panel.set_pkgname("gedit")
                    cache.open()
                    do_events_with_sleep()

    def test_memleak_appdetails(self):
        cache = get_pkg_info()
        cache.open(blocking=True)
        win = get_test_window_appdetails()
        view = win.get_data("view")
        app = Application("", "gedit")
        # get baseline
        view.show_app(app)
        do_events_with_sleep()
        with TraceMemoryUsage("AppdetailsView.show_app()"):
            for i in range(self.ITERATIONS):
                view.show_app(app, force=True)
                # this causes a huge memleak of ~35mb/run
                cache.open()
                do_events_with_sleep()

    def test_memleak_catview(self):
        db = get_test_db()
        win = get_test_window_catview(db)
        lobby = win.get_data("lobby")
        # get baseline
        do_events_with_sleep()
        with TraceMemoryUsage("LobbyView.on_db_reopen()"):
            for i in range(self.ITERATIONS):
                lobby._on_db_reopen(db)
                do_events_with_sleep()

    def test_memleak_subcatview(self):
        db = get_test_db()
        win = get_test_window_catview(db)
        lobby =  win.get_data("lobby")
        cat = [cat for cat in lobby.categories if cat.name == "Internet"][0]
        subcat = win.get_data("subcat")
        # get baseline
        subcat.set_subcategory(cat)
        do_events_with_sleep()
        with TraceMemoryUsage("SubcategoryView.set_subcategory()"):
            for i in range(self.ITERATIONS):
                subcat._set_subcategory(cat, 0)
                do_events_with_sleep()

    def test_memleak_app(self):
        options = Mock()
        options.display_navlog = False
        args = []
        # ensure the cache is fully ready before taking the baseline
        cache = get_pkg_info()
        cache.open(blocking=True)
        app = SoftwareCenterAppGtk3(options, args)
        app.window_main.show_all()
        do_events_with_sleep()
        with TraceMemoryUsage("app._on_transaction_finished"):
            for i in range(self.ITERATIONS):
                app._on_transaction_finished(None, None)
                cache.open()
                do_events_with_sleep()

    def test_memleak_pkginfo_open(self):
        cache = get_pkg_info()
        cache.open()
        do_events_with_sleep()
        with TraceMemoryUsage("PackageInfo.open()"):
            for i in range(self.ITERATIONS):
                cache.open()
                do_events_with_sleep()

    def test_memleak_backend_finished(self):
        backend = get_install_backend()
        backend.emit("transaction-finished", Mock())
        do_events_with_sleep()
        with TraceMemoryUsage("backend.emit('transaction-finished')"):
            for i in range(self.ITERATIONS):
                backend.emit("transaction-finished", Mock())
                do_events_with_sleep()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARN)
    unittest.main()
