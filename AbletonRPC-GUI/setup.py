"""
Setup script for creating macOS app bundle with py2app
"""

from setuptools import setup #type: ignore

APP = ['ableton_rpc.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',  # This tells py2app to use the icon
    'plist': {
        'CFBundleName': 'AbletonRPC',
        'CFBundleDisplayName': 'AbletonRPC',
        'CFBundleGetInfoString': "Ableton Live Discord Rich Presence",
        'CFBundleIdentifier': "com.user.ableton-rpc",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHumanReadableCopyright': "Copyright © 2024",
        'LSUIElement': False,  # Set to True to hide from Dock, False to show
        'LSBackgroundOnly': False,
    },
    'packages': ['pypresence', 'psutil', 'tkinter'],
    'includes': ['tkinter', 'tkinter.filedialog', 'tkinter.messagebox'],
}

setup(
    app=APP,
    name='AbletonRPC',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)