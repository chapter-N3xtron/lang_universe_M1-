# ComfyUI Workflow — Anima/Qwen-image anime style

This workflow locks the rendering style and adds optional IP-Adapter
(face/body reference) and ControlNet/OpenPose (pose/anatomy) control.

## Locked style (do not change)

- **Diffusion model**: `anima-base-v1.0.safetensors` (anima-base is the only allowed model)
- **Text encoder**: `qwen_3_06b_base.safetensors` via `CLIPLoader(type="qwen_image")`
- **VAE**: `qwen_image_vae.safetensors`
- **LoRA**: `dakota_anima_lora.safetensors` (strength `0.5`)
- **Width/Height**: 1280x720
- **Sampler**: `dpmpp_2m` / `sgm_uniform`
- **Steps**: 28, **CFG**: 4.5
- **Seed strategy**: `random`

## Optional control inputs

- Node `20` (`LoadImage`): reference image for IP-Adapter. Set filename to a real path, or leave as `""` to disable.
- Node `30` (`LoadImage`): pose hint image for OpenPose ControlNet. Set filename to a real path, or leave as `""` to disable.

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
