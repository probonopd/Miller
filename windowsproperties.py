import os
import win32com.client # pip install pywin32

def get_file_properties(file_path):
    print(f"Getting properties for {file_path}")
    # Replace / with \ in the path
    file_path = file_path.replace("/", "\\")
    properties = {}
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        namespace = shell.NameSpace(os.path.dirname(file_path))
        item = namespace.ParseName(os.path.basename(file_path))

        item.InvokeVerb("properties") # Does open the properties dialog

        # So, we are getting the individual properties instead to construct our own dialog
        # similar to https://github.com/Muratxx5/File_Attributes/blob/d28a58c955feb36324c4eb28228c32e24fb78f27/File_Attributes.py#L8
        
        # Mapping indices from 1 to 100
        details_mapping = {}
        for i in range(1, 501):
            attr_name = namespace.GetDetailsOf(None, i)
            if attr_name:
                details_mapping[i] = attr_name

        for index, attribute in details_mapping.items():
            attr_value = namespace.GetDetailsOf(item, index)
            properties[index] = (attribute, attr_value)
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return properties

if __name__ == "__main__":
    # Example usage
    path = r"C:\Windows\System32\notepad.exe"
    props = get_file_properties(path)
    print(props)