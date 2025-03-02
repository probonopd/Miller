import os, sys
from PyQt6 import QtGui, QtCore, QtWidgets

class Styling:
    _instance = None

    def __new__(cls, app):
        if cls._instance is None:
            cls._instance = super(Styling, cls).__new__(cls)
        else:
            if cls._instance.app != app:
                raise Exception("Styling instance already exists with a different QApplication")
        cls._instance.init(app)
        return cls._instance

    def init(self, app):
        self.app = app
        self.apply_styling()
        self.setup_icon_theme()

    def resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            rp = os.path.join(sys._MEIPASS, relative_path)
        else:
            rp = os.path.join(os.path.dirname(__file__), relative_path)
            if sys.platform == "win32":
                rp = rp.replace("/", "\\")
        print("Resource path:", rp)
        return rp

    def apply_styling(self):
        app = self.app
        app.setStyle("Fusion")

        if not sys.platform == "win32":
            # Load the custom fonts
            font_paths = {
                "regular": self.resource_path("fonts/Inter-Regular.ttf"),
                "bold": self.resource_path("fonts/Inter-Bold.ttf"),
                "italic": self.resource_path("fonts/Inter-Italic.ttf"),
                "bold_italic": self.resource_path("fonts/Inter-BoldItalic.ttf"),
            }

            # Load each font and set it in the application
            fonts = {}
            missing_fonts = []
            for style, path in font_paths.items():
                font_id = QtGui.QFontDatabase.addApplicationFont(path)
                if font_id == -1:
                    missing_fonts.append(style)
                else:
                    font_families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        fonts[style] = font_families[0]  # Store the family name

            # Show a dialog if any fonts are missing
            if missing_fonts:
                missing_fonts_str = ", ".join(missing_fonts)
                msg_box = QtWidgets.QMessageBox()
                msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
                msg_box.setText("Missing Fonts")
                msg_box.setInformativeText(
                    f"Oops! It looks like the following fonts are missing: {missing_fonts_str}.\n\n"
                    "Please download the 'Inter' font family from the following link:\n"
                    "https://fonts.google.com/specimen/Inter\n\n"
                    "After downloading, place the font files in the 'fonts' directory located in the same folder as your script.\n\n"
                    "" + self.resource_path("fonts")
                )
                msg_box.setWindowTitle("Font Error")
                msg_box.exec()

            # Set the default font
            if "regular" in fonts:
                default_font = QtGui.QFont(fonts["regular"], 9)  # Use the regular font
                app.setFont(default_font)

            # Create font instances for bold, italic, and bold-italic
            if "bold" in fonts:
                bold_font = QtGui.QFont(fonts["bold"], 9, QtGui.QFont.Weight.Bold)
            if "italic" in fonts:
                italic_font = QtGui.QFont(fonts["italic"], 9, QtGui.QFont.Weight.Normal, True)
            if "bold_italic" in fonts:
                bold_italic_font = QtGui.QFont(fonts["bold_italic"], 9, QtGui.QFont.Weight.Bold, True)

        # Set highlight color for selected items to blue
        palette = app.palette()
        palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(64, 64, 255))
        app.setPalette(palette)

        # 0px window border in red
        app.setStyleSheet("QMainWindow { border: 0px; }")

    def setup_icon_theme(self):
        # Set icon theme
        icon_theme_path = self.resource_path("icons/")
        # Check if the icon theme path exists
        if not os.path.exists(icon_theme_path):
            print(f"Icon theme path does not exist: {icon_theme_path}")

        # Check that it contains a folder named elementary-xfce that contains index.theme; if not, show a dialog
        if not os.path.exists(os.path.join(icon_theme_path, "elementary-xfce", "index.theme")):
            msg_box = QtWidgets.QMessageBox()
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg_box.setText("Missing Icon Theme")
            msg_box.setInformativeText(
                "Oops! It looks like the icon theme is missing.\n\n"
                "Please download the 'elementary-xfce' icon theme from the following link:\n"
                "http://archive.ubuntu.com/ubuntu/pool/universe/x/xubuntu-artwork/xubuntu-artwork_16.04.2.tar.xz\n"
                "and extract 'elementary-xfce' to the 'icons' directory located in the same folder as your script.\n\n"
                "" + self.resource_path("icons")
            )
            msg_box.setWindowTitle("Icon Theme Error")
            msg_box.exec()

        # qicon_instance = QtGui.QIcon()
        QtGui.QIcon.setThemeSearchPaths([icon_theme_path])
        QtGui.QIcon.setThemeName("elementary-xfce")
        
        available_fallback_themes = []
        if os.path.exists("/usr/share/icons"):
            available_fallback_themes += [d for d in os.listdir("/usr/share/icons") if os.path.isdir(os.path.join("/usr/share/icons", d))]
        if os.path.exists("/usr/local/share/icons"):
            available_fallback_themes += [d for d in os.listdir("/usr/local/share/icons") if os.path.isdir(os.path.join("/usr/local/share/icons", d))]
        print(f"Available fallback themes: {available_fallback_themes}")
        QtGui.QIcon.setThemeSearchPaths(QtGui.QIcon.themeSearchPaths() + ["/usr/share/icons", "/usr/local/share/icons"] + [os.path.join("/usr/share/icons", d) for d in available_fallback_themes])
        QtGui.QIcon.setFallbackThemeName("hicolor")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    s = Styling(app)
    # Make a window with an icon to test the icon theme
    window = QtWidgets.QMainWindow()
    window.setWindowIcon(QtGui.QIcon.fromTheme("folder"))
    # Add a widget to the window containing an icon
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    label = QtWidgets.QLabel()
    label.setPixmap(QtGui.QIcon.fromTheme("folder").pixmap(128, 128))
    layout.addWidget(label)
    window.setCentralWidget(widget)

    window.show()

    app.lastWindowClosed.connect(app.quit)
    app.exec()
