import os
import unittest

from mock import patch
from gi.repository import GLib

from tests.utils import (
    get_test_db,
    setup_test_env,
)
setup_test_env()

import softwarecenter
from softwarecenter.backend.recagent import RecommenderAgent


class MockTestRecommenderAgent(unittest.TestCase):

    @patch.object(softwarecenter.backend.recagent.SpawnHelper, 
                  'run_generic_piston_helper')
    def test_mocked_recagent_post_submit_profile(self, mock_spawn_helper_run):
        recommender_agent = RecommenderAgent()
        recommender_agent._calc_profile_id = lambda profile: "i-am-random"
        db = get_test_db()
        recommender_agent.post_submit_profile(db)
        args, kwargs =  mock_spawn_helper_run.call_args
        # ensure we have packages in the package list and the
        # kwargs have the names we expect
        self.assertNotEqual(kwargs['data'][0]['package_list'], [])


class RealTestRecommenderAgent(unittest.TestCase):
    """ tests the recommender agent """
    
    @unittest.skipIf(os.getuid() == 0, 
                     "this is not supported running as root")
    def setUp(self):
        self.loop = GLib.MainLoop(GLib.main_context_default())
        self.error = False
        if "SOFTWARE_CENTER_RECOMMENDER_HOST" in os.environ:
            orig_host = os.environ.get("SOFTWARE_CENTER_RECOMMENDER_HOST")
            self.addCleanup(os.environ.__setitem__,
                "SOFTWARE_CENTER_RECOMMENDER_HOST", orig_host)
        else:
            self.addCleanup(os.environ.pop, "SOFTWARE_CENTER_RECOMMENDER_HOST")
        server = "https://rec.staging.ubuntu.com"
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = server
        # most tests need it
        self.recommender_agent = RecommenderAgent()
        self.recommender_agent.connect("error", self.on_query_error)

    def on_query_done(self, recagent, data):
        #print "query done, data: '%s'" % data
        self.loop.quit()
        self.error = False
        self.error_msg = ""

    def on_query_error(self, recagent, error):
        #print "query error received: ", error
        self.loop.quit()
        self.error = True
        self.error_msg = error

    def assertServerReturnsWithNoError(self):
        self.loop.run()
        self.assertFalse(self.error, "got error: '%s'" % self.error_msg)

    def test_recagent_query_server_status(self):
        self.recommender_agent.connect("server-status", self.on_query_done)
        self.recommender_agent.query_server_status()
        self.assertServerReturnsWithNoError()

    @unittest.skip("server returns 401")
    def test_recagent_post_submit_profile(self):
        # NOTE: This requires a working recommender host that is reachable
        db = get_test_db()
        self.recommender_agent.connect(
            "submit-profile-finished", self.on_query_done)
        self.recommender_agent.post_submit_profile(db)
        self.assertServerReturnsWithNoError()
        #print mock_request._post
        
    @unittest.skip("server returns 401")
    def test_recagent_query_submit_anon_profile(self):
        self.recommender_agent.connect(
            "submit-anon-profile-finished", self.on_query_done)
        self.recommender_agent.post_submit_anon_profile(
                uuid="xxxyyyzzz",
                installed_packages=["pitivi", "fretsonfire"],
                extra="")
        self.assertServerReturnsWithNoError()

    @unittest.skip("server returns 401")
    def test_recagent_query_profile(self):
        self.recommender_agent.connect("profile", self.on_query_done)
        self.recommender_agent.query_profile(pkgnames=["pitivi", "fretsonfire"])
        self.assertServerReturnsWithNoError()

    @unittest.skip("server returns 401")
    def test_recagent_query_recommend_me(self):
        self.recommender_agent.connect("recommend-me", self.on_query_done)
        self.recommender_agent.query_recommend_me()
        self.assertServerReturnsWithNoError()

    def test_recagent_query_recommend_app(self):
        self.recommender_agent.connect("recommend-app", self.on_query_done)
        self.recommender_agent.query_recommend_app("pitivi")
        self.assertServerReturnsWithNoError()

    def test_recagent_query_recommend_all_apps(self):
        self.recommender_agent.connect("recommend-all-apps", self.on_query_done)
        self.recommender_agent.query_recommend_all_apps()
        self.assertServerReturnsWithNoError()

    def test_recagent_query_recommend_top(self):
        self.recommender_agent.connect("recommend-top", self.on_query_done)
        self.recommender_agent.query_recommend_top()
        self.assertServerReturnsWithNoError()

    def test_recagent_query_error(self):
        # NOTE: This tests the error condition itself! it simply forces an error
        #       'cuz there definitely isn't a server here  :)
        fake_server = "https://test-no-server-here.staging.ubuntu.com"
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = fake_server
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-top", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_top()
        self.loop.run()
        self.assertTrue(self.error)

    @unittest.skip("server returns 401")
    def test_recagent_post_implicit_feedback(self):
        self.recommender_agent.connect("submit-implicit-feedback-finished",
                                  self.on_query_done)
        from softwarecenter.enums import RecommenderFeedbackActions
        self.recommender_agent.post_implicit_feedback(
                "bluefish",
                RecommenderFeedbackActions.INSTALLED)
        self.assertServerReturnsWithNoError()


if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
