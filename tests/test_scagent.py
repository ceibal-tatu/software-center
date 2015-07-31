import unittest

from gi.repository import GLib
from mock import Mock, patch

from tests.utils import (
    setup_test_env,
)
setup_test_env()

from softwarecenter.backend.scagent import SoftwareCenterAgent

class TestSCAgent(unittest.TestCase):
    """ tests software-center-agent """

    def setUp(self):
        self.loop = GLib.MainLoop(GLib.main_context_default())
        self.error = False

    def on_query_done(self, scagent, data):
        # print "query done, data: '%s'" % data
        self.loop.quit()

    def on_query_error(self, scagent, error):
        self.loop.quit()
        self.error = True

    def test_scagent_query_available(self):
        sca = SoftwareCenterAgent()
        sca.connect("available", self.on_query_done)
        sca.connect("error", self.on_query_error)
        sca.query_available()
        self.loop.run()
        self.assertFalse(self.error)

    def test_scagent_query_exhibits(self):
        sca = SoftwareCenterAgent()
        sca.connect("exhibits", self.on_query_done)
        sca.connect("error", self.on_query_error)
        sca.query_exhibits()
        self.loop.run()
        self.assertFalse(self.error)

    def test_scaagent_query_available_for_me_uses_complete_only(self):
        run_generic_piston_helper_fn = (
            'softwarecenter.backend.spawn_helper.SpawnHelper.'
            'run_generic_piston_helper')
        with patch(run_generic_piston_helper_fn) as mock_run_piston_helper:
            sca = SoftwareCenterAgent()
            sca.query_available_for_me()

            mock_run_piston_helper.assert_called_with(
                'SoftwareCenterAgentAPI', 'subscriptions_for_me',
                complete_only=True)


class RegressionsTestCase(unittest.TestCase):

    def setUp(self):
        self.sca = SoftwareCenterAgent()
        self.sca.emit = Mock()
        
    def _get_exhibit_list_from_emit_call(self):
        args, kwargs = self.sca.emit.call_args
        scagent, exhibit_list = args
        return exhibit_list

    def test_regression_lp1004417(self):
        mock_ex = Mock()
        mock_ex.package_names = "foo,bar\n\r"
        results = [mock_ex]
        self.sca._on_exhibits_data_available(None, results)
        self.assertTrue(self.sca.emit.called)
        # and ensure we get the right list len
        exhibit_list = self._get_exhibit_list_from_emit_call()
        self.assertEqual(len(exhibit_list), 1)
        # and the right data in the list
        exhibit = exhibit_list[0]
        self.assertEqual(exhibit.package_names, "foo,bar")
        self.assertFalse(exhibit.package_names.endswith("\n\r"))

    def test_regression_lp1043152(self):
        mock_ex = Mock()
        mock_ex.package_names = "moo, baa, lalala"
        results = [mock_ex]
        self.sca._on_exhibits_data_available(None, results)
        # ensure that the right data in the list
        exhibit = self._get_exhibit_list_from_emit_call()[0]
        self.assertEqual(exhibit.package_names, "moo,baa,lalala")

if __name__ == "__main__":
    unittest.main()
