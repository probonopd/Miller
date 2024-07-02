import os
import win32com.client  # Make sure to install pywin32

def get_file_properties(file_path):
    """
    Retrieves properties of a file specified by file_path using Shell.Application.

    Args:
        file_path (str): The path to the file whose properties are to be retrieved.

    Returns:
        dict: A dictionary mapping property indices to tuples of (attribute_name, attribute_value).
    """
    print(f"Getting properties for {file_path}")
    file_path = file_path.replace("/", "\\")
    properties = {}

    try:
        shell = win32com.client.Dispatch("Shell.Application")
        namespace = shell.NameSpace(os.path.dirname(file_path))
        item = namespace.ParseName(os.path.basename(file_path))

        # Invoke the system properties dialog
        item.InvokeVerb("properties")

        # Fetching up to 100 because that's where typical file properties are
        for i in range(100):
            attr_name = namespace.GetDetailsOf(None, i)
            if attr_name:
                attr_value = namespace.GetDetailsOf(item, i)
                properties[i] = (attr_name, attr_value)

    except AttributeError as e:
        print(f"AttributeError: {e}")
    except pywintypes.com_error as e:
        print(f"COM Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    return properties

if __name__ == "__main__":
    PATH = r"C:\Windows\System32\notepad.exe"
    properties = get_file_properties(PATH)
    print(properties)
