from setuptools import setup

setup(
    name="CCTokenDashboard",
    app=["app_main.py"],
    data_files=[],
    options={"py2app": {
        "argv_emulation": False,
        "includes": ["cc_token_dashboard"],
        "packages": ["rumps"],
        "plist": {
            "CFBundleName": "CC Token 儀表板",
            "CFBundleDisplayName": "CC Token 儀表板",
            "CFBundleIdentifier": "cc.watermansports.tokendashboard",
            "CFBundleShortVersionString": "1.0",
            "CFBundleVersion": "1.0",
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    }},
    setup_requires=["py2app"],
)
