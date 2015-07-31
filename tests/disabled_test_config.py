#!/usr/bin/python

import os
from tempfile import NamedTemporaryFile
import unittest

from tests.utils import setup_test_env
setup_test_env()
from softwarecenter.config import (
    SoftwareCenterConfig, 
    get_config,
    )


class ConfigTestCase(unittest.TestCase):
    """ tests the config class """

    def setUp(self):
        self.tempfile = NamedTemporaryFile(prefix="sc-test-")
        self.config = SoftwareCenterConfig(self.tempfile.name)

    def test_properties_simple_bool(self):
        """ test a bool property """
        for value in [ True, False, True ]:
            self.config.add_to_unity_launcher = value
            self.assertEqual(self.config.add_to_unity_launcher, value)
            self.assertEqual(
                self.config.getboolean("general", "add_to_launcher"), value)

    def test_properties_default_bool(self):
        """ test default values for properties """
        self.assertTrue(self.config.add_to_unity_launcher)

    def test_properties_default_window_size(self):
        """ default value for window size tuple """
        self.assertEqual(self.config.app_window_size, [-1, -1])

    def test_properties_window_size(self):
        """ test the app_window_size getter/setter """
        self.config.app_window_size = [10, 10]
        self.assertEqual(self.config.app_window_size, [10, 10])

    def test_property_simple_string(self):
        """ test a string property """
        for value in [ "", "xxxyyy"]:
            self.config.recommender_uuid = value
            self.assertEqual(self.config.recommender_uuid, value)
            self.assertEqual(
                self.config.get("general", "recommender_uuid"), value)

    def test_write(self):
        """ test that write writes """
        self.assertEqual(os.path.getsize(self.tempfile.name), 0)
        self.config.user_accepted_tos = True
        self.config.write()
        self.assertNotEqual(os.path.getsize(self.tempfile.name), 0)
        with open(self.tempfile.name) as f:
            content = f.read()
            self.assertTrue(content.startswith("[general]\n"))
            self.assertTrue("\naccepted_tos = True\n" in content)

    def test_uuid_conversion(self):
        """ Test that going from the old uuid format to the new
            works transparently
        """
        self.config.recommender_uuid = "xx-yy-zz"
        self.assertEqual(self.config.recommender_uuid, "xxyyzz")

    def test_raise_on_unknown_property(self):
        """ test that we get a error for unknown properties """
        with self.assertRaises(AttributeError):
            self.config.unknown_propertiy

    def test_config_singleton(self):
        config1 = get_config()
        config2 = get_config()
        self.assertEqual(config1, config2)

if __name__ == "__main__":
    unittest.main()
