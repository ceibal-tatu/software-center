import json
import platform
import unittest
import xapian

from gi.repository import GLib

from mock import patch
from piston_mini_client import PistonResponseObject
from tests.utils import (
    get_test_pkg_info,
    setup_test_env,
    ObjectWithSignals,
)
setup_test_env()

from softwarecenter.enums import (
    AppInfoFields,
    AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
    XapianValues,
)
from softwarecenter.db.database import get_reinstall_previous_purchases_query
from softwarecenter.db.update import (
    SCAPurchasedApplicationParser,
    SCAApplicationParser,
    update_from_software_center_agent,
)

# Example taken from running:
# PYTHONPATH=. utils/piston-helpers/piston_generic_helper.py --output=pickle \
#           --debug --needs-auth SoftwareCenterAgentAPI subscriptions_for_me
# then:
#    f = open('my_subscriptions.pickle')
#    subscriptions = pickle.load(f)
#    completed_subs = [subs for subs in subscriptions if subs.state=='Complete']
#    completed_subs[0].__dict__
SUBSCRIPTIONS_FOR_ME_JSON = """
[
    {
         "deb_line": "deb https://username:random3atoken@private-ppa.launchpad.net/commercial-ppa-uploaders/photobomb/ubuntu natty main",
         "purchase_price": "2.99",
         "purchase_date": "2011-09-16 06:37:52",
         "state": "Complete",
         "failures": [],
         "open_id": "https://login.ubuntu.com/+id/ABCDEF",
         "application": {
              "archive_id": "commercial-ppa-uploaders/photobomb",
              "signing_key_id": "1024R/75254D99",
              "name": "Photobomb",
              "package_name": "photobomb",
              "description": "Easy and Social Image Editor\\nPhotobomb give you easy access to images in your social networking feeds, pictures on your computer and peripherals, and pictures on the web, and let\'s you draw, write, crop, combine, and generally have a blast mashing \'em all up. Then you can save off your photobomb, or tweet your creation right back to your social network.",
              "version": "1.2.1"
         },
         "distro_series": {"code_name": "natty", "version": "11.04"}
    }
]
"""
# Taken directly from:
# https://software-center.ubuntu.com/api/2.0/applications/en/ubuntu/oneiric/i386/
AVAILABLE_APPS_JSON = """
[
    {
        "archive_id": "commercial-ppa-uploaders/fluendo-dvd",
        "signing_key_id": "1024R/75254D99",
        "license": "Proprietary",
        "name": "Fluendo DVD Player",
        "package_name": "fluendo-dvd",
        "support_url": "",
        "series": {
            "maverick": [
                "i386",
                "amd64"
            ],
            "natty": [
                "i386",
                "amd64"
            ],
            "oneiric": [
                "i386",
                "amd64"
            ]
        },
        "price": "24.95",
        "demo": null,
        "date_published": "2011-12-05 18:43:21.653868",
        "status": "Published",
        "channel": "For Purchase",
        "icon_data": "...",
        "department": [
            "Sound & Video"
        ],
        "archive_root": "https://private-ppa.launchpad.net/",
        "screenshot_url": "http://software-center.ubuntu.com/site_media/screenshots/2011/05/fluendo-dvd-maverick_.png",
        "tos_url": "https://software-center.ubuntu.com/licenses/3/",
        "icon_url": "http://software-center.ubuntu.com/site_media/icons/2011/05/fluendo-dvd.png",
        "categories": "AudioVideo",
        "description": "Play DVD-Videos\\r\\n\\r\\nFluendo DVD Player is a software application specially designed to\\r\\nreproduce DVD on Linux/Unix platforms, which provides end users with\\r\\nhigh quality standards.\\r\\n\\r\\nThe following features are provided:\\r\\n* Full DVD Playback\\r\\n* DVD Menu support\\r\\n* Fullscreen support\\r\\n* Dolby Digital pass-through\\r\\n* Dolby Digital 5.1 output and stereo downmixing support\\r\\n* Resume from last position support\\r\\n* Subtitle support\\r\\n* Audio selection support\\r\\n* Multiple Angles support\\r\\n* Support for encrypted discs\\r\\n* Multiregion, works in all regions\\r\\n* Multiple video deinterlacing algorithms",
        "website": null,
        "version": "1.2.1",
        "binary_filesize": 12345
    },
    {
    "website": "",
    "package_name": "photobomb",
    "video_embedded_html_urls": [ ],
    "demo": null,
    "keywords": "photos, pictures, editing, gwibber, twitter, facebook, drawing",
    "video_urls": [ ],
    "screenshot_url": "http://software-center.ubuntu.com/site_media/screenshots/2011/08/Screenshot-45.png",
    "id": 83,
    "archive_id": "commercial-ppa-uploaders/photobomb",
    "support_url": "http://launchpad.net/photobomb",
    "icon_url": "http://software-center.ubuntu.com/site_media/icons/2011/08/logo_64.png",
    "binary_filesize": null,
    "version": "",
    "company_name": "",
    "department": [
        "Graphics"
    ],
    "tos_url": "",
    "channel": "For Purchase",
    "status": "Published",
    "signing_key_id": "1024R/75254D99",
    "description": "Easy and Social Image Editor\\nPhotobomb give you easy access to images in your social networking feeds, pictures on your computer and peripherals, and pictures on the web, and let's you draw, write, crop, combine, and generally have a blast mashing 'em all up. Then you can save off your photobomb, or tweet your creation right back to your social network.",
    "price": "2.99",
    "debtags": [ ],
    "date_published": "2011-12-05 18:43:20.794802",
    "categories": "Graphics",
    "name": "Photobomb",
    "license": "GNU GPL v3",
    "screenshot_urls": [
        "http://software-center.ubuntu.com/site_media/screenshots/2011/08/Screenshot-45.png"
    ],
    "archive_root": "https://private-ppa.launchpad.net/"
  }
]
"""


class SCAApplicationParserTestCase(unittest.TestCase):

    def _make_application_parser(self, piston_application=None):
        if piston_application is None:
            piston_application = PistonResponseObject.from_dict(
                json.loads(AVAILABLE_APPS_JSON)[0])
        return SCAApplicationParser(piston_application)

    def test_parses_application_from_available_apps(self):
        parser = self._make_application_parser()
        inverse_map = dict(
            (val, key) for key, val in SCAApplicationParser.MAPPING.items())

        # Delete the keys which are not yet provided via the API:
        del(inverse_map['video_embedded_html_url'])

        for key in inverse_map:
            self.assertEqual(
                getattr(parser.sca_application, key),
                parser.get_value(inverse_map[key]))

    def test_name_not_updated_for_non_purchased_apps(self):
        parser = self._make_application_parser()

        self.assertEqual('Fluendo DVD Player',
                         parser.get_value(AppInfoFields.NAME))

    def test_binary_filesize(self):
        parser = self._make_application_parser()

        self.assertEqual(12345,
                         parser.get_value(AppInfoFields.DOWNLOAD_SIZE))

    def test_keys_not_provided_by_api(self):
        parser = self._make_application_parser()

        self.assertIsNone(parser.get_value(AppInfoFields.VIDEO_URL))
        self.assertEqual('Application', parser.get_value(AppInfoFields.TYPE))

    def test_thumbnail_is_screenshot(self):
        parser = self._make_application_parser()

        self.assertEqual(
            "http://software-center.ubuntu.com/site_media/screenshots/"
            "2011/05/fluendo-dvd-maverick_.png",
            parser.get_value(AppInfoFields.THUMBNAIL_URL))

    def test_extracts_description(self):
        parser = self._make_application_parser()

        self.assertEqual("Play DVD-Videos",
                         parser.get_value(AppInfoFields.SUMMARY))
        self.assertEqual(
            "Fluendo DVD Player is a software application specially designed "
            "to\r\nreproduce DVD on Linux/Unix platforms, which provides end "
            "users with\r\nhigh quality standards.\r\n\r\nThe following "
            "features are provided:\r\n* Full DVD Playback\r\n* DVD Menu "
            "support\r\n* Fullscreen support\r\n* Dolby Digital pass-through"
            "\r\n* Dolby Digital 5.1 output and stereo downmixing support\r\n"
            "* Resume from last position support\r\n* Subtitle support\r\n"
            "* Audio selection support\r\n* Multiple Angles support\r\n"
            "* Support for encrypted discs\r\n"
            "* Multiregion, works in all regions\r\n"
            "* Multiple video deinterlacing algorithms",
            parser.get_value(AppInfoFields.DESCRIPTION))

    def test_desktop_categories_uses_department(self):
        parser = self._make_application_parser()

        self.assertEqual([u'DEPARTMENT:Sound & Video', "AudioVideo"],
            parser.get_categories())

    def test_desktop_categories_no_department(self):
        piston_app = PistonResponseObject.from_dict(
            json.loads(AVAILABLE_APPS_JSON)[0])
        del(piston_app.department)
        parser = self._make_application_parser(piston_app)

        self.assertEqual(["AudioVideo"], parser.get_categories())

    def test_magic_channel(self):
        parser = self._make_application_parser()

        self.assertEqual(
            AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
            parser.get_value(AppInfoFields.CHANNEL))


class SCAPurchasedApplicationParserTestCase(unittest.TestCase):

    def _make_application_parser(self, piston_subscription=None):
        if piston_subscription is None:
            piston_subscription = PistonResponseObject.from_dict(
                json.loads(SUBSCRIPTIONS_FOR_ME_JSON)[0])

        return SCAPurchasedApplicationParser(piston_subscription)

    def setUp(self):
        get_distro_patcher = patch('softwarecenter.db.update.get_distro')
        self.addCleanup(get_distro_patcher.stop)
        mock_get_distro = get_distro_patcher.start()
        mock_get_distro.return_value.get_codename.return_value = 'quintessential'

    def test_get_desktop_subscription(self):
        parser = self._make_application_parser()

        expected_results = {
            AppInfoFields.DEB_LINE: "deb https://username:random3atoken@"
                         "private-ppa.launchpad.net/commercial-ppa-uploaders"
                         "/photobomb/ubuntu quintessential main",
            AppInfoFields.DEB_LINE_ORIG:
                         "deb https://username:random3atoken@"
                         "private-ppa.launchpad.net/commercial-ppa-uploaders"
                         "/photobomb/ubuntu natty main",
            AppInfoFields.PURCHASED_DATE: "2011-09-16 06:37:52",
        }
        for key in expected_results:
            result = parser.get_value(key)
            self.assertEqual(expected_results[key], result)

    def test_get_desktop_application(self):
        # The parser passes application attributes through to
        # an application parser for handling.
        parser = self._make_application_parser()

        # We're testing here also that the name is updated automatically.
        expected_results = {
            AppInfoFields.NAME: "Photobomb (already purchased)",
            AppInfoFields.PACKAGE: "photobomb",
            AppInfoFields.SIGNING_KEY_ID: "1024R/75254D99",
            AppInfoFields.PPA: "commercial-ppa-uploaders/photobomb",
        }
        for key in expected_results.keys():
            result = parser.get_value(key)
            self.assertEqual(expected_results[key], result)

    def test_has_option_desktop_includes_app_keys(self):
        # The SCAPurchasedApplicationParser handles application keys also
        # (passing them through to the composited application parser).
        parser = self._make_application_parser()

        for key in (AppInfoFields.NAME, AppInfoFields.PACKAGE,
                    AppInfoFields.SIGNING_KEY_ID, AppInfoFields.PPA):
            self.assertIsNotNone(parser.get_value(key))
        for key in (AppInfoFields.DEB_LINE, AppInfoFields.PURCHASED_DATE):
            self.assertIsNotNone(parser.get_value(key),
                                 'Key: {0} was not an option.'.format(key))

    def test_license_key_present(self):
        piston_subscription = PistonResponseObject.from_dict(
            json.loads(SUBSCRIPTIONS_FOR_ME_JSON)[0])
        piston_subscription.license_key = 'abcd'
        piston_subscription.license_key_path = '/foo'
        parser = self._make_application_parser(piston_subscription)

        self.assertEqual('abcd', parser.get_value(AppInfoFields.LICENSE_KEY))
        self.assertEqual(
            '/foo', parser.get_value(AppInfoFields.LICENSE_KEY_PATH))

    def test_license_key_not_present(self):
        parser = self._make_application_parser()

        for key in (AppInfoFields.LICENSE_KEY, AppInfoFields.LICENSE_KEY_PATH):
            self.assertIsNone(parser.get_value(key))

    def test_purchase_date(self):
        parser = self._make_application_parser()
        self.assertEqual(
            "2011-09-16 06:37:52",
            parser.get_value(AppInfoFields.PURCHASED_DATE))

    def test_will_handle_supported_distros_when_available(self):
        # When the fix for bug 917109 reaches production, we will be
        # able to use the supported series.
        parser = self._make_application_parser()
        supported_distros = {
            "maverick": [
                "i386",
                "amd64"
                ],
            "natty": [
                "i386",
                "amd64"
                ],
            }
        parser.sca_application.series = supported_distros

        self.assertEqual(
            supported_distros,
            parser.get_value(AppInfoFields.SUPPORTED_DISTROS))

    def test_update_debline_other_series(self):
        orig_debline = (
            "deb https://username:random3atoken@"
            "private-ppa.launchpad.net/commercial-ppa-uploaders"
            "/photobomb/ubuntu karmic main")
        expected_debline = (
            "deb https://username:random3atoken@"
            "private-ppa.launchpad.net/commercial-ppa-uploaders"
            "/photobomb/ubuntu quintessential main")

        self.assertEqual(expected_debline,
            SCAPurchasedApplicationParser.update_debline(orig_debline))

    def test_update_debline_with_pocket(self):
        orig_debline = (
            "deb https://username:random3atoken@"
            "private-ppa.launchpad.net/commercial-ppa-uploaders"
            "/photobomb/ubuntu karmic-security main")
        expected_debline = (
            "deb https://username:random3atoken@"
            "private-ppa.launchpad.net/commercial-ppa-uploaders"
            "/photobomb/ubuntu quintessential-security main")

        self.assertEqual(expected_debline,
            SCAPurchasedApplicationParser.update_debline(orig_debline))


class TestAvailableForMeMerging(unittest.TestCase):

    def setUp(self):
        self.available_for_me = self._make_available_for_me_list()
        self.available = self._make_available_list()

    def _make_available_for_me_list(self):
        my_subscriptions = json.loads(SUBSCRIPTIONS_FOR_ME_JSON)
        return list(
            PistonResponseObject.from_dict(subs) for subs in my_subscriptions)

    def _make_available_list(self):
        available_apps = json.loads(AVAILABLE_APPS_JSON)
        return list(
            PistonResponseObject.from_dict(subs) for subs in available_apps)

    def _make_fake_scagent(self, available_data, available_for_me_data):
        sca = ObjectWithSignals()
        sca.query_available = lambda **kwargs: GLib.timeout_add(
                100, lambda: sca.emit('available', sca, available_data))
        sca.query_available_for_me = lambda **kwargs: GLib.timeout_add(
            100, lambda: sca.emit('available-for-me', 
                                  sca, available_for_me_data))
        return sca

    def test_reinstall_purchased_mock(self):
        # test if the mocks are ok
        self.assertEqual(len(self.available_for_me), 1)
        self.assertEqual(
            self.available_for_me[0].application['package_name'], "photobomb")

    @patch("softwarecenter.db.update.SoftwareCenterAgent")
    @patch("softwarecenter.db.update.UbuntuSSO")
    def test_reinstall_purchased_xapian(self, mock_helper, mock_agent):
        small_available =  [ self.available[0] ]
        mock_agent.return_value = self._make_fake_scagent(
            small_available, self.available_for_me)

        db = xapian.inmemory_open()
        cache = get_test_pkg_info()

        # now create purchased debs xapian index (in memory because
        # we store the repository passwords in here)
        old_db_len = db.get_doccount()
        update_from_software_center_agent(db, cache)
        # ensure we have the new item
        self.assertEqual(db.get_doccount(), old_db_len+2)
        # query
        query = get_reinstall_previous_purchases_query()
        enquire = xapian.Enquire(db)
        enquire.set_query(query)
        matches = enquire.get_mset(0, db.get_doccount())
        self.assertEqual(len(matches), 1)
        distroseries = platform.dist()[2]
        for m in matches:
            doc = db.get_document(m.docid)
            self.assertEqual(doc.get_value(XapianValues.PKGNAME), "photobomb")
            self.assertEqual(
                doc.get_value(XapianValues.ARCHIVE_SIGNING_KEY_ID),
                "1024R/75254D99")
            self.assertEqual(doc.get_value(XapianValues.ARCHIVE_DEB_LINE),
                "deb https://username:random3atoken@"
                 "private-ppa.launchpad.net/commercial-ppa-uploaders"
                 "/photobomb/ubuntu %s main" % distroseries)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
