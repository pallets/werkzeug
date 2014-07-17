from . import bar
if bar.first_import:
    bar.first_import = False
    raise AttributeError("Test")
else:
    pass
