import math

import cv2
import matplotlib.pyplot as plt
import numpy as np
import requests
import torch
from det import detect_groundingdino
from PIL import Image
from utils import get_device

"""
models
"""


def segment_clipseg(img: Image.Image, labels: list[str]) -> tuple[list[str], list[torch.Tensor]]:
    from transformers import AutoProcessor, CLIPSegForImageSegmentation

    processor = AutoProcessor.from_pretrained("CIDAS/clipseg-rd64-refined")
    model = CLIPSegForImageSegmentation.from_pretrained("CIDAS/clipseg-rd64-refined")

    inputs = processor(text=labels, images=[img] * len(labels), padding=True, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits
    masks = torch.sigmoid(logits)

    return labels, masks


def segment_sam1(image: Image.Image, query: list[list[float]]) -> list[tuple[str, torch.Tensor]]:
    from transformers import AutoModelForMaskGeneration, AutoProcessor

    device = get_device()
    segmenter_id = "facebook/sam-vit-base"
    segmentator = AutoModelForMaskGeneration.from_pretrained(segmenter_id).to(device)
    processor = AutoProcessor.from_pretrained(segmenter_id)
    inputs = processor(images=image, input_boxes=[query], return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = segmentator(**inputs)
    masks = processor.post_process_masks(masks=outputs.pred_masks, original_sizes=inputs.original_sizes, reshaped_input_sizes=inputs.reshaped_input_sizes)[0]

    return labels, masks


"""
utils
"""


def plot_segmentation_detection(image: Image.Image, boxes: list[list[float]], scores: list[float], labels: list[str], masks: list[torch.Tensor]):
    def _refine_masks(masks: torch.BoolTensor) -> list[np.ndarray]:
        def mask_to_polygon(mask: np.ndarray) -> list[list[int]]:
            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            largest_contour = max(contours, key=cv2.contourArea)
            polygon = largest_contour.reshape(-1, 2).tolist()  # extract vertices of the contour
            return polygon

        def polygon_to_mask(polygon: list[tuple[int, int]], image_shape: tuple[int, int]) -> np.ndarray:
            # polygon = (x, y) coordinates of the vertices
            # image_shape = (height, width) of the mask

            mask = np.zeros(image_shape, dtype=np.uint8)
            pts = np.array(polygon, dtype=np.int32)  # point array
            cv2.fillPoly(mask, [pts], color=(255,))
            return mask

        masks = masks.cpu().float()
        masks = masks.permute(0, 2, 3, 1)
        masks = masks.mean(axis=-1)
        masks = (masks > 0).int()
        masks = masks.numpy().astype(np.uint8)
        masks = list(masks)

        for idx, mask in enumerate(masks):
            shape = mask.shape
            polygon = mask_to_polygon(mask)
            mask = polygon_to_mask(polygon, shape)
            masks[idx] = mask

        return masks

    boxes = [[math.floor(val) for val in box] for box in boxes]
    masks = _refine_masks(masks)

    image_cv2 = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    for label, score, (xmin, ymin, xmax, ymax), mask in zip(labels, scores, boxes, masks):
        color = np.random.randint(0, 256, size=3)

        # bounding box
        cv2.rectangle(image_cv2, (xmin, ymin), (xmax, ymax), color.tolist(), 2)
        cv2.putText(image_cv2, f"{label}: {score:.2f}", (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color.tolist(), 2)

        # mask
        mask_uint8 = (mask * 255).astype(np.uint8)
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(image_cv2, contours, -1, color.tolist(), 2)

    annotated_image = cv2.cvtColor(image_cv2, cv2.COLOR_BGR2RGB)
    plt.imshow(annotated_image)
    plt.axis("off")
    plt.show()


def plot_segmentation(img: Image.Image, labels: list[str], masks: list[torch.Tensor]):
    plt.imshow(img)
    plt.axis("off")

    cmap = plt.get_cmap("tab20")
    colors = [cmap(i / len(labels)) for i in range(len(labels))]
    for mask, color in zip(masks, colors):
        mask_np = mask.squeeze().numpy()

        # resize the mask to match the original image dimensions
        mask_resized = np.array(Image.fromarray(mask_np).resize(img.size, Image.BILINEAR))

        color_mask = np.zeros((*mask_resized.shape, 4))
        color_mask[..., :3] = color[:3]  # use the first 3 values (RGB) from the color tuple
        color_mask[..., 3] = mask_resized * 0.5
        plt.imshow(color_mask)
        plt.contour(mask_resized, levels=[0.5], colors=[color], alpha=0.8)

    legend_elements = [plt.Line2D([0], [0], color=color, lw=4, label=label) for label, color in zip(labels, colors)]
    plt.legend(handles=legend_elements, loc="center left", bbox_to_anchor=(1, 0.5))

    plt.tight_layout()
    plt.show()


"""
example
"""

if __name__ == "__main__":
    labels = ["cat", "remote control"]
    threshold = 0.3

    url = "http://images.cocodataset.org/val2017/000000039769.jpg"
    img = Image.open(requests.get(url, stream=True).raw)

    # labels, masks = segment_clipseg(img, labels)
    # plot_segmentation(img, labels, masks)

    boxes, scores, labels = detect_groundingdino(img, labels, threshold)
    labels, masks = segment_sam1(img, query=boxes)
    plot_segmentation_detection(img, boxes, scores, labels, masks)
