import unittest

from mock import patch
from softwarecenter.distro import get_distro
from softwarecenter.backend.zeitgeist_logger import ZeitgeistLogger
from tests.utils import setup_test_env

setup_test_env()

class TestZeitgeistLogger(unittest.TestCase):
    """ tests the zeitgeist logger """

    def setUp(self):
        from softwarecenter.backend import zeitgeist_logger
        if not zeitgeist_logger.HAVE_MODULE:
            self.skipTest("Zeitgeist module missing, impossible to test")

        from zeitgeist import datamodel
        self.distro = get_distro()
        self.logger = ZeitgeistLogger(self.distro)
        self.datamodel = datamodel

    def _verify_event(self, event):
        self.assertEqual(event.actor, "application://" +
                         self.distro.get_app_id() + ".desktop")
        self.assertEqual(event.manifestation,
                         self.datamodel.Manifestation.EVENT_MANIFESTATION.USER_ACTIVITY)

    def _verify_subject(self, subject, desktop):
        self.assertEqual(subject.interpretation, self.datamodel.Interpretation.SOFTWARE)
        self.assertEqual(subject.manifestation, self.datamodel.Manifestation.SOFTWARE_ITEM)
        self.assertEqual(subject.uri, "application://" + desktop)
        self.assertEqual(subject.current_uri, subject.uri)
        self.assertEqual(subject.mimetype, "application/x-desktop")

    def test_construction(self):
        self.assertEqual(self.logger.distro, self.distro)

    @patch("zeitgeist.client.ZeitgeistClient.insert_event")
    def test_log_install_event(self, mock_insert_event):
        test_desktop = "software-center.desktop"
        self.assertTrue(self.logger.log_install_event(test_desktop))
        self.assertTrue(mock_insert_event.called)
        self.assertEqual(mock_insert_event.call_count, 2)
        [event] = mock_insert_event.call_args_list[0][0]
        self._verify_event(event)
        self.assertEqual(event.interpretation,
                         self.datamodel.Interpretation.EVENT_INTERPRETATION.CREATE_EVENT)
        self.assertEqual(len(event.subjects), 1)
        self._verify_subject(event.subjects[0], test_desktop)

        [event] = mock_insert_event.call_args_list[1][0]
        self._verify_event(event)
        self.assertEqual(event.interpretation,
                         self.datamodel.Interpretation.EVENT_INTERPRETATION.ACCESS_EVENT)
        self.assertEqual(len(event.subjects), 1)
        self._verify_subject(event.subjects[0], test_desktop)

    @patch("zeitgeist.client.ZeitgeistClient.insert_event")
    def test_log_install_event_invalid_desktop(self, mock_insert_event):
        self.assertFalse(self.logger.log_install_event(""))
        self.assertFalse(mock_insert_event.called)

    @patch("zeitgeist.client.ZeitgeistClient.insert_event")
    def test_log_uninstall_event(self, mock_insert_event):
        test_desktop = "software-center.desktop"
        self.assertTrue(self.logger.log_uninstall_event(test_desktop))
        self.assertTrue(mock_insert_event.called)
        self.assertEqual(mock_insert_event.call_count, 1)
        [event] = mock_insert_event.call_args_list[0][0]
        self._verify_event(event)
        self.assertEqual(event.interpretation,
                         self.datamodel.Interpretation.EVENT_INTERPRETATION.DELETE_EVENT)
        self.assertEqual(len(event.subjects), 1)
        self._verify_subject(event.subjects[0], test_desktop)

    @patch("zeitgeist.client.ZeitgeistClient.insert_event")
    def test_log_uninstall_event_invalid_desktop(self, mock_insert_event):
        self.assertFalse(self.logger.log_uninstall_event(""))
        self.assertFalse(mock_insert_event.called)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
