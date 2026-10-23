# Источники и применение

Числа времени и памяти получены локальными запусками 23 октября 2026 года. Они не являются чужими опубликованными бенчмарками. Снимок окружения – environment.json, команды каждого прогона – results/*/record.json.

## SD-FLUX3

[sd.cpp: FLUX.3 usage](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/flux3.md).

Проверка: 2026-10-23. Тип: documentation. Применение: Component choice, distilled 16 steps and CFG 1.0. Current documentation; binary used in experiment is separately pinned.

## SD-MEMORY

[sd.cpp: memory placement and segmented execution](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/performance.md).

Проверка: 2026-10-23. Тип: documentation. Применение: Explanation of CPU parameter storage, max-vram and GPU compute. No speed guarantee is copied.

## SD-RELEASE

[Measured Windows CUDA 12 release](https://github.com/leejet/stable-diffusion.cpp/releases/tag/master-992-39bc9d0).

Проверка: 2026-10-22 / binary SHA rechecked 2026-10-23. Тип: release metadata + local measurement. Применение: Exact archive URL, release and commit. Release metadata saved before this batch; extracted files hashed again for this batch.

## FLUX-GGUF

[FLUX.3 Q4_0 weights](https://huggingface.co/leejet/flux-3-image-klein-GGUF/tree/1c2ad2f9b9247ccca6506a23bdb033fdb0873321).

Проверка: 2026-10-22 / file SHA rechecked 2026-10-23. Тип: repository metadata + local hash. Применение: Exact revision, file size and SHA; no claim of a separate public Pascal benchmark.

## QWEN-GGUF

[Qwen3-VL 4B text encoder](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/blob/1cd86afb9a95c410a6038ab3b40d8b578c892266/Qwen3VL-4B-Instruct-Q4_K_M.gguf).

Проверка: 2026-10-23. Тип: repository metadata + local hash. Применение: Reused encoder is Qwen3-VL, not the older Qwen3-4B without VL.

## VAE

[FLUX.2 VAE exact file](https://huggingface.co/Comfy-Org/Flux-2-Dev/commit/ca4ac7c84eb42f3200fffc85b5fbee67129e6ffa).

Проверка: 2026-10-23. Тип: repository metadata + local hash. Применение: Published pointer gives exact matching SHA and 336213556 bytes.

## NVIDIA

[NVIDIA: CUDA architecture support](https://developer.nvidia.com/blog/navigating-gpu-architecture-support-a-guide-for-nvidia-cuda-developers/).

Проверка: 2026-10-23. Тип: documentation. Применение: CUDA 13 drops offline compilation for Pascal. Tested profile reuses CUDA 12.6.85.

## BFL

[Black Forest Labs: reference implementation](https://github.com/black-forest-labs/flux-3-image-klein).

Проверка: 2026-10-23. Тип: documentation. Применение: Official model context and 8 GB INT8 recommendation explicitly naming RTX 3070; this is not Pascal validation.

## BFL-TERMS

[Model distribution and applicable upstream terms](https://huggingface.co/black-forest-labs/flux-3-image-klein).

Проверка: link supplied; full gated model card not re-read in this batch. Тип: upstream reference. Применение: Weights are not redistributed in this project; consult the upstream terms before obtaining them.

[Strata: current project scope](https://github.com/Niko1221/Strata). Checked 2026-10-23. README presents Qwen inference; no FLUX backend or Strata speed-up is claimed in this experiment.

## Графический установщик, проверено 23 октября 2026

- [NVIDIA CUDA 12.6.3 redistributable manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.6.3.json) – Pinned Windows cudart 12.6.77 and cuBLAS 12.6.4.1 package URLs, sizes and SHA256; full cuBLAS transfer is not repeated on a computer with working CUDA.
- [PyInstaller 6.22.3 usage](https://pyinstaller.org/en/stable/usage.html) – Windows onedir/windowed build with Python 3.14.4 and Tk; no separate Python installation for the packaged application.
- [PyInstaller external program DLL search](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application) – Restore system DLL search during external subprocess creation and then restore bundled DLL search in the parent process.
