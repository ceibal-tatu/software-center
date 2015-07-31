import unittest

from mock import (
    patch,
    Mock,
    )

from tests.utils import (
    setup_test_env,
    get_test_db,
)
setup_test_env()
from softwarecenter.db.application import (
    Application,
    AppDetails,
    )


# FIXME: move application/appdetails tests from test_database.py
#        into this file for better structure
class ApplicationTestCase(unittest.TestCase):

    def test_application_name(self):
        app1 = Application(appname="The AppName", pkgname="pkgapp")
        self.assertEqual(app1.name, "The AppName")
        app2 = Application(appname="", pkgname="pkgapp2")
        self.assertEqual(app2.name, "pkgapp2")

    def test_appdetails(self):
        app = Application("Foo app", "dpkg")
        db = get_test_db()
        appdetails = app.get_details(db)
        # patching properties is a bit cumbersome
        with patch.object(AppDetails, "raw_price") as mock_price:
            with patch.object(AppDetails, "currency") as mock_currency:
                mock_price.__get__ = Mock(return_value="2.99")
                mock_currency.__get__ = Mock(return_value="USD")
                self.assertEqual("USD 2.99", appdetails.price)


if __name__ == "__main__":
    unittest.main()
