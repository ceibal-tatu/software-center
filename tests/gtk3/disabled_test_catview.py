import unittest

from mock import patch, Mock

from tests.utils import (
    do_events,
    do_events_with_sleep,
    get_test_db,
    get_test_gtk3_icon_cache,
    make_recommender_agent_recommend_me_dict,
    setup_test_env,
)
setup_test_env()

import softwarecenter.distro
import softwarecenter.paths

from softwarecenter.db.appfilter import AppFilter
from softwarecenter.enums import (SortMethods,
                                  TransactionTypes,
                                  RecommenderFeedbackActions)
from softwarecenter.ui.gtk3.views import lobbyview
from softwarecenter.ui.gtk3.widgets.containers import FramedHeaderBox
from softwarecenter.ui.gtk3.widgets.spinner import SpinnerNotebook
from tests.gtk3.windows import get_test_window_catview


class CatViewBaseTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = get_test_db()

    def setUp(self, selected_category=None):
        self._cat = None
        self._app = None
        self.win = get_test_window_catview(self.db, selected_category)
        self.addCleanup(self.win.destroy)
        self.notebook = self.win.get_child()
        self.lobby = self.win.get_data("lobby")
        self.subcat_view = self.win.get_data("subcat")

    def _on_category_selected(self, subcatview, category):
        self._cat = category


class TopAndWhatsNewTestCase(CatViewBaseTestCase):

    def test_top_rated(self):
        # simulate review-stats refresh
        self.lobby._update_top_rated_content = Mock()
        self.lobby.reviews_loader.emit("refresh-review-stats-finished", [])
        self.assertTrue(self.lobby._update_top_rated_content.called)

        # test clicking top_rated
        self.lobby.connect("category-selected", self._on_category_selected)
        self.lobby.top_rated_frame.more.clicked()
        do_events()
        self.assertNotEqual(self._cat, None)
        self.assertEqual(self._cat.name, "Top Rated")
        self.assertEqual(self._cat.sortmode, SortMethods.BY_TOP_RATED)

    def test_new(self):
        # test db reopen triggers whats-new update
        self.lobby._update_whats_new_content = Mock()
        self.lobby.db.emit("reopen")
        self.assertTrue(self.lobby._update_whats_new_content.called)

        # test clicking new
        self.lobby.connect("category-selected", self._on_category_selected)
        self.lobby.whats_new_frame.more.clicked()
        do_events()
        self.assertNotEqual(self._cat, None)
        # encoding is utf-8 (since r2218, see category.py)
        self.assertEqual(self._cat.name, 'What\xe2\x80\x99s New')
        self.assertEqual(self._cat.sortmode, SortMethods.BY_CATALOGED_TIME)

    def test_no_axi_cataloged_time_info_yet(self):
        """ ensure that we show "whats new" DB_CATALOGED_TIME data if there
            is no x-a-i yet """
        db = get_test_db()
        cache = db._aptcache
        icons = get_test_gtk3_icon_cache()
        apps_filter = AppFilter(db, cache)

        # simulate a fresh install with no catalogedtime info in a-x-i
        if "catalogedtime" in db._axi_values:
            del db._axi_values["catalogedtime"]

        # create it
        view = lobbyview.LobbyView(cache, db, icons,
            softwarecenter.distro.get_distro(), apps_filter)
        view.show_all()
        # and ensure its visible
        self.assertTrue(view.whats_new_frame.get_property("visible"))


class RecommendationsTestCase(CatViewBaseTestCase):
    """The test suite for the recommendations ."""
    
    # we need to use a custom setUp method for the recommendations test cases
    # so that everything gets configured properly
    @patch('softwarecenter.ui.gtk3.widgets.recommendations.get_login_backend')
    @patch('softwarecenter.ui.gtk3.widgets.recommendations.RecommenderAgent'
           '.is_opted_in')
    # patch out the agent query method to avoid making the actual server call
    @patch('softwarecenter.ui.gtk3.widgets.recommendations.RecommenderAgent'
           '.post_submit_profile')
    def setUp(self, mock_query, mock_recommender_is_opted_in, mock_sso):
        # patch the recommender to specify that we are not opted-in at
        # the start of each test
        mock_recommender_is_opted_in.return_value = False
        # we specify the "Internet" category because we do specific checks
        # in the following tests that depend on this being the category choice
        super(RecommendationsTestCase, self).setUp(selected_category="Internet")
        self.rec_panel = self.lobby.recommended_for_you_panel

    def test_recommended_for_you_opt_in_display(self):
        self.assertEqual(self.rec_panel.spinner_notebook.get_current_page(),
                         FramedHeaderBox.CONTENT)
        self.assertTrue(
            self.rec_panel.recommended_for_you_content.get_property("visible"))

        # ensure that we are showing the opt-in view
        self.assertTrue(self.rec_panel.opt_in_button.get_property("visible"))
        label_text = self.rec_panel.opt_in_label.get_text()
        self.assertEqual(label_text,
                         self.rec_panel.RECOMMENDATIONS_OPT_IN_TEXT)

    @patch('softwarecenter.ui.gtk3.widgets.recommendations'
           '.network_state_is_connected')
    def test_recommended_for_you_spinner_display(self, 
                                             mock_network_state_is_connected):
        # pretend we have network even if we don't
        mock_network_state_is_connected.return_value = True
        # click the opt-in button to initiate the process,
        # this will show the spinner
        self.rec_panel.opt_in_button.clicked()
        do_events_with_sleep()
        self.assertEqual(self.rec_panel.spinner_notebook.get_current_page(),
                         SpinnerNotebook.SPINNER_PAGE)
        self.assertTrue(
            self.rec_panel.recommended_for_you_content.get_property("visible"))

    @patch('softwarecenter.ui.gtk3.widgets.recommendations'
           '.network_state_is_connected')
    def test_recommended_for_you_network_not_available(self,
                mock_network_state_is_connected):
        # simulate no network available
        mock_network_state_is_connected.return_value = False
        self._opt_in_and_populate_recommended_for_you_panel()
        # ensure that we are showing the network not available view
        self.assertFalse(self.rec_panel.opt_in_button.get_property("visible"))
        label_text = self.rec_panel.opt_in_label.get_text()
        self.assertEqual(label_text,
                         self.rec_panel.NO_NETWORK_RECOMMENDATIONS_TEXT)

    def test_recommended_for_you_display_recommendations(self):
        self._opt_in_and_populate_recommended_for_you_panel()
        # we fake the callback from the agent here
        for_you = self.rec_panel.recommended_for_you_cat
        for_you._recommend_me_result(None,
            make_recommender_agent_recommend_me_dict())
        self.assertNotEqual(for_you.get_documents(self.db), [])
        self.assertEqual(self.rec_panel.spinner_notebook.get_current_page(),
                         SpinnerNotebook.CONTENT_PAGE)
        do_events()
        # test clicking recommended_for_you More button
        self.lobby.connect("category-selected", self._on_category_selected)
        self.rec_panel.more.clicked()
        # this is delayed for some reason so we need to sleep here
        do_events_with_sleep()
        self.assertNotEqual(self._cat, None)
        self.assertEqual(self._cat.name, "Recommended For You")

    def test_recommended_for_you_display_recommendations_not_opted_in(self):
        # we want to work in the "subcat" view
        self.notebook.next_page()

        do_events()
        visible = self.subcat_view.recommended_for_you_in_cat.get_property(
            "visible")
        self.assertFalse(visible)

    def test_recommended_for_you_display_recommendations_opted_in(self):
        self._opt_in_and_populate_recommended_for_you_panel()

        # we want to work in the "subcat" view
        self.notebook.next_page()

        rec_cat_panel = self.subcat_view.recommended_for_you_in_cat
        rec_cat_panel._update_recommended_for_you_content()
        do_events()
        # we fake the callback from the agent here
        rec_cat_panel.recommended_for_you_cat._recommend_me_result(
                                None,
                                make_recommender_agent_recommend_me_dict())
        result_docs = rec_cat_panel.recommended_for_you_cat.get_documents(
            self.db)
        self.assertNotEqual(result_docs, [])
        # check that we are getting the correct number of results,
        # corresponding to the following Internet items:
        #   Mangler, Midori, Midori Private Browsing, Psi
        self.assertTrue(len(result_docs) == 4)
        self.assertEqual(rec_cat_panel.spinner_notebook.get_current_page(),
                         SpinnerNotebook.CONTENT_PAGE)
        # check that the tiles themselves are visible
        self.assertTrue(rec_cat_panel.recommended_for_you_content.get_property(
            "visible"))
        self.assertTrue(rec_cat_panel.recommended_for_you_content.get_children(
            )[0].title.get_property("visible"))

        # test clicking recommended_for_you More button
        self.subcat_view.connect(
            "category-selected", self._on_category_selected)
        rec_cat_panel.more.clicked()
        # this is delayed for some reason so we need to sleep here
        do_events_with_sleep()
        self.assertNotEqual(self._cat, None)
        self.assertEqual(self._cat.name, "Recommended For You in Internet")
        
    def test_implicit_recommender_feedback(self):
        self._opt_in_and_populate_recommended_for_you_panel()
        # we fake the callback from the agent here
        for_you = self.rec_panel.recommended_for_you_cat
        for_you._recommend_me_result(None,
            make_recommender_agent_recommend_me_dict())
        do_events()
        
        post_implicit_feedback_fn = ('softwarecenter.ui.gtk3.widgets'
                                     '.recommendations.RecommenderAgent'
                                     '.post_implicit_feedback')
        with patch(post_implicit_feedback_fn) as mock_post_implicit_feedback:
            # we want to grab the app that is activated, it will be in
            # self._app after the app is activated on the tile click
            self.rec_panel.recommended_for_you_content.connect(
                                            "application-activated",
                                            self._on_application_activated)
            # click a recommendation in the lobby
            self._click_first_tile_in_panel(self.rec_panel)
            # simulate installing the application
            self._simulate_install_events(self._app)
            # and verify that after the install has completed we have fired
            # the implicit feedback call to the recommender with the correct
            # arguments
            mock_post_implicit_feedback.assert_called_with(
                    self._app.pkgname,
                    RecommenderFeedbackActions.INSTALLED)
            # finally, make sure that we have cleared the application
            # from the recommended_apps_viewed set
            self.assertFalse(self._app.pkgname in
                    self.rec_panel.recommended_apps_viewed)
                    
    def test_implicit_recommender_feedback_on_item_viewed(self):
        self._opt_in_and_populate_recommended_for_you_panel()
        # we fake the callback from the agent here
        for_you = self.rec_panel.recommended_for_you_cat
        for_you._recommend_me_result(None,
            make_recommender_agent_recommend_me_dict())
        do_events()
        
        post_implicit_feedback_fn = ('softwarecenter.ui.gtk3.widgets'
                                     '.recommendations.RecommenderAgent'
                                     '.post_implicit_feedback')
        with patch(post_implicit_feedback_fn) as mock_post_implicit_feedback:
            # we want to grab the app that is activated, it will be in
            # self._app after the app is activated on the tile click
            self.rec_panel.recommended_for_you_content.connect(
                                            "application-activated",
                                            self._on_application_activated)
            # click a recommendation in the lobby
            self._click_first_tile_in_panel(self.rec_panel)
            # and verify that upon selecting a recommended app we have fired
            # the implicit feedback call to the recommender with the correct
            # arguments
            mock_post_implicit_feedback.assert_called_with(
                    self._app.pkgname,
                    RecommenderFeedbackActions.VIEWED)
                    
    def test_implicit_recommender_feedback_recommendations_panel_only(self):
        # this test insures that we only provide feedback when installing
        # items clicked to via the recommendations panel itself, and not
        # via the What's New or Top Rated panels
        self._opt_in_and_populate_recommended_for_you_panel()
        # we fake the callback from the agent here
        for_you = self.rec_panel.recommended_for_you_cat
        for_you._recommend_me_result(None,
            make_recommender_agent_recommend_me_dict())
        do_events()
        
        post_implicit_feedback_fn = ('softwarecenter.ui.gtk3.widgets'
                                     '.recommendations.RecommenderAgent'
                                     '.post_implicit_feedback')
        with patch(post_implicit_feedback_fn) as mock_post_implicit_feedback:
            # we want to grab the app that is activated, it will be in
            # self._app after the app is activated on the tile click
            self.lobby.top_rated.connect("application-activated",
                                          self._on_application_activated)
            # click a tile in the Top Rated section of the lobby
            self._click_first_tile_in_panel(self.lobby.top_rated_frame)
            # simulate installing the application
            self._simulate_install_events(self._app)
            # and verify that after the install has completed we have *not*
            # fired the implicit feedback call to the recommender service
            self.assertFalse(mock_post_implicit_feedback.called)
                    
    def test_implicit_recommender_feedback_not_opted_in(self):
        # this test verifies that we do *not* send feedback to the
        # recommender service if the user has not opted-in to it
        post_implicit_feedback_fn = ('softwarecenter.ui.gtk3.widgets'
                                     '.recommendations.RecommenderAgent'
                                     '.post_implicit_feedback')
        with patch(post_implicit_feedback_fn) as mock_post_implicit_feedback:
            # we are not opted-in
            from softwarecenter.db.application import Application
            app = Application("Calculator", "gcalctool")
            # simulate installing the application
            self._simulate_install_events(app)
            # and verify that after the install has completed we have *not*
            # fired the implicit feedback call to the recommender
            self.assertFalse(mock_post_implicit_feedback.called)

    def _opt_in_and_populate_recommended_for_you_panel(self):
        # click the opt-in button to initiate the process
        self.rec_panel.opt_in_button.clicked()
        do_events()
        # simulate a successful opt-in by setting the recommender_uuid
        self.rec_panel.recommender_agent._set_recommender_uuid(
                "35fd653e67b14482b7a8b632ea90d1b6")
        # and update the recommended for you panel to load it up
        self.rec_panel._update_recommended_for_you_content()
        do_events()

    def _on_application_activated(self, catview, app):
        self._app = app

    def _click_first_tile_in_panel(self, framed_header_box):
        first_tile = (framed_header_box.content_box.
                        get_children()[0].get_children()[0])
        first_tile.clicked()
        do_events_with_sleep()

    def _simulate_install_events(self, app):
        # pretend we started an install
        self.rec_panel.backend.emit("transaction-started",
                                    app.pkgname, app.appname,
                                    "testid101",
                                    TransactionTypes.INSTALL)
        do_events_with_sleep()
        # send the signal to complete the install
        mock_result = Mock()
        mock_result.pkgname = app.pkgname
        self.rec_panel.backend.emit("transaction-finished",
                                    mock_result)
        do_events()

        
if __name__ == "__main__":
    unittest.main()
