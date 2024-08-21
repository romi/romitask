def get_version():
    """Return used ROMI libraries version."""
    import importlib
    from importlib.metadata import version
    from importlib.metadata import PackageNotFoundError
    hash_dict = {}
    for package in ["dtw", "plant3dvision", "plantdb", "plantimager", "romicgal", "romiseg", "romitask"]:
        try:
            module = importlib.import_module(package)
        except ModuleNotFoundError or PackageNotFoundError:
            hash_dict[package] = "Not Installed"
        else:
            try:
                hash_dict[package] = version(package)
            except AttributeError:
                hash_dict[package] = "Undefined"
            except PackageNotFoundError:
                hash_dict[package] = "Not Installed"

    return hash_dict


def parse_kbdi(kbdi, default='n'):
    """Method to handle keyboard input from user."""
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if kbdi == '':
        return valid[default]
    else:
        return valid[kbdi]
