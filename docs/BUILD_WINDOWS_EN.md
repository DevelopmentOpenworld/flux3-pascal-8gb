# Build Windows Manager

Users of the ready-made EXE do not need these steps. Build on Windows x64. Tested: Python 3.14.4 x64, Tcl/Tk 8.6.15 and PyInstaller 6.22.3. Build dependencies are pinned in `desktop/build-requirements.txt`; a separate build environment does not modify CUDA or other projects.

```powershell
python -m venv .build-env
.build-env/Scripts/python.exe -m pip install -r desktop/build-requirements.txt
.build-env/Scripts/python.exe -B -m unittest discover -s tests -v
.build-env/Scripts/python.exe desktop/build_windows.py --output dist --work .build-work
```

The result is the entire `dist/FLUX3-Manager` folder, including `_internal`. Zip the whole folder. Weights, the engine, CUDA, user configuration, sessions, logs and the 39-image corpus are excluded from the EXE.

A working Python installation with Tcl/Tk is required. A successful PyInstaller exit alone is insufficient. Preview 0.1.1-preview has programmatic checks of translations, settings and the actual EXE server lifecycle; no native window was opened. Native layout and system dialog behavior remain unverified preview limitations.

The shared translations are in `ui/messages.json`; browser logic is in `ui/app.js`. The whole `ui` folder is bundled. Optional DOM checks use Node.js 24 and jsdom 30.0.1, then `node tests/ui_languages.cjs`. jsdom is a test-only dependency, not an app dependency.

Use `FLUX3-Manager.exe --settings-dir <separate-folder>` for an isolated manual setup. The app uses `--server` and `--generate-worker` internally. `--worker-check <result.json>` checks bundled imports, resources and languages without opening a window or running a model. Sources and EXE must be from the same version.

Byte-for-byte deterministic EXE rebuilds are not claimed. A concrete release is pinned by SHA256 and a file manifest in `desktop/release.json`. Source changes require a new build and new checks.

The builder now rejects unavailable Tcl before running PyInstaller and rejects missing Tcl/Tk files after collection. Both checks create no window.

```powershell
npm install --prefix "$env:TEMP/flux3-ui-tests" --no-audit --no-fund jsdom@30.0.1
$env:NODE_PATH = "$env:TEMP/flux3-ui-tests/node_modules"
node tests/ui_languages.cjs
```
