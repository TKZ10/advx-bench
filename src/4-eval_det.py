import csv
import gc
import itertools
import json
import os
import random
from pathlib import Path

import torch
import torchvision.transforms as transforms
from datasets import load_dataset
from PIL import Image
from sklearn.metrics import average_precision_score
from tqdm import tqdm

from advx.background import get_gradient_background, get_perlin_background, get_random_background, get_zigzag_background
from advx.masks import get_diamond_mask
from advx.utils import add_overlay
from metrics.metrics import get_cosine_similarity, get_iou, get_psnr, get_ssim
from models.det import detect_vit
from models.utils import set_seed
from utils import get_device


def is_cached(path: Path, entry_ids: dict) -> bool:
    entry_ids = entry_ids.copy()

    if not path.exists():
        return False

    with open(path, mode="r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if all(row[key] == str(value) for key, value in entry_ids.items()):
                return True
    return False


def get_coco_label(idx: int) -> str:
    datapath = Path.cwd() / "data" / "coco_labels.json"
    data = json.loads(datapath.read_text())
    return data[str(idx)]


def get_coco_labels() -> list[str]:
    datapath = Path.cwd() / "data" / "coco_labels.json"
    data = json.loads(datapath.read_text())
    return list(data.values())


def get_advx(img: Image.Image, combination: dict) -> Image.Image:
    combination = combination.copy()

    # overlay image
    get_diamond_overlay = lambda img: add_overlay(img, overlay=get_diamond_mask(diamond_count=15, diamonds_per_row=10), opacity=160)
    img = get_diamond_overlay(img)

    # get background
    width, height = img.size * 3
    background = None
    if combination["background"] == "perlin":
        background = get_perlin_background(width=width, height=height)
    elif combination["background"] == "zigzag":
        background = get_zigzag_background(width=width, height=height)
    elif combination["background"] == "gradient":
        background = get_gradient_background(width=width, height=height)
    elif combination["background"] == "random":
        background = get_random_background(width=width, height=height)
    else:
        raise ValueError(f"unknown background {combination['background']}")

    # place image(s) on background
    # ...

    return img

"""
environment
"""

seed = 41
set_seed(seed=seed)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
if get_device() == "cuda":
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.reset_accumulated_memory_stats()



"""
config
"""


CONFIG = {
    "outpath": Path.cwd() / "data" / "eval" / "eval_cls.csv",
    "subset_size": 5,  # number of detection tasks per background
}
COMBINATIONS = {
    "images_per_background": 3,  # number of images to place on a single background
    "background": ["perlin", "zigzag", "gradient", "random"],
}


"""
eval loop
"""


random_combinations = list(itertools.product(*COMBINATIONS.values()))
random.shuffle(random_combinations)
print(f"total iterations: {len(random_combinations) * CONFIG['subset_size']}")

dataset_size = CONFIG["images_per_background"] * CONFIG["subset_size"]
dataset = load_dataset("detection-datasets/coco", split="val", streaming=True).take(CONFIG["images_per_background"]).shuffle(seed=seed)
dataset = list(map(lambda x: (x["image_id"], x["image"].convert("RGB"), x["objects"]["category"], x["objects"]["caption"]), dataset))

for combination in tqdm(random_combinations, total=len(random_combinations)):
    combination = dict(zip(COMBINATIONS.keys(), combination))

    for label_id, image, boxes, labels in dataset:
        ids = {
            **combination,
            "img_id": label_id,
        }
        if is_cached(CONFIG["outpath"], ids):
            print(f"skipping {ids}")
            continue

        with torch.no_grad(), torch.amp.autocast(device_type=get_device(disable_mps=True), enabled="cuda" == get_device()):
            adv_image = get_advx(image, combination)

            # try to place multiple images on a single background
            # show result

            exit()

            transform = transforms.Compose([transforms.Resize((256, 256)), transforms.Grayscale(num_output_channels=3), transforms.ToTensor()])
            x: torch.Tensor = transform(image).unsqueeze(0)
            advx_x: torch.Tensor = transform(adv_image).unsqueeze(0)

            def filter_detections(probs, boxes, labels, min_prob=0.5, max_prob=0.95):
                filtered = [(prob, box, label) for prob, box, label in zip(probs, boxes, labels) if min_prob <= prob <= max_prob]
                if not filtered:
                    return [], [], []
                return map(list, zip(*filtered))

            # also consider: clip grid https://www.pinecone.io/learn/series/image-search/zero-shot-object-detection-clip/#Zero-Shot-CLIP
            # this would allow us to use the robustified model from the previous step for detection as well
            x_boxes, x_probs, x_labels = detect_vit(image)
            adv_x_boxes, adv_x_probs, adv_x_labels = detect_vit(adv_image)

            x_probs_50_95, x_boxes_50_95, x_labels_50_95 = filter_detections(x_probs, x_boxes, x_labels)
            adv_x_probs_50_95, adv_x_boxes_50_95, adv_x_labels_50_95 = filter_detections(adv_x_probs, adv_x_boxes, adv_x_labels)

        results = {
            **ids,
            # semantic similarity
            "cosine_sim": get_cosine_similarity(image, adv_image),
            "psnr": get_psnr(x, advx_x),
            "ssim": get_ssim(x, advx_x),
            # accuracy
            "ground_truth_labels": labels,  # compute based on where images are placed in background
            "ground_truth_boxes": boxes,  # compute based on where images are placed in background
            "ap_x": average_precision_score([1 if label in labels else 0 for label in x_labels], x_probs) if len(x_labels) > 0 else 0.0,
            "ap_adv_x": average_precision_score([1 if label in labels else 0 for label in adv_x_labels], adv_x_probs) if len(adv_x_labels) > 0 else 0.0,
            "ap_x_50_95": average_precision_score([1 if label in labels else 0 for label in x_labels_50_95], x_probs_50_95) if len(x_labels_50_95) > 0 else 0.0,
            "ap_adv_x_50_95": average_precision_score([1 if label in labels else 0 for label in adv_x_labels_50_95], adv_x_probs_50_95) if len(adv_x_labels_50_95) > 0 else 0.0,
            "iou_x": max([get_iou(box, box_) for box in boxes for box_ in x_boxes]) if len(x_boxes) > 0 else 0.0,
            "iou_adv_x": max([get_iou(box, box_) for box in boxes for box_ in adv_x_boxes]) if len(adv_x_boxes) > 0 else 0.0,
        }

        with open(CONFIG["outpath"], mode="a") as f:
            writer = csv.DictWriter(f, fieldnames=results.keys())
            if CONFIG["outpath"].stat().st_size == 0:
                writer.writeheader()
            writer.writerow(results)

        torch.cuda.empty_cache()
        gc.collect()
