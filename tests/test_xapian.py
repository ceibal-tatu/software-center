import os
import platform
import unittest
import xapian

from mock import Mock, patch

from tests.utils import (
    REAL_DATA_DIR,
    setup_test_env,
)
setup_test_env()

from softwarecenter.enums import XapianValues, CustomKeys
from softwarecenter.db.update import rebuild_database


class TestXapian(unittest.TestCase):
    """ tests the xapian database """

    def setUp(self):
        # FIXME: create a fixture DB instead of using the system one
        # but for now that does not matter that much, only if we
        # call open the db is actually read and the path checked
        pathname = os.path.join(REAL_DATA_DIR, "xapian")
        if not os.path.exists(pathname):
            os.makedirs(pathname)
        if not os.listdir(pathname):
            rebuild_database(pathname)
        self.xapiandb = xapian.Database(pathname)
        self.enquire = xapian.Enquire(self.xapiandb)

    def test_exact_query(self):
        query = xapian.Query("APsoftware-center")
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertEqual(len(matches), 1)

    def test_search_term(self):
        search_term = "apt"
        parser = xapian.QueryParser()
        query = parser.parse_query(search_term)
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) > 5)

    def test_category_query(self):
        query = xapian.Query("ACaudiovideo")
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) > 5)

    def test_mime_query(self):
        query = xapian.Query("AMtext/html")
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) > 5)
        pkgs = set()
        for match in matches:
            doc = match.document
            pkgs.add(doc.get_value(XapianValues.PKGNAME))
        self.assertTrue("firefox" in pkgs)

    def test_eset(self):
        """ test finding "similar" items than the ones found before """
        query = xapian.Query("foo")
        self.enquire.set_query(query)
        # this yields very few results
        matches = self.enquire.get_mset(0, 100)
        # create a relevance set from the query
        rset = xapian.RSet()
        #print "original finds: "
        for match in matches:
            #print match.document.get_data()
            rset.add_document(match.docid)
        # and use that to get a extended set
        eset = self.enquire.get_eset(20, rset)
        #print eset
        # build a query from the eset
        eset_query = xapian.Query(xapian.Query.OP_OR, [e.term for e in eset])
        self.enquire.set_query(eset_query)
        # ensure we have more results now than before
        eset_matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) < len(eset_matches))
        #print "expanded finds: "
        #for match in eset_matches:
        #    print match.document.get_data()

    def test_spelling_correction(self):
        """ test automatic suggestions for spelling corrections """
        parser = xapian.QueryParser()
        parser.set_database(self.xapiandb)
        # mispelled search term
        search_term = "corect"
        query = parser.parse_query(
            search_term, xapian.QueryParser.FLAG_SPELLING_CORRECTION)
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertEqual(len(matches), 0)
        corrected_query_string = parser.get_corrected_query_string()
        self.assertEqual(corrected_query_string, "correct")
        # set the corrected one
        query = parser.parse_query(corrected_query_string)
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        #print len(matches)
        self.assertTrue(len(matches) > 0)


class AptXapianIndexTestCase(unittest.TestCase):

    # this will fail on precise so we skip the test there
    @unittest.skipIf(platform.dist()[2] == "precise" and
                     not os.path.exists("/var/lib/apt-xapian-index/index"),
                     "Need populated apt-xapian-index for this test")
    def test_wildcard_bug1025579_workaround(self):
        db = xapian.Database("/var/lib/apt-xapian-index/index")
        enquire = xapian.Enquire(db)
        parser = xapian.QueryParser()
        parser.set_database(db)
        # this is the gist, the mangled version of the XPM term
        parser.add_prefix("pkg_wildcard", "XPM")
        parser.add_prefix("pkg_wildcard", "XP")
        parser.add_prefix("pkg_wildcard", "AP")
        s = 'pkg_wildcard:unity_lens_*'
        query = parser.parse_query(s, xapian.QueryParser.FLAG_WILDCARD)
        enquire.set_query(query)
        mset = enquire.get_mset(0, 100)
        for m in mset:
            self.assertTrue(m.document.get_data().startswith("unity-lens-"))
        self.assertNotEqual(len(mset), 0)


class XapianPluginsTestCase(unittest.TestCase):

    def make_mock_document(self):
        doc = Mock()
        return doc

    def make_mock_package(self):
        pkg = Mock()
        ver = Mock()
        ver.uri = "http://archive.ubuntu.com/foo.deb"
        ver.record = {}
        for varname in vars(CustomKeys):
            key = getattr(CustomKeys, varname)
            ver.record[key] = "custom-%s" % key
        pkg.candidate = ver
        pkg.name = "meep"
        return pkg

    def test_xapian_plugin_sc(self):
        from apt_xapian_index_plugin.software_center import (
            SoftwareCenterMetadataPlugin)
        plugin = SoftwareCenterMetadataPlugin()
        plugin.init(info=None, progress=None)
        # mock the indexer
        with patch.object(plugin, "indexer") as mock_indexer:
            # make mock document 
            doc = self.make_mock_document()
            # ... and mock pkg/version
            pkg = self.make_mock_package()
            # go for it
            plugin.index(doc, pkg)
            # check that we got the expected calls
            doc.add_term.assert_any_call("AA"+"custom-AppName")
            # indexer
            mock_indexer.index_text_without_positions.assert_called()
            # check the xapian values calls
            expected_values = set([
                    XapianValues.APPNAME, XapianValues.ICON,
                    XapianValues.SCREENSHOT_URLS, XapianValues.THUMBNAIL_URL])
            got_values = set()
            for args, kwargs in doc.add_value.call_args_list:
                got_values.add(args[0])
            self.assertTrue(expected_values.issubset(got_values))


if __name__ == "__main__":
    unittest.main()
