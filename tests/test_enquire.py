import time
import unittest
import xapian

from tests.utils import (
    get_test_db,
    get_test_pkg_info,
    setup_test_env,
)
setup_test_env()
from softwarecenter.db.appfilter import AppFilter
from softwarecenter.db.enquire import AppEnquire


class TestEnquire(unittest.TestCase):

    def test_app_enquire(self):
        db = get_test_db()
        cache = get_test_pkg_info()

        xfilter = AppFilter(cache, db)
        enquirer = AppEnquire(cache, db)
        terms = [ "app", "this", "the", "that", "foo", "tool", "game",
                  "graphic", "ubuntu", "debian", "gtk", "this", "bar",
                  "baz"]

        # run a bunch of the queries in parallel
        for nonblocking in [False, True]:
            for i in range(10):
                for term in terms:
                    enquirer.set_query(
                        search_query=xapian.Query(term),
                        limit=0,
                        filter=xfilter,
                        nonblocking_load=nonblocking)
        # give the threads a bit of time
        time.sleep(5)


if __name__ == "__main__":
    unittest.main()
