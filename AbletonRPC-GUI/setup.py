"""
Setup script for creating macOS app bundle with py2app
"""

from setuptools import setup # type: ignore

APP = ['ableton_rpc.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns', 
    'plist': {
        'CFBundleName': 'AbletonRPC',
        'CFBundleDisplayName': 'AbletonRPC',
        'CFBundleExecutable': 'AbletonRPC', 
        'CFBundleGetInfoString': "Ableton Live Discord Rich Presence",
        'CFBundleIdentifier': "com.user.ableton-rpc",
        'CFBundleVersion': "1.0.3",
        'CFBundleShortVersionString': "1.0.3",
        'NSHumanReadableCopyright': "Copyright © 2025",
        'LSUIElement': False, 
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
    },
    'packages': ['pypresence', 'psutil', 'tkinter'],
    'includes': ['tkinter', 'tkinter.filedialog', 'tkinter.messagebox', 'shutil', 'pathlib'],
    'semi_standalone': False, 
    'site_packages': True,
}

setup(
    app=APP,
    name='AbletonRPC',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)