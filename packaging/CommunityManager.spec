# PyInstaller recipe: builds dist/CommunityManager/CommunityManager.exe
# Run from the repository root:  pyinstaller packaging/CommunityManager.spec
from pathlib import Path

root = Path(SPECPATH).parent
pkg = root / "community_manager"

a = Analysis(
    [str(root / "run.py")],
    pathex=[str(root)],
    datas=[
        (str(pkg / "templates"), "community_manager/templates"),
        (str(pkg / "static"), "community_manager/static"),
        (str(pkg / "migrations"), "community_manager/migrations"),
    ],
    hiddenimports=["waitress"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="CommunityManager",
    console=True,  # the window shows the app is running; closing it stops the app
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="CommunityManager")
