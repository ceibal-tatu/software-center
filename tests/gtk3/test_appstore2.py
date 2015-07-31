import unittest
import xapian

from mock import Mock, patch

from tests.utils import (
    do_events,
    get_test_db,
    get_test_gtk3_icon_cache,
    get_test_pkg_info,
    setup_test_env,
)
setup_test_env()

from softwarecenter.ui.gtk3.models.appstore2 import AppListStore
from softwarecenter.db.enquire import AppEnquire


class AppStoreTestCase(unittest.TestCase):
    """ test the appstore """

    @classmethod
    def setUpClass(cls):
        cls.cache = get_test_pkg_info()
        cls.icons = get_test_gtk3_icon_cache()
        cls.db = get_test_db()

    def test_lp872760(self):
        def monkey_(s):
            translations = {
                "Painting &amp; Editing" : "translation for Painting &amp; "
                                           "Editing",
            }
            return translations.get(s, s)
        with patch("softwarecenter.ui.gtk3.models.appstore2._", new=monkey_):
            model = AppListStore(self.db, self.cache, self.icons)
            untranslated = "Painting & Editing"
            translated = model._category_translate(untranslated)
            self.assertNotEqual(untranslated, translated)

    def test_app_store(self):
        # get a enquire object
        enquirer = AppEnquire(self.cache, self.db)
        enquirer.set_query(xapian.Query(""))

        # get a AppListStore and run functions on it
        model = AppListStore(self.db, self.cache, self.icons)

        # test if set from matches works
        self.assertEqual(len(model), 0)
        model.set_from_matches(enquirer.matches)
        self.assertTrue(len(model) > 0)
        # ensure the first row has a xapian doc type
        self.assertEqual(type(model[0][0]), xapian.Document)
        # lazy loading of the docs
        self.assertEqual(model[100][0], None)

        # test the load range stuff
        model.load_range(indices=[100], step=15)
        self.assertEqual(type(model[100][0]), xapian.Document)

        # ensure buffer_icons works and loads stuff into the cache
        model.buffer_icons()
        self.assertEqual(len(model.icon_cache), 0)
        do_events()
        self.assertTrue(len(model.icon_cache) > 0)

        # ensure clear works
        model.clear()
        self.assertEqual(model.current_matches, None)

    def test_lp971776(self):
        """ ensure that refresh is not called for invalid image files """
        model = AppListStore(self.db, self.cache, self.icons)
        model.emit = Mock()
        model._on_image_download_complete(None, "xxx", "software-center")
        self.assertFalse(model.emit.called)

if __name__ == "__main__":
    unittest.main()
