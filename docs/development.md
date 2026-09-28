# Development

Python engine:

```bash
python -m venv venv
source venv/bin/activate
python -m pip install -e '.[all]'
python -m pytest -q
uvicorn engine.api:app --host 127.0.0.1 --port 47821
```

Desktop UI:

```bash
cd desktop
npm install
npm run dev
npm run build
```

Tauri development requires the platform prerequisites documented by Tauri 2. The production sidecar is built separately per target OS and architecture; a Linux executable cannot be copied into Windows or macOS bundles.
