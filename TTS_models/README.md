# TTS Models Directory

⚠️ **IMPORTANT: This directory is empty by default. You MUST download TTS models before using LISA.**

## Why Models Are Not Included

TTS model files are large (60-100MB+ each) and are excluded from the repository via `.gitignore`. You must download them separately before running LISA.

## Required Files

You need to download Piper TTS models and place them in this directory. Each voice requires two files:
- `<model-name>.onnx` - The neural network model
- `<model-name>.onnx.json` - Model configuration

**Without these files, LISA's speech functionality will not work.**

## Downloading Models

### Option 1: Direct Download from Piper Releases

Visit the [Piper Releases page](https://github.com/rhasspy/piper/releases) and download your preferred voice models.

### Option 2: Using wget (Example)

```bash
cd TTS_models/

# Download English (US) Amy voice (medium quality - recommended)
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/en_US-amy-medium.onnx
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/en_US-amy-medium.onnx.json

# Alternative: High quality LibriTTS voice (slower but better quality)
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/en_US-libritts-high.onnx
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/en_US-libritts-high.onnx.json
```

## Recommended Models

| Model | Quality | Speed | File Size | Use Case |
|-------|---------|-------|-----------|----------|
| `en_US-amy-medium` | Good | Fast | ~60MB | Recommended for production |
| `en_US-libritts-high` | Excellent | Slow | ~100MB | High-quality announcements |
| `en_US-lessac-medium` | Good | Fast | ~60MB | Alternative voice |
| `en_GB-*` | Various | Various | Various | British English accent |

## Using Different Voices

The default voice is `en_US-amy-medium.onnx`. To change the voice, edit `robot_functions.py`:

```python
def robot_speak(text, model_name="en_US-amy-medium.onnx"):
```

Or call `robot_speak()` with a different model:

```python
robot_speak("Hello", model_name="en_US-libritts-high.onnx")
```

## Available Languages

Piper supports many languages including:
- English (US, GB, IN)
- Spanish (ES, MX)
- French (FR)
- German (DE)
- Italian (IT)
- Dutch (NL)
- And many more...

See the [Piper documentation](https://github.com/rhasspy/piper) for a complete list.

## Model File Structure

After downloading, your directory should look like:
```
TTS_models/
├── README.md (this file)
├── en_US-amy-medium.onnx
├── en_US-amy-medium.onnx.json
├── en_US-libritts-high.onnx (optional)
└── en_US-libritts-high.onnx.json (optional)
```

## Troubleshooting

**Voice sounds robotic**:
- Try a higher quality model (e.g., `high` instead of `medium`)

**Speech is too slow**:
- Use a `low` or `medium` quality model
- Ensure sufficient system resources

**Model not found error**:
- Verify both `.onnx` and `.onnx.json` files are present
- Check that the filename in code matches exactly (case-sensitive)

## Resources

- [Piper GitHub Repository](https://github.com/rhasspy/piper)
- [Piper Model Samples](https://rhasspy.github.io/piper-samples/)
- [Model Downloads](https://github.com/rhasspy/piper/releases)

