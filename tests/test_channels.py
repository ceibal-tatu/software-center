import unittest

from tests.utils import (
    get_test_db,
    setup_test_env,
)
setup_test_env()


class TestChannels(unittest.TestCase):
    """ tests the channels backend stuff """

    def test_generic(self):
        from softwarecenter.backend.channel import ChannelsManager
        db = get_test_db()
        m = ChannelsManager(db)
        channels = m._get_channels_from_db(installed_only=False)
        self.assertNotEqual(channels, [])
        channels_installed = m._get_channels_from_db(installed_only=True)
        self.assertNotEqual(channels_installed, [])

    def test_aptchannels(self):
        from softwarecenter.backend.channel_impl.aptchannels import (
            AptChannelsManager)
        db = get_test_db()
        m = AptChannelsManager(db)
        channels = m.channels
        self.assertNotEqual(channels, [])
        channels_installed = m.channels_installed_only
        self.assertNotEqual(channels_installed, [])


if __name__ == "__main__":
    unittest.main()
