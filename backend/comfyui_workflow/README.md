# ComfyUI Workflow — Anima/Qwen-image anime style

This workflow locks the rendering style and adds optional IP-Adapter
(face/body reference) and ControlNet/OpenPose (pose/anatomy) control.

## Locked style (do not change)

- **Diffusion model**: `anima-base-v1.0.safetensors` (anima-base is the only allowed model)
- **Text encoder**: `qwen_3_06b_base.safetensors` via `CLIPLoader(type="qwen_image")`
- **VAE**: `qwen_image_vae.safetensors`
- **LoRA**: `dakota_anima_lora.safetensors` (strength `0.5`)
- **Width/Height**: 1216x704
- **Sampler**: `dpmpp_2m` / `karras`
- **UNET weight dtype**: `fp16`
- **Steps**: 28, **CFG**: 4.5
- **Seed strategy**: `random`

## Optional control inputs

The base workflow does not include IP-Adapter or ControlNet nodes. To add them,
pass a reference image path or pose hint image path when calling `place_image_order`;
the agent will inject the nodes at queue time. If no image is provided, the base
workflow renders with only the locked anime style.

## Character-specific inputs

- Node `7`: positive prompt from `prompt_engine.py`.
- Node `8`: negative prompt from `prompt_engine.py`.

## API usage

1. Build a prompt with the character framework's `prompt_engine.py`.
2. Patch nodes `7` and `8`.
3. Optionally set node `20` and/or node `30` image paths.
4. POST the updated workflow to ComfyUI:

```bash
curl -X POST http://127.0.0.1:8188/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": $(cat workflow_api.json), "client_id": "my-client"}'
```

Or use the included `queue.py`:

```bash
python queue.py 7 "your positive prompt" 8 "your negative prompt"
```
