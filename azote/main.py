import os
import sys
import i3ipc
import common
import gi
from PIL import Image

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf, Gdk
from tools import set_env, log, hash_name, create_thumbnails, file_allowed


class Preview(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()

        self.set_border_width(0)
        self.set_size_request(0, 500)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)

        common.buttons_list = []
        self.grid = Gtk.Grid()

        create_thumbnails(common.settings.src_path)

        col = 0
        row = 0
        src_pictures = [f for f in os.listdir(common.settings.src_path) if
                        os.path.isfile(os.path.join(common.settings.src_path, f))]

        for file in src_pictures:
            if file_allowed(file):
                btn = ThumbButton(common.settings.src_path, file)
                common.buttons_list.append(btn)
                self.grid.attach(btn, col, row, 1, 1)
                if col < common.cols - 1:
                    col += 1
                else:
                    col = 0
                    row += 1

        self.add_with_viewport(self.grid)

    def refresh(self, create_thumbs=True):
        if create_thumbs:
            create_thumbnails(common.settings.src_path)

        for button in common.buttons_list:
            self.grid.remove(button)
            button.destroy()

        col = 0
        row = 0
        src_pictures = [f for f in os.listdir(common.settings.src_path) if
                        os.path.isfile(os.path.join(common.settings.src_path, f))]

        for file in src_pictures:
            if file_allowed(file):
                btn = ThumbButton(common.settings.src_path, file)
                common.buttons_list.append(btn)
                self.grid.attach(btn, col, row, 1, 1)
                if col < common.cols - 1:
                    col += 1
                else:
                    col = 0
                    row += 1
                btn.show()


class ThumbButton(Gtk.Button):
    def __init__(self, folder, filename):
        super().__init__()

        self.set_property("name", "thumb-btn")

        self.filename = filename
        self.source_path = os.path.join(folder, filename)

        img = Gtk.Image()
        self.thumb_file = "{}.png".format(os.path.join(common.thumb_dir, hash_name(self.source_path)))
        img.set_from_file(self.thumb_file)

        self.set_image(img)
        self.set_image_position(2)  # TOP

        if len(filename) > 30:
            filename = '…{}'.format(filename[-28::])
        self.set_label(filename)
        self.selected = False

        self.connect('clicked', self.select)

    def select(self, button):
        self.selected = True
        common.selected_wallpaper = self
        deselect_all()
        button.set_property("name", "thumb-btn-selected")

        with Image.open(self.source_path) as img:
            common.selected_picture_label.set_text("{}    ({} x {})".format(self.filename, img.size[0], img.size[1]))

    def deselect(self, button):
        self.selected = False
        button.set_property("name", "thumb-btn")


def deselect_all():
    for btn in common.buttons_list:
        btn.deselect(btn)


class DisplayBox(Gtk.Box):
    """
    The box contains elements to preview certain displays and assign wallpapers to them
    """
    def __init__(self, display_name):
        super().__init__()

        self.set_orientation(Gtk.Orientation.VERTICAL)

        self.img = Gtk.Image()
        self.img.set_from_file("images/empty.png")

        self.set_button = Gtk.Button()
        self.set_button.set_label(display_name)                 # label on top: name (with x height)
        self.set_button.set_image(self.img)                     # preview of selected wallpaper
        self.set_button.set_image_position(3)                   # label on top, image below
        self.set_button.set_property("name", "display-btn")     # to assign css style

        self.pack_start(self.set_button, False, False, 10)

        self.set_button.connect_after('clicked', self.select_btn)

        # Combo box to choose the image position
        img_position_selector = Gtk.ListStore(str)
        options = ["stretch", "fit", "fill", "center", "tile"]
        for option in options:
            img_position_selector.append([option])

        img_pos_combo = Gtk.ComboBox.new_with_model(img_position_selector)
        img_pos_combo.set_active(2)
        img_pos_combo.connect("changed", self.on_country_combo_changed)
        renderer_text = Gtk.CellRendererText()
        img_pos_combo.pack_start(renderer_text, True)
        img_pos_combo.add_attribute(renderer_text, "text", 0)
        self.pack_start(img_pos_combo, False, False, True)

    def select_btn(self, button):
        if common.selected_wallpaper:
            self.img.set_from_file(common.selected_wallpaper.thumb_file)
            button.set_property("name", "display-btn-selected")

    def on_country_combo_changed(self, combo):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            country = model[tree_iter][0]
            print("Selected: country=%s" % country)


class GUI:
    def __init__(self, displays):

        window = Gtk.Window()

        window.set_title("Azote")
        window.set_wmclass("azote", "azote")

        window.connect_after('destroy', self.destroy)

        main_box = Gtk.Box()
        main_box.set_spacing(15)
        main_box.set_border_width(10)
        main_box.set_orientation(Gtk.Orientation.VERTICAL)
        window.add(main_box)

        # This contains a Gtk.ScrolledWindow with Gtk.Grid() inside, filled with ThumbButton(Gtk.Button) instances
        common.preview = Preview()
        window.connect('configure-event', on_configure_event)

        main_box.pack_start(common.preview, False, False, 0)

        # Label to display details of currently selected picture
        common.selected_picture_label = Gtk.Label()
        common.selected_picture_label.set_text('Select a picture')

        main_box.pack_start(common.selected_picture_label, False, False, 0)

        # Button to set the wallpapers folder
        folder_button = Gtk.Button(common.settings.src_path)
        main_box.pack_start(folder_button, False, False, 0)

        folder_button.connect_after('clicked', self.on_folder_clicked)

        # We need a horizontal container to display outputs in columns
        displays_box = Gtk.Box()
        displays_box.set_spacing(15)
        displays_box.set_orientation(Gtk.Orientation.HORIZONTAL)
        window.add(main_box)

        for display in displays:
            # Label format: name (width x height)
            display_box = DisplayBox(
                "{} ({} x {})".format(display.get('name'), display.get('width'), display.get('height')))
            displays_box.pack_start(display_box, True, False, 0)

        main_box.pack_start(displays_box, False, False, 0)

        window.show_all()

    def destroy(window, self):
        Gtk.main_quit()

    def on_folder_clicked(self, button):
        dialog = Gtk.FileChooserDialog("Open Image", button.get_toplevel(), Gtk.FileChooserAction.SELECT_FOLDER);
        dialog.add_button(Gtk.STOCK_CANCEL, 0)
        dialog.add_button(Gtk.STOCK_OK, 1)
        dialog.set_default_response(1)
        dialog.set_default_size(300, 300)

        response = dialog.run()
        if response == 1:
            common.settings.src_path = dialog.get_filename()
            common.settings.save()
            common.preview.refresh()
            button.set_label(common.settings.src_path)

        dialog.destroy()


def check_displays():
    displays = []
    try:
        i3 = i3ipc.Connection()
        common.outputs = i3.get_outputs()
        for output in common.outputs:
            if output.active:  # dunno WTF xroot-0 is: i3 returns such an output with "active":false
                display = {'name': output.name,
                           'x': output.rect.x,
                           'y': output.rect.y,
                           'width': output.rect.width,
                           'height': output.rect.height}
                displays.append(display)
                log("Output: {}".format(display), common.INFO)

        """"# for testing
        display = {'name': 'HDMI-A-2',
                   'x': 0,
                   'y': 0,
                   'width': 1920,
                   'height': 1080}
        displays.append(display)
        log("Output: {}".format(display), common.INFO)

        display = {'name': 'HDMI-A-3',
                   'x': 0,
                   'y': 0,
                   'width': 1920,
                   'height': 1080}
        displays.append(display)
        log("Output: {}".format(display), common.INFO)

        display = {'name': 'HDMI-A-4',
                   'x': 1366,
                   'y': 728,
                   'width': 1920,
                   'height': 1080}
        displays.append(display)
        log("Output: {}".format(display), common.INFO)"""

        return displays
    except Exception as e:
        log(e, common.ERROR)
        return None


def on_configure_event(window, e):
    cols = e.width // 256
    if cols != common.cols:
        common.preview.hide()
        if cols != common.cols:
            common.cols = cols
            common.preview.refresh(False)

        # window.reshow_with_initial_size()

        common.preview.show()
        print("Refresh!")
    print('I have resized:', e.width, cols)


def main():
    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    css = b"""
            button#thumb-btn {
                background-color: #fefefe;
                font-weight: normal;
                font-size: 11px;
            }
            button#thumb-btn-selected {
                background-color: #66ccff;
                font-weight: bold;
                font-size: 12px;
            }
            button#display-btn {
                font-weight: normal;
                font-size: 12px;
            }
            button#display-btn-selected {
                font-weight: bold;
                font-size: 12px;
            }
            """
    provider.load_from_data(css)

    set_env()  # set paths and stuff
    displays = check_displays()
    common.cols = len(displays) if len(displays) > 3 else 3
    app = GUI(displays)
    Gtk.main()


if __name__ == "__main__":
    sys.exit(main())
