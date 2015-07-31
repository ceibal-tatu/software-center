import apt
import datetime
import os
import subprocess
import time
import unittest

from gi.repository import GLib
from tests.utils import (
    DATA_DIR,
    do_events,
    setup_test_env,
)
setup_test_env()

from softwarecenter.db.history_impl.apthistory import AptHistory
from softwarecenter.utils import ExecutionTime


class TestAptHistory(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.join(DATA_DIR, "apt-history")
        apt.apt_pkg.config.set("Dir::Log", self.basedir)
        #apt_pkg.config.set("Dir::Log::History", "./")

    def _get_apt_history(self):
        history = AptHistory(use_cache=False)
        do_events()
        return history

    def test_history(self):
        history = self._get_apt_history()
        self.assertEqual(history.transactions[0].start_date,
                         datetime.datetime.strptime("2010-06-09 14:50:00",
                                                    "%Y-%m-%d  %H:%M:%S"))
        # 186 is from "zgrep Start data/apt-history/history.log*|wc -l"
        #print "\n".join([str(x) for x in history.transactions])
        self.assertEqual(len(history.transactions), 186)

    def test_apthistory_upgrade(self):
        history = self._get_apt_history()
        self.assertEqual(history.transactions[1].upgrade,
                         ['acl (2.2.49-2, 2.2.49-3)'])

    def _glib_timeout(self):
        self._timeouts.append(time.time())
        return True

    def _generate_big_history_file(self, new_history):
        # needs to ensure the date is decreasing, otherwise the rescan
        # code is too clever and skips it
        f = open(new_history,"w")
        date=datetime.date(2009, 8, 2)
        for i in range(1000):
            date -= datetime.timedelta(days=i)
            s="Start-Date: %s 14:00:00\nInstall: 2vcard\nEnd-Date: %s 14:01:00\n\n" % (date, date)
            f.write(s)
        f.close()
        subprocess.call(["gzip", new_history])
        self.addCleanup(os.remove, new_history + ".gz")

    def test_apthistory_rescan_big(self):
        """ create big history file and ensure that on rescan the
            events are still processed
        """
        self._timeouts = []
        new_history = os.path.join(self.basedir, "history.log.2")
        history = self._get_apt_history()
        self.assertEqual(len(history.transactions), 186)
        self._generate_big_history_file(new_history)
        timer_id = GLib.timeout_add(100, self._glib_timeout)
        with ExecutionTime("rescan %s byte file" % os.path.getsize(new_history+".gz")):
            history._rescan(use_cache=False)
        GLib.source_remove(timer_id)
        # verify rescan
        self.assertTrue(len(history.transactions) > 186)
        # check the timeouts
        self.assertTrue(len(self._timeouts) > 0)
        for i in range(len(self._timeouts)-1):
            # check that we get a max timeout of 0.2s
            if abs(self._timeouts[i] - self._timeouts[i+1]) > 0.2:
                raise

    def test_no_history_log(self):
        # set to dir with no existing history.log
        apt.apt_pkg.config.set("Dir::Log", "/")
        # this should not raise
        history = self._get_apt_history()
        self.assertEqual(history.transactions, [])
        apt.apt_pkg.config.set("Dir::Log", self.basedir)

if __name__ == "__main__":
    unittest.main()
