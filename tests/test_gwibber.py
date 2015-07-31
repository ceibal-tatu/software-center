import os
import unittest

Gwibber = None
try:
    from gi.repository import Gwibber
except ImportError:
    pass

from tests.utils import (
    setup_test_env,
)
setup_test_env()
from softwarecenter.gwibber_helper import GwibberHelper, GwibberHelperMock

NOT_DEFINED = object()


@unittest.skipIf(Gwibber is None,
    "Please install the gwibber gir bindings to run this test case.")
class TestGwibber(unittest.TestCase):
    """Tests the "where is it in the menu" code."""

    patch_vars = (("SOFTWARE_CENTER_GWIBBER_MOCK_USERS", "2"),
                  ("SOFTWARE_CENTER_GWIBBER_MOCK_NO_FAIL", "1"))

    def setUp(self):
        for env_var, value in self.patch_vars:
            real = os.environ.get(env_var, NOT_DEFINED)
            if real is NOT_DEFINED:
                self.addCleanup(os.environ.pop, env_var)
            else:
                self.addCleanup(os.environ.__setitem__, env_var, real)
            os.environ[env_var] = value

    def test_gwibber_helper_mock(self):
        gh = GwibberHelperMock()
        accounts = gh.accounts()
        self.assertEqual(len(accounts), 2)
        #print accounts
        # we can not test the real gwibber here, otherwise it will
        # post our test data to real services
        self.assertEqual(gh.send_message ("test"), True)

    def test_gwibber_helper(self):
        # readonly test as there maybe be real accounts
        gh = GwibberHelper()
        have_accounts = gh.has_accounts_in_sqlite()
        self.assertTrue(isinstance(have_accounts, bool))
        accounts = gh.accounts()
        self.assertTrue(isinstance(accounts, list))

    @unittest.skip('not_working_because_gi_does_not_provide_list_test_gwibber')
    def test_gwibber_send_message(self):
        service = Gwibber.Service()
        self.addCleanup(service.quit)
        # get account data
        accounts = Gwibber.Accounts()
        # print dir(accounts)
        self.assertTrue(len(accounts.list()) > 0)
        # check single account for send enabled, only do if "True"
        #print accounts.send_enabled(accounts.list[0])
        # first check gwibber available
        service = Gwibber.Service()
        # print dir(service)
        service.service_available(False)
        service.send_message("test")


if __name__ == "__main__":
    unittest.main()
