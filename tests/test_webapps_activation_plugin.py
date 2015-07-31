import unittest

from mock import (
    Mock,
    patch)

from tests.utils import (
    setup_test_env,
    FakedCache,
    ObjectWithSignals,
)
setup_test_env()

from softwarecenter.plugins.webapps_activation import (
    UnityWebappsActivationPlugin)


def make_install_result_mock(pkgname, success):
    mock_install_result = Mock()
    mock_install_result.success = success
    mock_install_result.pkgname = pkgname
    return mock_install_result


def make_mock_package_with_record(pkgname, record):
    pkg = Mock()
    pkg.candidate = Mock()
    pkg.candidate.record = record
    return pkg


class FakedInstallBackend(ObjectWithSignals):
    pass


class WebappsActivationTestCase(unittest.TestCase):
    """Tests the webapps activation plugin """

    def setUp(self):
        # create webapp
        unity_webapp = make_mock_package_with_record(
            "unity-webapp",  { 'Ubuntu-Webapps-Domain': 'mail.ubuntu.com' })
        # create a non-webapp
        non_unity_webapp = make_mock_package_with_record(
            "unity-webapp",  {})
        # pkginfo
        self.mock_pkginfo = FakedCache()
        self.mock_pkginfo["unity-webapp"] = unity_webapp
        self.mock_pkginfo["non-unity-webapp"] = non_unity_webapp
        # install backend
        self.mock_installbackend = FakedInstallBackend()

    @patch("softwarecenter.plugins.webapps_activation.get_install_backend")
    @patch("softwarecenter.plugins.webapps_activation.get_pkg_info")
    def _get_patched_unity_webapps_activation_plugin(self,
                                                     mock_get_pkg_info,
                                                     mock_install_backend):
        mock_install_backend.return_value = self.mock_installbackend
        mock_get_pkg_info.return_value = self.mock_pkginfo
        w = UnityWebappsActivationPlugin()
        w.init_plugin()
        patcher = patch.object(w, "activate_unity_webapp_for_domain")
        patcher.start()
        self.addCleanup(patcher.stop)
        return w

    def test_activation(self):
        w = self._get_patched_unity_webapps_activation_plugin()
        self.mock_installbackend.emit(
            "transaction-finished", self.mock_installbackend,
            make_install_result_mock("unity-webapp", True))
        self.assertTrue(w.activate_unity_webapp_for_domain.called)
        w.activate_unity_webapp_for_domain.assert_called_with("mail.ubuntu.com")

    def test_no_activation_on_fail(self):
        w = self._get_patched_unity_webapps_activation_plugin()
        self.mock_installbackend.emit(
            "transaction-finished", self.mock_installbackend,
            make_install_result_mock("unity-webapp", False))
        self.assertFalse(w.activate_unity_webapp_for_domain.called)

    def test_no_activation_on_non_webapp(self):
        w = self._get_patched_unity_webapps_activation_plugin()
        self.mock_installbackend.emit(
            "transaction-finished", self.mock_installbackend,
            make_install_result_mock("non-unity-webapp", True))
        self.assertFalse(w.activate_unity_webapp_for_domain.called)

if __name__ == "__main__":
    unittest.main()
