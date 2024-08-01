import os

def is_appdir(path):
    return (
        os.path.isdir(path)
        and path.endswith(".AppDir")
        and ( os.path.exists(os.path.join(path, "AppRun")) or os.path.exists(os.path.join(path, "AppRun.bat")))
        and ( os.access(os.path.join(path, "AppRun"), os.X_OK) or os.access(os.path.join(path, "AppRun.bat"), os.X_OK))
    )

class AppDir(object):
    def __init__(self, path):
        self.path = os.path.normpath(path)

    def is_valid(self):
        """Check if the given path is a valid AppDir"""
        return is_appdir(self.path)

    def get_icon_path(self):
        """Get the path to the application icon"""
        icon_path = os.path.join(self.path, ".DirIcon")
        if os.path.exists(icon_path):
            return icon_path
        else:
            return None

    def get_apprun_path(self):
        """Get the path to the AppRun file"""
        apprun_path = os.path.join(self.path, "AppRun")
        if os.path.exists(apprun_path):
            return apprun_path
        elif os.path.exists(apprun_path + ".bat"):
            return apprun_path + ".bat"
        else:
            return None
