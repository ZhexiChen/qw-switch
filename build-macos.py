#!/usr/bin/env python3
"""Build the standalone Apple Silicon QW Switch disk image."""
import argparse
import hashlib
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
VERSION = '0.2.0'
PYTHON_ARCHIVE_SHA256 = '4da072af9dbbc2557d3aabf51db553a19694f6ac61b5b7169749e4acfa5a052d'


def build(archive, image):
    with archive.open('rb') as file:
        if hashlib.file_digest(file, 'sha256').hexdigest() != PYTHON_ARCHIVE_SHA256:
            raise SystemExit('Python archive checksum does not match the pinned release')
    if image.exists():
        raise FileExistsError(image)
    image.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='qw-switch-build-') as temp:
        work = Path(temp)
        subprocess.run(['tar', '-xf', str(archive), '-C', temp, 'python/install', 'python/licenses',
                        'python/PYTHON.json'], check=True)
        volume = work / 'volume'
        bundle = volume / 'QW Switch.app'
        contents = bundle / 'Contents'
        resources = contents / 'Resources'
        executables = contents / 'MacOS'
        resources.mkdir(parents=True)
        executables.mkdir()
        (volume / 'Applications').symlink_to('/Applications')
        shutil.move(str(work / 'python/install'), resources / 'Python')
        shutil.move(str(work / 'python/licenses'), resources / 'Third-Party Licenses')
        shutil.move(str(work / 'python/PYTHON.json'), resources / 'Python Build.json')
        for name in ('gateway.py', 'switch_config.py', 'qw-switch.html', 'LICENSE'):
            shutil.copy2(SOURCE / name, resources)
        (contents / 'Info.plist').write_bytes(plistlib.dumps({
            'CFBundleName': 'QW Switch', 'CFBundleDisplayName': 'QW Switch',
            'CFBundleIdentifier': 'local.qw-switch.desktop', 'CFBundlePackageType': 'APPL',
            'CFBundleExecutable': 'QW Switch', 'CFBundleVersion': '2',
            'CFBundleShortVersionString': VERSION, 'LSMinimumSystemVersion': '13.0',
            'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
            'NSHighResolutionCapable': True,
        }))
        subprocess.run(['xcrun', 'swiftc', '-O', '-target', 'arm64-apple-macos13.0',
                        str(SOURCE / 'App.swift'), '-o', str(executables / 'QW Switch')], check=True)
        subprocess.run(['codesign', '--force', '--sign', '-', str(bundle)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
        subprocess.run(['hdiutil', 'create', '-quiet', '-fs', 'HFS+', '-format', 'UDZO', '-volname', 'QW Switch',
                        '-srcfolder', str(volume), str(image)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.python_archive.resolve(), args.output.resolve())
