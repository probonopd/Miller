# Rename a partition/volume on Windows

import wmi # pip install wmi

def rename_volume(drive_letter, new_name):
    c = wmi.WMI()
    for volume in c.Win32_Volume():
        if volume.DriveLetter == drive_letter + ":":
            volume.Label = new_name
            volume.Put_()
            print(f"Volume {drive_letter}: renamed to {new_name}")
            return True
    return False

def main():
    drive_letter = "E"
    new_name = "MiniDexed"
    # rename_volume(drive_letter, new_name)

if __name__ == "__main__":
    main()