# Property Brain - Training Guide

## When You Get Home

### Step 1: Download Files from VPS

Open PowerShell or Git Bash and run:

```bash
scp root@2.24.118.123:/tmp/property-brain-training.tar.gz ~/Desktop/
cd ~/Desktop
tar xzf property-brain-training.tar.gz
```

### Step 2: Run Setup

Double-click `setup-training.bat` or run in terminal:

```bash
cd sqhq-local-ai
./setup-training.bat
```

This will:
- Create a Python virtual environment
- Install all dependencies (PyTorch, Unsloth, etc.)
- Verify your GPU is working
- Run a dry run to confirm everything is ready

### Step 3: Start Training

```bash
cd sqhq-local-ai
venv\Scripts\activate
python src\training\train.py
```

Training will take ~2-3 hours on your RTX 4070.

### Step 4: Model Output

When training completes, you'll have:
- `models/property-brain-final/` — Full model
- `models/checkpoints/` — Training checkpoints

### Step 5: Export to GGUF (for llama.cpp)

After training, convert to GGUF format:

```bash
python -c "
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained('models/property-brain-final')
model.save_pretrained_gguf('models/gguf', tokenizer, quantization_method='q5_k_m')
"
```

### Step 6: Deploy to VPS

```bash
scp -r models/gguf/*.gguf root@2.24.118.123:/root/sqhq-local-ai/models/
```

---

## Training Configuration

| Setting | Value |
|---------|-------|
| Base model | Qwen2.5-3B-Instruct |
| Method | LoRA (rank 16, alpha 16) |
| Epochs | 3 |
| Batch size | 4 (gradient accumulation 4) |
| Learning rate | 2e-4 |
| VRAM usage | ~8-10 GB |
| Training time | ~2-3 hours |

---

## Troubleshooting

### "CUDA not available"
- Make sure you have NVIDIA drivers installed
- Run `nvidia-smi` to verify GPU is detected
- Restart after driver installation

### "Out of memory"
- Reduce batch size: `python src/training/train.py --batch-size 2`
- Or reduce LoRA rank: `python src/training/train.py --lora-rank 8`

### "Model not found"
- Make sure you're in the `sqhq-local-ai` directory
- Check that `data/training_data_alpaca.json` exists
