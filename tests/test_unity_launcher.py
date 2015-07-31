import unittest

from mock import (
    Mock,
    patch,
    )

from softwarecenter.backend.unitylauncher import (
    UnityLauncherInfo,
    UnityLauncher,
    )

from tests.utils import setup_test_env
setup_test_env()


class TestUnityLauncherIntegration(unittest.TestCase):
    """ tests the sc utils """

    @patch("softwarecenter.backend.unitylauncher.UnityLauncher"
           "._get_launcher_dbus_iface")
    def test_apps_from_sc_agent(self, mock_dbus_iface):
        mock_iface = Mock()
        mock_dbus_iface.return_value = mock_iface
        launcher_info = UnityLauncherInfo(
            name="Meep", icon_name="icon-meep", 
            icon_file_path="/tmp/icon-meep.png", icon_x=15, icon_y=18,
            icon_size=48, installed_desktop_file_path="software-center-agent",
            trans_id="dkfjklsdf")
        unity_launcher = UnityLauncher()
        unity_launcher.send_application_to_launcher("meep-pkg", launcher_info)
        args = mock_iface.AddLauncherItemFromPosition.call_args[0]
        # basic verify
        self.assertEqual(args[0], "Meep")
        # ensure that the a app from software-center-agent got a temp desktop
        # file
        self.assertTrue(args[5].startswith("/tmp/"))
        self.assertEqual(open(args[5]).read(),"""
[Desktop Entry]
Name=Meep
Icon=/tmp/icon-meep.png
Type=Application""")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
