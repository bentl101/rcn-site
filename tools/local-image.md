# Local image workflow

`local-image` provides two Apple-Silicon-native image-generation profiles:

- `final` (default): Qwen-Image-2512 Q8 for typography, prompt fidelity, and final ad creative.
- `draft`: FLUX.2 Klein 4B Q8 for fast concept iteration.

Both source models and the selected quantized weights are Apache 2.0 licensed.
The runner is MFLUX/MLX, so generation stays local after the initial Hugging Face
download.

## Generate

```bash
local-image final \
  --prompt 'A premium river-cruise ad, headline "SAVE 20%", elegant navy and teal art direction' \
  --width 1200 \
  --height 628 \
  --seed 42 \
  --output creative.png
```

Use `draft` for a faster four-step pass:

```bash
local-image draft --prompt-file brief.txt --auto-seeds 4 --output concepts.png
```

When multiple seeds are requested, MFLUX adds the seed to each output filename.
Generation settings are embedded in each PNG for reproducibility. Inspect them
later with:

```bash
local-image info creative.png
```

The runner also requests a JSON sidecar. Qwen writes the full record there;
MFLUX 0.16.9 currently emits `null` in the FLUX.2 sidecar, so the embedded PNG
record is the source of truth for draft outputs.

## Workflow integration

Shell, Python subprocesses, launchd jobs, and workflow tools can call the same
command. For example, an n8n Execute Command node can run:

```bash
local-image final --prompt-file /absolute/path/brief.txt --output /absolute/path/result.png
```

Use absolute paths in unattended workflows. Keep the Mac awake and connected to
power for Qwen jobs; the final profile is substantially slower than the draft
profile on an M1 Max.

Run `local-image help` for the short command reference. All additional flags are
passed through to the corresponding MFLUX CLI.
