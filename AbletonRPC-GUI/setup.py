from setuptools import setup # type: ignore

APP = ['ableton_rpc.py']
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns', 
    'plist': {
        'CFBundleName': 'AbletonRPC',
        'CFBundleDisplayName': 'AbletonRPC',
        'CFBundleExecutable': 'AbletonRPC', 
        'CFBundleIdentifier': "com.user.ableton-rpc",
        'CFBundleVersion': "2.0.1",
        'CFBundleShortVersionString': "2.0.1",
        'LSUIElement': False, 
    },
    'packages': ['pypresence', 'psutil', 'tkinter'],
    'includes': ['tkinter', 'tkinter.filedialog', 'tkinter.messagebox', 'shutil', 'pathlib', 'subprocess', 'glob', 'tempfile'],
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)