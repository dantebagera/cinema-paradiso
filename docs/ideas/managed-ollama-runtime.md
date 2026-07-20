# Managed Ollama Runtime

- **Status:** Deferred
- **Last reviewed:** 2026-07-19
- **Owner:** Cinema Paradiso

## Problem

Cinema Paradiso currently connects to an independently installed Ollama process. AI features
become unavailable when that process is not running, even if CP's saved URL and model are
correct. This external lifecycle is a poor fit for CP's longer-term direction as a media
operating system on a mini PC.

## Intended Experience

Local AI should behave like a native CP capability. A normal user should not need to install,
start, update, or diagnose Ollama separately. CP should clearly distinguish local inference,
cloud-backed models, missing models, stopped runtimes, and failed requests.

## Proposed Direction

- Package a tested standalone Ollama runtime under `runtime/ollama/versions/<version>/`.
- Let CP start, health-check, restart, and stop only the Ollama process that CP owns.
- Bind the managed runtime to localhost on a CP-controlled port.
- Store models outside the replaceable application directory, under App Data or a selected
  data drive using `OLLAMA_MODELS`.
- Keep `Managed Local AI` as the normal mode and retain `External Ollama` as an advanced mode.
- Offer hardware-appropriate model packs instead of placing every model in the main CP archive.
- Keep AI Control and Ask AI as separate product contracts. AI Control can use a smaller,
  constrained model while Ask AI may use a larger local or explicit cloud model.
- Pin and test Ollama versions with CP releases rather than allowing an independent silent
  updater to change the runtime contract.

## Constraints And Risks

- The mini-PC CPU, GPU, RAM, storage, and thermal limits determine which local model is viable.
- Ollama runtime licensing and model licensing are separate redistribution responsibilities.
- Model packages can be several gigabytes or more and must survive normal CP upgrades.
- AI inference must not degrade playback, IPTV remuxing, library reconciliation, or downloads.
- CP needs bounded concurrency, short model keep-alive, useful logs, and controlled recovery.
- A private managed port must not collide with a user's external Ollama server on port `11434`.
- Cloud-tagged models still require internet access even when the local Ollama gateway is bundled.

## Non-Goals

- Replacing Ollama with a CP-built inference engine.
- Combining Ask AI and AI Control into one behavior contract.
- Shipping every supported model and GPU backend in one universal archive.
- Making a cloud-backed model appear local or offline.

## Open Questions

- Will CP target one fixed mini-PC hardware specification or arbitrary Windows computers?
- What minimum response quality and maximum latency are acceptable for AI Control and Ask AI?
- Which edge model passes CP's structured-intent and recommendation benchmarks?
- Should the downloadable release omit model weights while a preconfigured appliance includes them?
- How should CP pause or unload AI when media playback needs the same RAM, VRAM, or CPU?

## Dependencies

- A defined mini-PC hardware target or supported hardware tiers.
- Repeatable AI Control and Ask AI quality benchmarks.
- A runtime manager with process ownership, health checks, version manifests, and rollback.
- A release policy for runtime hashes, third-party notices, and model licenses.

## Revisit Conditions

Revisit this idea after the target mini-PC hardware and CP distribution model are defined. The
next discussion should select a model tier and produce measured latency, memory, playback-impact,
and structured-output results before implementation is approved.

## References

- [Ollama Windows standalone runtime](https://docs.ollama.com/windows)
- [Ollama FAQ and runtime controls](https://docs.ollama.com/faq)
- [Ollama license](https://github.com/ollama/ollama/blob/main/LICENSE)
- [Gemma terms](https://ai.google.dev/gemma/terms)
- [`tools/build_portable_release.py`](../../tools/build_portable_release.py)
