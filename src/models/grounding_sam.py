import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import matplotlib.pyplot as plt
import numpy as np
import requests
import torch
from det import detect_groundingdino
from PIL import Image
from transformers import AutoModelForMaskGeneration, AutoProcessor
from utils import get_device


@dataclass
class BoundingBox:
    xmin: int
    ymin: int
    xmax: int
    ymax: int

    @property
    def xyxy(self) -> List[float]:
        return [self.xmin, self.ymin, self.xmax, self.ymax]


@dataclass
class DetectionResult:
    score: float
    label: str
    box: BoundingBox
    mask: Optional[np.array] = None


def plot_detections(image: Union[Image.Image, np.ndarray], detections: List[DetectionResult]) -> None:
    def annotate(image: Union[Image.Image, np.ndarray], detection_results: List[DetectionResult]) -> np.ndarray:
        # Convert PIL Image to OpenCV format
        image_cv2 = np.array(image) if isinstance(image, Image.Image) else image
        image_cv2 = cv2.cvtColor(image_cv2, cv2.COLOR_RGB2BGR)

        # Iterate over detections and add bounding boxes and masks
        for detection in detection_results:
            label = detection.label
            score = detection.score
            box = detection.box
            mask = detection.mask

            # Sample a random color for each detection
            color = np.random.randint(0, 256, size=3)

            # Draw bounding box
            cv2.rectangle(image_cv2, (box.xmin, box.ymin), (box.xmax, box.ymax), color.tolist(), 2)
            cv2.putText(image_cv2, f"{label}: {score:.2f}", (box.xmin, box.ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color.tolist(), 2)

            # If mask is available, apply it
            if mask is not None:
                # Convert mask to uint8
                mask_uint8 = (mask * 255).astype(np.uint8)
                contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(image_cv2, contours, -1, color.tolist(), 2)

        return cv2.cvtColor(image_cv2, cv2.COLOR_BGR2RGB)

    annotated_image = annotate(image, detections)
    plt.imshow(annotated_image)
    plt.axis("off")
    plt.show()


def refine_masks(masks: torch.BoolTensor, polygon_refinement: bool = False) -> List[np.ndarray]:
    def mask_to_polygon(mask: np.ndarray) -> List[List[int]]:
        # Find contours in the binary mask
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Find the contour with the largest area
        largest_contour = max(contours, key=cv2.contourArea)

        # Extract the vertices of the contour
        polygon = largest_contour.reshape(-1, 2).tolist()

        return polygon

    def polygon_to_mask(polygon: List[Tuple[int, int]], image_shape: Tuple[int, int]) -> np.ndarray:
        """
        Convert a polygon to a segmentation mask.

        Args:
        - polygon (list): List of (x, y) coordinates representing the vertices of the polygon.
        - image_shape (tuple): Shape of the image (height, width) for the mask.

        Returns:
        - np.ndarray: Segmentation mask with the polygon filled.
        """
        # Create an empty mask
        mask = np.zeros(image_shape, dtype=np.uint8)

        # Convert polygon to an array of points
        pts = np.array(polygon, dtype=np.int32)

        # Fill the polygon with white color (255)
        cv2.fillPoly(mask, [pts], color=(255,))

        return mask

    masks = masks.cpu().float()
    masks = masks.permute(0, 2, 3, 1)
    masks = masks.mean(axis=-1)
    masks = (masks > 0).int()
    masks = masks.numpy().astype(np.uint8)
    masks = list(masks)

    if polygon_refinement:
        for idx, mask in enumerate(masks):
            shape = mask.shape
            polygon = mask_to_polygon(mask)
            mask = polygon_to_mask(polygon, shape)
            masks[idx] = mask

    return masks


def segment_samv2(image: Image.Image, detection_results: List[Dict[str, Any]], polygon_refinement: bool = False) -> List[DetectionResult]:
    # https://huggingface.co/facebook/sam2-hiera-tiny
    # https://huggingface.co/facebook/sam2-hiera-small
    # https://huggingface.co/facebook/sam2-hiera-base-plus
    # https://huggingface.co/facebook/sam2-hiera-large
    segmenter_id = "facebook/sam-vit-base"

    device = get_device()
    segmentator = AutoModelForMaskGeneration.from_pretrained(segmenter_id).to(device)
    processor = AutoProcessor.from_pretrained(segmenter_id)

    def get_boxes(results: DetectionResult) -> List[List[List[float]]]:
        boxes = []
        for result in results:
            xyxy = result.box.xyxy
            boxes.append(xyxy)

        return [boxes]

    boxes = get_boxes(detection_results)
    inputs = processor(images=image, input_boxes=boxes, return_tensors="pt").to(device)

    outputs = segmentator(**inputs)
    masks = processor.post_process_masks(masks=outputs.pred_masks, original_sizes=inputs.original_sizes, reshaped_input_sizes=inputs.reshaped_input_sizes)[0]

    masks = refine_masks(masks, polygon_refinement)

    for detection_result, mask in zip(detection_results, masks):
        detection_result.mask = mask

    return detection_results


labels = ["a cat", "a remote control"]
threshold = 0.3

url = "http://images.cocodataset.org/val2017/000000039769.jpg"
img = Image.open(requests.get(url, stream=True).raw)


boxes, scores, labels = detect_groundingdino(img, labels, threshold)
detections = []
for box, score, label in zip(boxes, scores, labels):
    detections.append(DetectionResult(score=score, label=label, box=BoundingBox(xmin=math.floor(box[0]), ymin=math.floor(box[1]), xmax=math.floor(box[2]), ymax=math.floor(box[3]))))

detections = segment_samv2(img, detections, polygon_refinement=True)

plot_detections(np.array(img), detections)
