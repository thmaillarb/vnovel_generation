# vnovel_generation

Builds upon Xiaoyu Han's project to automate the generation of visual novels about research ethics.

## Usage

These instructions are written for Windows only.

1. (Optional) Create a new virtual environment and enable it (git ignores it if it's named venv):
   ```bash
   python3 -m venv venv
   .\venv\Scripts\activate.ps1
   ```
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Download [Ren'Py](https://www.renpy.org/release/8.2.3) and extract it in a new `renpy` folder.

   Note: Only version 8.2.3 was tested. Use other versions at your own risk.
4. Download and install [Ollama](https://ollama.com/download).
5. Pull the `llama3:8b` and `gemma2:9b` models:
   ```bash
   ollama pull llama3:8b
   ollama pull gemma2:9b
   ```
6. Make sure you have access to the [Stable Diffusion 3 Medium](https://huggingface.co/stabilityai/stable-diffusion-3-medium) model on HuggingFace, then log into your account:
   ```bash
   huggingface-cli login
   ```
7. Run the script:
   ```bash
   PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python main.py
   ```

## Config

The questions should be in the `questions.yaml`. Its syntax should be:

```yaml
situations:
  - question: "The 1st question that should be asked in the visual novel"
    answers:
      - "Answer 0"
      - "Answer 1"
      # ...
      - "Answer n"
    correct_answer: 0 # The index of the correct answer, starting with 0.
  # ...
  - question: "The n-th question that should be asked in the visual novel"
    answers:
      - "Answer 0"
      - "Answer 1"
      # ...
      - "Answer n"
    correct_answer: 0
```

See the `situation examples` directory for sample files.