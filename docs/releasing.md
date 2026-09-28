# Releasing

The Tauri configuration declares AppImage, DEB, DMG, and NSIS targets. A release pipeline still needs to build the Python sidecar for each runner, rename it to the Tauri external-binary target triple, and sign artifacts with CI-held credentials.

Local packaging commands after the sidecar is present:

```bash
cd desktop
npm run build
npm run tauri build
```

Windows produces an NSIS installer, macOS a DMG, and Linux AppImage/DEB according to the host target. Signing and update manifests must be configured before publishing.
