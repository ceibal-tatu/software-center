import os
import unittest

from mock import Mock

from tests.utils import (
    DATA_DIR,
    setup_test_env,
)
setup_test_env()
from softwarecenter.plugin import PluginManager


class TestPlugin(unittest.TestCase):

    def test_plugin_manager(self):
        app = Mock()
        pm = PluginManager(app, os.path.join(DATA_DIR, "plugins"))
        pm.load_plugins()
        self.assertEqual(len(pm.plugins), 1)
        self.assertTrue(pm.plugins[0].i_am_happy)


if __name__ == "__main__":
    unittest.main()
