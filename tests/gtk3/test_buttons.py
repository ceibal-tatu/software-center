import unittest

from tests.utils import (
    get_mock_app_properties_helper,
    setup_test_env,
)
setup_test_env()

from softwarecenter.ui.gtk3.widgets.buttons import FeaturedTile


class TestWidgets(unittest.TestCase):
    """ basic tests for the TileButton widget """

    def test_feature_tile_dup_symbol(self):
        values = {'display_price': 'US$ 1.00' }
        mock_property_helper = get_mock_app_properties_helper(values)
        # we don't really need a "doc" on second input as we mock the helper
        button = FeaturedTile(mock_property_helper, None)
        self.assertEqual(
            button.price.get_label(), '<span font_desc="10">US$ 1.00</span>')

    def test_free_price(self):
        values = {'display_price': "Free"}
        mock_property_helper = get_mock_app_properties_helper(values)
        # we don't really need a "doc" on second input as we mock the helper
        button = FeaturedTile(mock_property_helper, None)
        self.assertEqual(
            button.price.get_label(), '<span font_desc="10">Free</span>')


if __name__ == "__main__":
    unittest.main()
