# Releasing

The Tauri configuration declares AppImage, DEB, DMG, and NSIS targets. A release pipeline still needs to build the Python sidecar for each runner, rename it to the Tauri external-binary target triple, and sign artifacts with CI-held credentials.

Tagged releases use `.github/workflows/release.yml`. The workflow runs Python tests and the frontend build, freezes the engine on each runner, stages the target-triple sidecar, builds the native installer, renames artifacts, and publishes SHA256 checksums. Signing hooks read optional GitHub secrets and remain disabled when secrets are absent.

Local packaging commands after the sidecar is present:

```bash
cd desktop
npm run build
npm run tauri build
```

Windows produces an NSIS installer, macOS a DMG, and Linux AppImage/DEB according to the host target. Signing and update manifests must be configured before publishing.

Local sidecar example:

```bash
python -m pip install pyinstaller
pyinstaller --clean --onefile --name nl2sql-engine engine/server.py
mkdir -p desktop/src-tauri/binaries
cp dist/nl2sql-engine desktop/src-tauri/binaries/nl2sql-engine-$(rustc -vV | sed -n 's/^host: //p')
cd desktop && npm run tauri build
```
