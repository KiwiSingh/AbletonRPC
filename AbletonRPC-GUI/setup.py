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
        'CFBundleVersion': "1.0.8",
        'CFBundleShortVersionString': "1.0.8",
        'LSUIElement': False, 
    },
    'packages': ['pypresence', 'psutil', 'tkinter'],
    'includes': ['tkinter', 'tkinter.filedialog', 'tkinter.messagebox', 'shutil', 'pathlib', 'subprocess', 'glob'],
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)