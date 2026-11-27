# Episode 1: MiniMax H3-Image and P-H3-Image

Watch the episode: https://www.youtube.com/watch?v=G6cXCfZ3cbY

Everything here is what you need to run the episode's tests on your own card, or on a rented one in Colab, and to hold your numbers up against ours. Nothing in it differs from what the episode ran, down to the seeds. When we reran the 1-megapixel size test with this script on our RTX 3060, both models gave back the episode's pictures pixel for pixel.

There are no pictures and no model weights in this folder. The script fetches the weights from the makers' own pages, and the pictures are the ones you make.

## The two models

| | MiniMax H3-Image | P-H3-Image |
|---|---|---|
| Made by | MiniMax | Pruna AI, rebuilt from MiniMax's H3 |
| Model page | [huggingface.co/MiniMaxAI/MiniMax-H3-Image](https://huggingface.co/MiniMaxAI/MiniMax-H3-Image) and [github.com/MiniMax-AI/MiniMax-H3-Image](https://github.com/MiniMax-AI/MiniMax-H3-Image) | [huggingface.co/PrunaAI/P-Image-OSS](https://huggingface.co/PrunaAI/P-Image-OSS) and Pruna's [launch post](https://www.pruna.ai/blog/p-image-oss-launch) |
| The files the episode ran | Comfy-Org's 4-bit build, [huggingface.co/Comfy-Org/MiniMax-H3-Image](https://huggingface.co/Comfy-Org/MiniMax-H3-Image): 29.4 GB | Pruna's 4-bit build, [huggingface.co/PrunaAI/P-Image-OSS-Comfy](https://huggingface.co/PrunaAI/P-Image-OSS-Comfy): 26.8 GB |
| Steps | 6, the maker's setting | 8 on Pruna's own noise levels, the maker's setting |
| Your prompt | goes to the model as you wrote it | goes through Pruna's prompt rewriter on every take, as Pruna recommend, and the model draws from the rewrite |
| ComfyUI's guide | [docs.comfy.org, MiniMax H3-Image](https://docs.comfy.org/tutorials/image/minimax/minimax-h3-image) | [docs.comfy.org, P-H3-Image](https://docs.comfy.org/tutorials/image/pruna/p-h3-image) |

Pruna publishes the model as P-Image-OSS and its ComfyUI files as `p-h3-image_*`. The episode calls it P-H3-Image.

Each prompt in `prompts/` is written for its model the way that model's maker says to prompt it, so the two models get the same picture described in two ways. The model files come under their makers' own licences, which are on each model page. The MIT licence in this repository covers our code only.

## What the episode tested

Every test has the same woman in it, a photographic character made for the episode called Maya. Each prompt has a name, and `python run_takes.py --list` prints them all.

| Test | What it asks | Prompt names | Pictures going in |
|---|---|---|---|
| A | Her in five new scenes, with new hair and clothes each time | `a-at-work`, `a-rainy-street`, `a-gallery-evening`, `a-at-home`, `a-rooftop-dawn` | her face and her body sheet |
| B | One change at a time: a coat, a background, the light, ten years older | `b-navy-coat`, `b-rainy-street`, `b-evening-light`, `b-ten-years-older` | her face |
| C | The size question: one portrait from words at 1, 4, 8 and 16 megapixels | `c-size-1mp`, `c-size-4mp`, `c-size-8mp`, `c-size-16mp` | none |
| D | The stress round: three fingers, a clock at twenty to five, five pairs of headphones, a mirror | `d-three-fingers`, `d-twenty-to-five`, `d-five-headphones`, `d-mirror` | her face |
| E | Several pictures into one: three objects made from words, then her holding and wearing them | `e-object-headphones`, `e-object-jacket`, `e-object-card`, then `e-four-into-one` | her face and the three objects |
| G | A film poster in one long prompt, then a new title and date | `g-poster-one-pass`, `g-poster-retitled` | her face and body, then the poster |

Then three posters, built step by step, in `prompts/posters.json`:

| Poster | What it is | How it was built |
|---|---|---|
| `poster-1` | A one-sheet for the series *The Echo of Lazarus* | The one-pass poster from test G, then an edit that puts two large faces of her in the sky, then the same poster again at print size |
| `poster-2` | A title card for this episode | A layout from words, her brought in, the graphics card brought in, the title, a badge, then fixes |
| `poster-3` | A 1960s-style advertisement for the RTX 3060 | The style and headline from words, her brought in, the card as a product drawing, the small print, the paragraph, then fixes |

On Pruna's model, bringing her into a layout that already had a woman in it didn't take in three tries, so its posters 2 and 3 start again with her in from the words. `posters.json` keeps both routes, and the tries that didn't carry on are under `also_tried`.

Take 1 of every prompt uses the seed in the file, the same on both models and on every card. Later takes draw a new seed, as they did in the episode.

### Her face and body pictures

The tests that bring her in need a face picture and a body sheet (her from the neck down, from the front, the side and the back). The episode's came from an earlier character session that started from a drawn reference, and they aren't shared, since this repository carries no pictures. You can use pictures of your own, of someone who has agreed to it, or make them with the models: `c-size-4mp` draws a woman close to Maya from words alone, and `subject-body` makes a body sheet from a face.

```
python run_takes.py --comfy ComfyUI --model h3-image --prompt c-size-4mp --takes 1
python run_takes.py --comfy ComfyUI --model h3-image --prompt subject-body --takes 1 --picture face=runs/h3-image/c-size-4mp/<the take>.png
```

## The hardware

| | At home | Colab | Colab |
|---|---|---|---|
| Card | NVIDIA GeForce RTX 3060, 12 GB, from 2021 | NVIDIA L4, 24 GB (22.5 GB as `nvidia-smi` counts it) | NVIDIA A100, 80 GB |
| Processor and memory | Intel Core i9-9900X, 53.4 GB | Intel Xeon, 12 threads, 53.0 GB | as Colab gave it |
| System | Ubuntu 26.04.1, NVIDIA driver 595.99.02 | Colab's | Colab's |
| PyTorch | 2.15.0 with CUDA 13.2, Python 3.14 | Colab's own | Colab's own |
| ComfyUI | commit `995456d`, 19 November 2026 | the same commit | the same commit |
| ComfyUI started with | `--fast-disk --preview-method auto --preview-size 1024` | `--disable-auto-launch` | `--disable-auto-launch` |
| Compute units an hour | | 1.93 to 2.34 | 8.87 to 8.89 |

## What you need

- An NVIDIA card. Both builds filled our 12 GB card to about 11.4 GB at every size, from 1 to 16 megapixels. Pruna's ComfyUI page says its 4-bit files need an NVIDIA Ampere card (RTX 30 series) or newer.
- Linux. That's where this was tested. The script reads system memory from `/proc/meminfo`, and on other systems it falls back to `psutil` if you have it.
- System memory: our highest reading at home was 22.2 GB for the whole computer, during edits with two pictures going in.
- Disk: 29.4 GB for MiniMax H3-Image and 26.8 GB for P-H3-Image, plus several GB for ComfyUI and PyTorch.
- Python 3.10 or newer with its `venv` module (on Ubuntu and Debian that's the `python3-venv` package), and git.

## Install and run on your own machine

```
git clone https://github.com/kushalsharma/weights-and-watts
cd weights-and-watts/ep01-h3-image
bash setup.sh                                          # ComfyUI at the episode's commit, in ComfyUI/venv
ComfyUI/venv/bin/python get_models.py h3-image         # or p-h3-image, or both
ComfyUI/venv/bin/python run_takes.py --comfy ComfyUI --model h3-image --prompt c-size-4mp
```

`setup.sh` installs PyTorch 2.15.0 for CUDA 13.2, the build we ran. For an older driver, pick another build from [pytorch.org](https://pytorch.org/get-started/locally/), for example `TORCH_INDEX=https://download.pytorch.org/whl/cu126 TORCH="torch==2.14.1 torchvision" bash setup.sh`. To build the environment with a different Python, name it with `PYTHON=python3.12 bash setup.sh`.

With `--comfy`, the script starts ComfyUI for the run and stops it after, so the first take of a run includes loading the model, the way a first take did in the episode. Pictures go to `runs/<model>/<prompt>/`, with a JSON record beside each one (the workflow sent, every reading taken during the take), and every take adds a row to `runs/takes.csv`.

More ways to run it (`python` here is `ComfyUI/venv/bin/python`):

```
# several prompts, three takes each
python run_takes.py --comfy ComfyUI --model p-h3-image --prompt c-size-1mp --prompt c-size-4mp --takes 3

# a test that brings her in
python run_takes.py --comfy ComfyUI --model h3-image --prompt b-navy-coat --picture face=face.png

# your own prompt, with the episode's settings for that model (a picture is optional; up to four)
python run_takes.py --comfy ComfyUI --model h3-image --text "A product photograph of ..." --size 2048x2048
python run_takes.py --comfy ComfyUI --model h3-image --text "Edit <Picture 1>. ..." --picture photo.png

# a whole poster, step by step, each step working from take 1 of the step before
python run_takes.py --comfy ComfyUI --model p-h3-image --poster poster-1 --picture face=face.png --picture body=body.png
```

Some poster steps in the episode worked from the other model's take: MiniMax's two-faces edit started from Pruna's one-pass poster, for example. The script follows the episode and tells you which take it needs. Add `--own-model` to have each model work from its own takes instead.

Already running ComfyUI? Point the script at it with `--comfy-url http://127.0.0.1:8188` (on the same computer, so the readings are of the card doing the work). It needs a ComfyUI recent enough to have the MiniMax H3 nodes, and its own start-up flags then apply. If the model files are somewhere else, `--models-dir FOLDER` points ComfyUI at a folder holding `diffusion_models/`, `text_encoders/` and `vae/`.

## Run it on Colab

Open [`colab/ep01-h3-image-colab.ipynb`](colab/ep01-h3-image-colab.ipynb) in Colab ([open it directly](https://colab.research.google.com/github/kushalsharma/weights-and-watts/blob/main/ep01-h3-image/colab/ep01-h3-image-colab.ipynb)), choose an L4 or A100 runtime, set the model and prompts in the first cell, and run all the cells. It installs ComfyUI at the episode's commit on top of Colab's own PyTorch, as the episode's Colab runs did, downloads the model files and runs the takes.

Colab shows what the runtime costs, in compute units an hour, in its *Resources* panel. It doesn't hand that number to the code, so the notebook asks you to type it in, and then logs units for each take as seconds times that rate, the same way ours were worked out. Colab counts units for as long as the runtime is connected, downloads included, so the notebook also prints the total for the session.

## The CSV, column by column

`results/our-takes.csv` and the `takes.csv` the script writes share these columns.

| Column | What it is |
|---|---|
| `made_at` | When the take started, in UTC. On our Colab rows it's when the take was put in line |
| `prompt` | The prompt's name in `prompts/`. Empty on our rows whose prompt isn't shared (see below) |
| `test` | A to G, `poster 1` to `poster 3`, `subject`, `warm take`, or `character` |
| `step` | What the take was, in words |
| `take` | 1 for the take on the prompt's fixed seed, then 2, 3 … |
| `model` | MiniMax H3-Image or P-H3-Image |
| `card` | The graphics card |
| `place` | `home` or `colab` |
| `mode` | `words` (no pictures in), `one` (one picture in) or `several` |
| `pictures_in` | How many pictures went in |
| `width`, `height`, `megapixels` | The size of the picture made |
| `steps` | Sampling steps: 6 or 8 |
| `seed` | The seed |
| `seconds` | Time on the machine for the take, by ComfyUI's own clock |
| `card_gb_peak` | The card's memory in use at its highest during the take, the whole card |
| `system_gb_peak` | The computer's memory in use at its highest during the take, the whole computer |
| `watts_avg` | The card's average power draw over the take |
| `watts_peak` | The card's highest power reading during the take |
| `watt_hours` | The card's energy for the take |
| `card_temp_c` | The card's highest temperature during the take |
| `colab_units` | Compute units the take used, worked out from its seconds and the hourly rate |
| `cost_usd` | Those units in US dollars |
| `units_estimated` | True where units come from seconds times the rate, which is every row here |

The script adds a few columns after these: `card_gb_before` and `system_gb_before` (the readings just before the take, so you can see what else was using the card and the memory), `samples` (how many readings the take's numbers come from), `picture` (the file) and `error` (empty unless the take failed).

## How our numbers were measured

**Time** is ComfyUI's own clock, from the moment it starts on the take to the moment it finishes, picture saved. It includes loading the model files when the take is the first since ComfyUI started, and reading the prompt with the text encoder when the prompt is new. ComfyUI keeps the result of any part of the workflow whose inputs haven't changed, so a second take of the same prompt on a new seed skips the reading, and on Pruna's model it also skips the prompt rewriter. That's why take 2 is often much quicker than take 1.

**Card memory, watts and temperature** come from `nvidia-smi`, read about once a second the whole time. A take's numbers come from the readings between one second before it was sent and one second after it finished. Card memory is the whole card, so it includes anything else using it, such as your desktop.

**System memory** is the whole computer's memory in use (total less available, from `/proc/meminfo`), read with the card. It includes every other program running, which is what `system_gb_before` is there for.

**Watt-hours** add up each power reading times the time to the next reading, and the average is that energy over the time between the first and last reading. It's the graphics card's own reading, so it leaves out the rest of the computer, and it isn't power at the wall.

**GB** here means 1,024 MiB, the units `nvidia-smi` counts in, rounded to one decimal.

**On Colab, our rows were measured by a different runner from the one in this folder.** Its seconds ran from the take being handed to the machine to the picture being saved, checked once a second, so they can run about a second longer than ComfyUI's own clock. It read card memory twice a second and didn't record system memory, watts or temperature, so those columns are empty on our Colab rows. Units are seconds times the hourly rate Colab gave for the machine, and cost is those units at $0.1179 each, what the units were bought at. This folder's script measures Colab the same way it measures your own machine, so your Colab rows have the columns ours are missing.

## Our results

`results/our-takes.csv` holds every picture take of the episode, 280 of them, made on 24 and 25 November 2026.

| Where | Model | Takes |
|---|---|---|
| RTX 3060, at home | MiniMax H3-Image | 87 |
| RTX 3060, at home | P-H3-Image | 44 |
| Colab L4 | MiniMax H3-Image | 64 |
| Colab L4 | P-H3-Image | 48 |
| Colab A100 | MiniMax H3-Image | 3 |
| Colab A100 | P-H3-Image | 34 |

On the RTX 3060, those 131 takes took 3 hours 14 minutes and 518 watt-hours on the card. The Colab takes came to 8.45 units, about $1.00, not counting start-up and downloads.

Rows marked `character` are takes from before and beside the tests: the ones that made her face and body pictures, five scenes with a drawn version of her, and early portraits of a second character. Their prompts aren't in `prompts/`, since they all start from a reference picture that isn't shared.

The size test from words on the RTX 3060, in seconds (take 2, so with the model loaded and the prompt already read):

| | 1 MP | 4 MP | 8 MP | 16 MP |
|---|---|---|---|---|
| MiniMax H3-Image | 6.4 | 19.6 | 42.1 | 96.5 |
| P-H3-Image | 9.9 | 32.3 | 77.9 | 209.1 |

## Files

| | |
|---|---|
| `run_takes.py` | Runs the takes and writes the CSV. Standard library only |
| `get_models.py` | Downloads and checks the model files |
| `setup.sh` | Installs ComfyUI at the episode's commit, with PyTorch, on Linux |
| `models.json` | The model files, their revisions and checksums, and how each workflow is filled in |
| `workflows/` | The four ComfyUI workflows the episode ran, words and pictures for each model |
| `prompts/tests.json` | Every test prompt, as each model was sent it, with its size and seed |
| `prompts/posters.json` | The three posters, step by step |
| `results/our-takes.csv` | Our takes |
| `colab/ep01-h3-image-colab.ipynb` | The same runs on Colab |

## Author

Code, prompts and numbers by Kushal Sharma, for [Weights & Watts](https://www.youtube.com/@WeightsWatts). The code is under the MIT License (see `LICENSE` at the top of the repository).
