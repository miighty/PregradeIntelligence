"""Front/Back classification for Pokémon cards.

Goal: reliably detect if an input image is the *front* of a Pokémon card (required)
vs the *back* (optional), before running OCR/identity.

Design constraints:
- Deterministic outputs (same input -> same output)
- Lambda-friendly: default path uses ONNX Runtime if a model is present.
- Graceful fallback: if no model is bundled, fall back to a simple heuristic.

Model contract (ONNX):
- input:  float32 [B,3,H,W] in RGB, normalized with ImageNet mean/std
- output: logits [B,2]
- class order stored in adjacent labels.json
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class FrontBackPrediction:
    label: str  # "front" or "back" (or "unknown" if heuristic can't decide)
    confidence: float  # 0..1
    method: str


_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "models" / "front_back"
_DEFAULT_MODEL_PATH = _ASSETS_DIR / "best.onnx"
_DEFAULT_LABELS_PATH = _ASSETS_DIR / "labels.json"


def predict_front_back(image: Image.Image, model_path: Optional[str] = None) -> FrontBackPrediction:
    """Predict whether a card image is front/back.

    If an ONNX model is bundled, uses it. Otherwise uses a conservative heuristic.
    """

    model_p = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
    labels_p = _DEFAULT_LABELS_PATH

    if model_p.exists() and labels_p.exists():
        try:
            return _predict_onnx(image, model_p, labels_p)
        except Exception:
            # Fall back rather than throwing in the happy-path API.
            return _predict_heuristic(image)

    return _predict_heuristic(image)


def _predict_onnx(image: Image.Image, model_p: Path, labels_p: Path) -> FrontBackPrediction:
    import json

    import onnxruntime as ort

    labels = json.loads(labels_p.read_text()).get("classes")
    if not labels or len(labels) != 2:
        labels = ["back", "front"]

    # Determine expected input size from common default; for now assume 224.
    # If you re-export with a different size, store it in labels.json too.
    img_size = 224

    x = _preprocess(image, img_size)

    sess = ort.InferenceSession(model_p.as_posix(), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    out_name = sess.get_outputs()[0].name

    logits = sess.run([out_name], {input_name: x})[0]
    logits = np.asarray(logits, dtype=np.float32)[0]

    probs = _softmax(logits)
    idx = int(np.argmax(probs))

    return FrontBackPrediction(label=labels[idx], confidence=float(probs[idx]), method="onnx")


def _preprocess(image: Image.Image, img_size: int) -> np.ndarray:
    """RGB -> normalized NCHW float32."""

    im = image.convert("RGB")

    # Resize shorter side then center crop (like torchvision).
    w, h = im.size
    scale = int(img_size * 1.12)

    # resize so that smaller side == scale
    if w < h:
        new_w = scale
        new_h = int(round(h * (scale / w)))
    else:
        new_h = scale
        new_w = int(round(w * (scale / h)))

    im = im.resize((new_w, new_h), resample=Image.Resampling.BICUBIC)

    # center crop
    left = max(0, (new_w - img_size) // 2)
    top = max(0, (new_h - img_size) // 2)
    im = im.crop((left, top, left + img_size, top + img_size))

    arr = np.asarray(im, dtype=np.float32) / 255.0  # HWC

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std

    arr = np.transpose(arr, (2, 0, 1))  # CHW
    arr = np.expand_dims(arr, 0)  # NCHW
    return arr.astype(np.float32)


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    e = np.exp(x)
    return e / np.sum(e)


def _predict_heuristic(image: Image.Image) -> FrontBackPrediction:
    """Very simple heuristic to catch obvious 'back' cases.

    Pokémon backs have a strong blue border + central pokéball region.
    This heuristic computes a coarse color signature.

    Conservative: if uncertain, returns front with low confidence.
    (So we don't block identity extraction prematurely.)
    """

    im = image.convert("RGB")
    w, h = im.size

    # Sample a band near the border and a center patch.
    border = im.crop((0, int(h * 0.1), w, int(h * 0.2)))
    center = im.crop((int(w * 0.35), int(h * 0.45), int(w * 0.65), int(h * 0.65)))

    b = np.asarray(border, dtype=np.float32)
    c = np.asarray(center, dtype=np.float32)

    b_mean = b.mean(axis=(0, 1))  # RGB
    c_mean = c.mean(axis=(0, 1))

    # Back tends to have a "bluer" border than most fronts.
    blue_border_score = (b_mean[2] - (b_mean[0] + b_mean[1]) / 2.0) / 255.0

    # Center on back contains bright/varied pokeball; often higher contrast.
    c_std = float(c.std() / 255.0)

    # Tuned conservatively.
    if blue_border_score > 0.12 and c_std > 0.18:
        return FrontBackPrediction(label="back", confidence=0.70, method="heuristic")

    return FrontBackPrediction(label="front", confidence=0.55, method="heuristic")
