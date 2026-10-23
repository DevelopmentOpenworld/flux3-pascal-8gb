For installation and server control without a console, use [Windows Manager](INTERFACE_EN.md). The commands and measured settings below are for developers.

# Reproduction: FLUX.3 Image Klein on Pascal 8 GB

Tested route: Windows x64, GTX 1070 Ti / sm_61, 32 GiB RAM, an existing CUDA Toolkit 12.6.85 installation and a prebuilt stable-diffusion.cpp CUDA 12 binary. Engine code and model weights were not modified in this experiment. This route does not require a new CUDA Toolkit, PyTorch, ComfyUI, Diffusers or a separate FlashAttention package.

## 1. Check the existing CUDA installation

In PowerShell:

```powershell
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv,noheader
$cudaBin = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin'
& "$cudaBin\nvcc.exe" --version
Get-Item -LiteralPath "$cudaBin\cudart64_12.dll", "$cudaBin\cublas64_12.dll", "$cudaBin\cublasLt64_12.dll"
```

Observed output: GTX 1070 Ti, 8192 MiB, driver 581.80, compute capability 6.1; `nvcc` reports release 12.6, V12.6.85. CUDA 13.0 in the ordinary `nvidia-smi` heading does not mean Toolkit 13 is being used.

Replace `$cudaBin` with the actual path to an existing CUDA 12.6 installation if needed. There is no need to upgrade it for this project. CUDA 13 does not support new Pascal builds: [NVIDIA explanation](https://developer.nvidia.com/blog/navigating-gpu-architecture-support-a-guide-for-nvidia-cuda-developers/). A prebuilt executable must also contain sm_61 code; an arbitrary recent CUDA binary is not a qualified substitute for the pinned build.

The initial series used CUDA 12.6-compatible libraries with the same SHA256 values as the installed Toolkit. The toolkit-only-portrait-512 experiment, additional battles and UI checks use Toolkit bin without an extra DLL directory. Loading all three CUDA DLLs from the Toolkit was confirmed in toolkit-loaded-modules.json; hashes are in toolkit-dlls.json. CUDA was not reinstalled.

## 2. Obtain the exact files or reuse existing ones

Engine: [master-992-39bc9d0 release](https://github.com/leejet/stable-diffusion.cpp/releases/tag/master-992-39bc9d0), commit `39bc9d0b4bad86750fcb1fd2d711bc57a4c6018f`.

| File | Size, bytes | SHA256 |
|---|---:|---|
| sd-master-39bc9d0-bin-win-cuda12-x64.zip | 343795758 | b036d2174685050b2829ee660989a6548b300948930894f8a95a24b75380459a |
| flux3-image-klein-Q4_0.gguf | 3514023104 | 22d0b1fa05f5ef63fa68eebe801a680e0456cb786af28be5952e10fb5c9004b2 |
| Qwen3VL-4B-Instruct-Q4_K_M.gguf | 2497281664 | 66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a |
| flux2-vae.safetensors | 336213556 | d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5 |

Exact locations and revisions:

- DiT: [leejet/flux-3-image-klein-GGUF](https://huggingface.co/leejet/flux-3-image-klein-GGUF/tree/1c2ad2f9b9247ccca6506a23bdb033fdb0873321), revision `1c2ad2f9b9247ccca6506a23bdb033fdb0873321`.
- Encoder: [Qwen/Qwen3-VL-4B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/tree/1cd86afb9a95c410a6038ab3b40d8b578c892266), revision `1cd86afb9a95c410a6038ab3b40d8b578c892266`.
- VAE: [Comfy-Org/Flux-2-Dev](https://huggingface.co/Comfy-Org/Flux-2-Dev/blob/ca4ac7c84eb42f3200fffc85b5fbee67129e6ffa/split_files/vae/flux2-vae.safetensors), revision `ca4ac7c84eb42f3200fffc85b5fbee67129e6ffa`.

Use Qwen3-VL 4B specifically. The older Qwen3-4B without VL, used with FLUX.2, is not a tested substitute. No separate mmproj file was used for this text route.

When storing files inside the project, use this layout:

```text
runtime/
  sd-cli.exe
  stable-diffusion.dll
  ggml-cuda.dll
  ...other DLLs from the same archive...
models/
  flux3-image-klein-Q4_0.gguf
  Qwen3VL-4B-Instruct-Q4_K_M.gguf
  flux2-vae.safetensors
prompts/
  people-portrait.txt
```

Extract the whole engine archive. Do not move only sd-cli.exe without its neighboring DLLs. If the files already exist elsewhere, their paths can be set in the configuration; downloading or copying them again is unnecessary.

A Python standard-library script is provided for fresh downloads:

```powershell
python scripts/download_assets.py --list
# After reviewing upstream links and terms:
python scripts/download_assets.py
```

The script pins revisions and checks SHA256, reuses matching files and refuses to overwrite a different existing file. The additional series reused already verified files rather than downloading them again. A fresh-machine network download using this script was not tested.

## 3. Generate one image directly

Run from the project directory with the GPU available, sufficient RAM headroom and competing model processes closed:

```powershell
$cudaBin = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin'
$env:PATH = "$cudaBin;$env:PATH"
$env:OMP_NUM_THREADS = '8'
New-Item -ItemType Directory -Path outputs -ErrorAction Stop
& .\runtime\sd-cli.exe `
  --diffusion-model .\models\flux3-image-klein-Q4_0.gguf `
  --llm .\models\Qwen3VL-4B-Instruct-Q4_K_M.gguf `
  --vae .\models\flux2-vae.safetensors `
  --prompt-file .\prompts\people-portrait.txt `
  --steps 16 --cfg-scale 1.0 `
  --sampling-method euler --scheduler discrete `
  -W 512 -H 512 -s 42 `
  --flash-attn off,diffusion=on `
  --max-vram 6 --mmap --offload-to-cpu `
  -o .\outputs\portrait-512.png -v
if ($LASTEXITCODE -ne 0) { throw 'sd-cli failed: inspect the log' }
```

The outputs directory in this example is new. Choose a new result filename for a repeat experiment. The exact portable argument list for each published run is in `results/<run-id>/record.json`.

Key parameters:

- `--steps 16 --cfg-scale 1.0` is the distilled FLUX.3 Image Klein profile, not the Base profile.
- `--offload-to-cpu` stores original parameters in RAM and loads the required compute copies onto the GPU. It does not move the entire generation to CPU.
- `--max-vram 6` sets a managed 6 GiB budget. Desktop usage, driver context and external allocations are outside that budget.
- `--mmap` maps weight files into memory; read speed depends on the disk and Windows cache.
- `--flash-attn off,diffusion=on` enables the engine’s Flash Attention for DiT and disables it for other modules. These are GGML kernels, not a separate Python flash-attn package.
- Q4_0 is the published weight quantization. The tested route does not require FP8/NVFP4 or Tensor Cores.

## 4. Run with measurement logging

```powershell
Copy-Item -LiteralPath config.example.json -Destination config.local.json
# Change only existing-file paths and cuda_bin.
# Keep cuda_runtime_dir empty when using Toolkit bin DLLs.
python scripts/verify.py --config config.local.json
python scripts/generate.py --config config.local.json --case people-portrait-512 --run-id local-portrait-001
```

The wrapper measures a new sd-cli process and saves the PNG, a log sanitized of personal paths, parameters, hashes and sensors. It does not import torch. Available RAM below 3072 MiB, commit usage at or above 93%, or total occupied VRAM above 7680 MiB for five seconds is recorded as `MEMORY_GUARD`; this is not evidence of a confirmed model OOM. The process timeout is 900 seconds. Only the wrapper’s own sd-cli is terminated.

The wrapper records Windows and nvidia-smi sensors in sensors.jsonl. Reproduction requires sequential runs on an available GPU. The portable project does not require other internal service programs.

Use these conditions for the three resolution comparisons:

```text
people-portrait-512    people-portrait    people-portrait-1024
fantasy-weapon-512     fantasy-weapon     fantasy-weapon-1024
hitech-location-512    hitech-location    hitech-location-1024
```

The middle condition is 768×768. Each triplet has the same prompt and seed. Changing resolution changes the generation trajectory, so identical seeds and descriptions do not guarantee pixel-matching composition between resolutions.

For the tested 1024×1024 cases, the same argument list triggered an automatic VAE decoding retry from 1024×1024 to 512×512 tiles in an overlapping 3×3 grid. engine.log retains the budget warning and successful retry. The 1024² profile includes this behavior and its delay; `--vae-tiling` was not explicitly set.

## 5. Verify the result and reproduction limits

```powershell
python scripts/verify.py
```

Verifying the stored corpus does not run a model and does not require CUDA. Add `--config config.local.json` to check external weights; full SHA256 reads may warm the file cache.

Compare files, settings and the assessed quality level. Byte-identical images are not promised across different GPU drivers, CUDA versions, engines or cards. The paired identical-condition comparison on this setup is reported separately. Measurements use a warm or uncontrolled file cache; latency after inactivity may be higher.

32 GiB RAM was tested; it is not a measured minimum. Other Pascal cards, Linux, other quantizations, LoRA, Base, batch generation and image editing were not checked in this thematic series.

## 6. Generate through the interface

The main graphical route is [Windows Manager](INTERFACE_EN.md): select existing files or download them, then start the server with its button. Developers can use `Start-FLUX3.cmd` or `python scripts/app.py`. The complete native-button installation workflow remains unverified; the server and worker were checked programmatically.

Reproduce an additional battle with:

```powershell
python scripts/generate.py --config config.local.json --cases-file battle-cases.json --case fantasy-clear-7 --run-id local-battle-001
```

Every first result is retained. Grip, right/left-hand and mechanical limitations are documented in [BATTLES.md (Russian)](BATTLES.md).
