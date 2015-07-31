import unittest

from gi.repository import (
    GLib,
    Gtk,
    )

from tests.utils import (
    setup_test_env,
)
setup_test_env()

from softwarecenter.ui.gtk3.widgets.containers import (
    FramedHeaderBox,
    )
from softwarecenter.ui.gtk3.widgets.viewport import Viewport


def add_tiles(tile_grid):
    print "add_tiles"
    for i in range(10):
        b = Gtk.Button("tile %i" % i)
        b.show()
        tile_grid.pack_start(b, False, False, 0)
    print "/add_tiles"


class CatviewTestCase(unittest.TestCase):
    """This adds a test for the drawing artifact bug #1048912 

    Note that the bug is not fixed yet 
    """

    def test_visual_glitch_lp1048912(self):
        win = Gtk.Window()
        win.set_size_request(500, 300)

        scroll = Gtk.ScrolledWindow()
        win.add(scroll)

        viewport = Viewport()
        scroll.add(viewport)

        top_hbox = Gtk.HBox()
        viewport.add(top_hbox)

        right_column = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        top_hbox.pack_start(right_column, True, True, 0)

        apptiles = Gtk.VBox()
        apptiles_frame = FramedHeaderBox()
        apptiles_frame.set_name("apptiles top")
        apptiles_frame.set_header_label("Frame1")
        apptiles_frame.add(apptiles)
        right_column.pack_start(apptiles_frame, True, True, 0)
        apptiles_frame.header_implements_more_button()

        apptiles2 = Gtk.VBox()
        apptiles2_frame = FramedHeaderBox()
        apptiles2_frame.set_name("apptiles bottom")
        apptiles2_frame.set_header_label("Frame2")
        apptiles2_frame.add(apptiles2)
        right_column.pack_start(apptiles2_frame, True, True, 0)
        apptiles2_frame.header_implements_more_button()

        # this delayed adding of the tiles causes a visual glitch like
        # described in #1048912 on the top of the bottom frame the line
        # will not be drawn correctly - any subsequent redraw of the
        # window will fix it
        GLib.timeout_add(1000, add_tiles, apptiles2)

        # this "viewport.queue_draw()" will fix the glitch
        #GLib.timeout_add_seconds(2, lambda: viewport.queue_draw())

        # stop the test
        GLib.timeout_add_seconds(3, Gtk.main_quit)

        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        Gtk.main()

if __name__ == "__main__":
    unittest.main()
