# Install, launch and generate through the interface

**Preview 0.1.1-preview:** the server, translations and bundled worker resources were checked programmatically; no new GPU generations were run in this update. Native buttons, folder-selection dialogs and the full installation workflow through the native window remain unverified; installation on a clean machine was not tested. The app supports Russian and English.

## For Windows users

1. Extract the **entire** [FLUX3-Manager-Windows-x64.zip](https://github.com/DevelopmentOpenworld/flux3-pascal-8gb/releases/download/v0.1.1-preview/FLUX3-Manager-Windows-x64.zip) archive to a convenient folder. Double-click **FLUX3-Manager.exe**. Keep `_internal` beside it: this contains Python, window libraries and app data. This route does not require CMD, PowerShell or a separate Python installation.
2. Under **Storage folder («Где хранить скачанные файлы»)**, choose a folder with roughly 10 GiB free space. The engine and three models total about 6.23 GiB of downloads; without existing CUDA, about 411 MiB of downloads plus extracted libraries are added.
3. For existing files, use **Browse… («Обзор…»)** to select the folder containing `sd-cli.exe` and its DLLs, the FLUX.3 model, Qwen, VAE and the CUDA folder or its `bin`. Exact versions are pinned in `assets.lock.json`. CUDA 12 is detected automatically when the required DLLs are present. Selected files are used in place without copying.
4. For missing files, leave the corresponding fields empty and choose **Download missing files («Скачать недостающее»)**. The engine comes from GitHub, models from Hugging Face and CUDA Runtime/cuBLAS from NVIDIA. The current filename, byte count and SHA256 verification are shown. **Cancel download («Отменить загрузку»)** retains the accepted partial download. Retrying resumes it when HTTP Range is supported; otherwise that file restarts.
5. For existing files, choose **Check and save («Проверить и сохранить»)**. Model sizes/SHA256 and the pinned engine file set are verified. CUDA is checked for `cudart64_12.dll`, `cublas64_12.dll` and `cublasLt64_12.dll`; this is not a performance test. Checks run automatically after downloads.
6. Choose **Start server («Запустить сервер»)** to open the browser generator. **Open generator («Открыть генератор»)** returns to the tab. **Stop server («Остановить сервер»)** stops the server and its current generation. Closing the Manager also stops its own server. Closing only the browser tab leaves the server running.

Settings are saved in `%LOCALAPPDATA%/FLUX3Pascal`; downloads go to the selected folder. Existing CUDA is reused. If unavailable, local CUDA 12.6.3 libraries are downloaded without changing the system Toolkit, PATH or driver. A working NVIDIA driver is required.

Different existing files and unknown partial downloads are not overwritten. For a SHA256 mismatch, select the correct file or a different folder. After a network interruption, retry the download: completed files are verified and reused.

The EXE is distributed in a separate portable package without model weights, engine or CUDA. It is not signed with a publisher certificate; the computer owner decides how to handle a blocked launch. The app does not change security settings.

Use the source route for additional external launch wrappers. The ordinary Windows package uses its direct bundled worker.

## Interface language and updating

Choose **Русский / English** at the top right of Manager. The choice is saved in local `manager.json` and restored on the next launch. Manager opens the generator in that language; the generator also has **Русский / English** buttons. The browser remembers its own choice in local storage; when storage is blocked, the tab address retains it. Interface language does not translate prompts, lettering inside images, filenames or raw diagnostics from external components.

Switching remains available during checks, downloads and generation. It updates labels, hints, errors and stages while preserving paths, parameters, progress and the current PNG. Switching never starts or retries a generation and never stops the server.

To update, stop the server with the old Manager, close it and extract the new ZIP into a separate folder. Launch the new EXE; settings in `%LOCALAPPDATA%/FLUX3Pascal`, selected models and existing CUDA are reused. Keep the old folder until the new version starts successfully. A running server is not upgraded in place. For the source route, stop and restart the server from the updated sources, then reload the generator page.

This update was checked without opening a native window or running new GPU generations. Manager tests replace widgets and file dialogs with programmatic doubles; real servers use separate temporary settings and ports. This verifies handlers and the server, not native layout or system dialog behavior. System buttons within file dialogs follow the Windows language.

## Run from source

Developer route: `Start-FLUX3.cmd` or `python scripts/app.py`. Launch the Manager itself with `python desktop/launcher.py`. Python 3.14.4 x64 was tested; the native window requires working Tk. The app needs no external Python packages. Prepare the engine and weights using [REPRODUCE_EN.md](REPRODUCE_EN.md); EXE building is described in [BUILD_WINDOWS_EN.md](BUILD_WINDOWS_EN.md).

For the source server, set paths to sd-cli.exe, FLUX.3 Q4_0, Qwen3-VL 4B Q4_K_M, FLUX.2 VAE and CUDA Toolkit 12.6 bin. The additional DLL directory can remain empty. The VRAM budget is 6 GiB. The browser’s **Check and save paths («Проверить и сохранить пути»)** button checks existence; `python scripts/verify.py --config config.local.json` checks SHA256. The Manager’s readiness check includes SHA256.

Choose a preset or enter a prompt; set size, seed, steps and CFG; click **Generate («Сгенерировать»)**. The measured profile is 16 steps and CFG1. Dimensions must be multiples of 16, 256–1536 per side, with at most 1024² pixels in total. Seed range: 0–2147483647; steps: 1–64; CFG: 1–8. Options outside the measured profile have no promised quality or time.

## Current result

The app shows one current operation, with no saved-run list or API for such a list. It neither reads external user folders nor restores completed jobs after server restart.

**Save the original PNG before the next generation or before exiting.** The PNG includes the prompt and parameters. Working files use an app-owned temporary folder; the next generation removes previous temporary files, and normal shutdown clears the folder. External user directories selected in the configuration are not cleared.

Refreshing the page during a job shows the same current operation. A new app launch after server shutdown starts with an empty result. **Cancel («Отменить»)** stops its own process tree; **Exit app («Завершить приложение»)** closes the server. Closing only the tab does not stop the current generation.

## Connection and stages

The usual address is `http://127.0.0.1:8440`; the local random session persists across restarts. Do not share the full session URL or publish app-session.json. Set a different port explicitly, for example `python scripts/app.py --port 8441`; an occupied port is not silently replaced by a random one.

If disconnected, use **Start server («Запустить сервер»)** or **Open generator («Открыть генератор»)** in the Manager, then **Reconnect («Повторить подключение»)** in the browser. Reconnecting preserves entered settings and does not automatically repeat a generation POST. After a lost response, the client first reconciles the single current operation to avoid duplicate generation. The port can be changed explicitly in the Manager.

Weight-loading counters such as `316/316` are not diffusion steps. The indicator distinguishes model preparation, image generation at the requested step count and conversion to PNG. Percentage is an approximate stage, not an exact remaining-time estimate. At 1024² the VAE can automatically switch to tiles; warnings and delays are part of engine execution.

## Local settings and verification

config.local.json, app-state.json and app-session.json are excluded from Git and distribution packages. Configuration can live outside the project: `python scripts/app.py --config .\local\config.json`. The server listens only on 127.0.0.1; API access requires a session and checks Host, and modifications also check Origin. There is no cloud service or remote access.

Automated checks: `python -B -m unittest discover -s tests -v`. They cover local HTTP downloads, cancellation/resume, SHA256, overwrite refusal, extraction, no restored previous runs, a single current result, external-file preservation, restart, connection recovery and stage labels. These tests do not run the GPU model. Generator evidence: [ui-proof/verification.json](../ui-proof/verification.json); Manager evidence: [desktop/verification.json](../desktop/verification.json).
