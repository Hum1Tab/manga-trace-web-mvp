from __future__ import annotations

import hashlib
import io
import struct
import zlib
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

MAGIC = b"MT1"


def seed64(*parts: object) -> int:
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\0")
    return int.from_bytes(h.digest(), "little")


def rng(*parts: object) -> np.random.Generator:
    return np.random.default_rng(seed64(*parts))


def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def bits_to_bytes(bits: Iterable[int]) -> bytes:
    arr = np.array(list(bits), dtype=np.uint8)
    arr = arr[: len(arr) - (len(arr) % 8)]
    return np.packbits(arr).tobytes()


def make_fixed_payload(text: str, max_bytes: int = 40) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) > max_bytes:
        raise ValueError(f"payload text too long: {len(raw)} bytes > {max_bytes}")
    body = MAGIC + struct.pack(">H", len(raw)) + raw
    crc = zlib.crc32(body) & 0xFFFFFFFF
    payload = body + struct.pack(">I", crc)
    total = 3 + 2 + max_bytes + 4
    return payload + b"\0" * (total - len(payload))


def parse_fixed_payload(data: bytes) -> tuple[str | None, str]:
    if len(data) < 9:
        return None, "too short"
    if data[:3] != MAGIC:
        return None, "magic mismatch"
    n = struct.unpack(">H", data[3:5])[0]
    end = 5 + n
    if end + 4 > len(data):
        return None, "length out of range"
    got = struct.unpack(">I", data[end : end + 4])[0]
    exp = zlib.crc32(data[:end]) & 0xFFFFFFFF
    if got != exp:
        return None, f"crc mismatch got={got:08x} expected={exp:08x}"
    try:
        return data[5:end].decode("utf-8"), "ok"
    except UnicodeDecodeError as e:
        return None, f"utf8 error: {e}"


def block_positions(w: int, h: int, block: int, margin: int) -> list[tuple[int, int]]:
    return [(x, y) for y in range(margin, h - margin - block + 1, block) for x in range(margin, w - margin - block + 1, block)]


def chip(key: str, bit_i: int, rep_i: int, block: int) -> np.ndarray:
    r = rng(key, "chip", bit_i, rep_i, block)
    p = r.choice(np.array([-1.0, 1.0], dtype=np.float32), size=(block, block))
    p -= p.mean()
    p /= float(p.std() or 1.0)
    yy, xx = np.mgrid[0:block, 0:block]
    cx = cy = (block - 1) / 2
    dist = np.maximum(np.abs(xx - cx), np.abs(yy - cy)) / max(cx, cy, 1)
    window = np.clip(1.0 - 0.35 * dist, 0.45, 1.0).astype(np.float32)
    return p * window


def visibility_weight(gray: np.ndarray) -> np.ndarray:
    g = gray.astype(np.float32)
    mid = 1.0 - np.abs(g - 128.0) / 128.0
    # high-detail areas hide noise better than flat white/black areas.
    gy, gx = np.gradient(g)
    edge = np.clip((np.abs(gx) + np.abs(gy)) / 32.0, 0.0, 1.0)
    weight = 0.20 + 0.80 * np.maximum(mid, edge * 0.85)
    return np.clip(weight, 0.15, 1.0).astype(np.float32)


def embed_payload_to_image(
    image: Image.Image,
    text: str,
    *,
    key: str,
    strength: float = 0.22,
    block: int = 16,
    repeat: int = 5,
    margin: int = 32,
    max_bytes: int = 40,
) -> Image.Image:
    img = image.convert("RGB")
    arr = np.asarray(img).astype(np.float32)
    h, w = arr.shape[:2]
    gray = np.asarray(img.convert("L")).astype(np.float32)
    positions = block_positions(w, h, block, margin)
    payload = make_fixed_payload(text, max_bytes=max_bytes)
    bits = bytes_to_bits(payload)
    needed = len(bits) * repeat
    if len(positions) < needed:
        raise ValueError(f"image too small: need {needed} blocks, have {len(positions)}. Try smaller --block or --repeat.")
    order = rng(key, "positions", w, h, block, margin, len(bits), repeat).permutation(len(positions))[:needed]
    out = arr.copy()
    for bit_i, bit in enumerate(bits):
        sign = 1.0 if int(bit) == 1 else -1.0
        for rep_i in range(repeat):
            x, y = positions[int(order[bit_i * repeat + rep_i])]
            local_gray = gray[y : y + block, x : x + block]
            local_weight = visibility_weight(local_gray)
            delta = sign * chip(key, bit_i, rep_i, block) * strength * local_weight
            out[y : y + block, x : x + block, :] += delta[:, :, None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def render_watermarked_bytes(
    base_image_path: str | Path,
    payload_text: str,
    *,
    key: str,
    format: str = "WEBP",
    quality: int = 92,
    strength: float = 0.22,
) -> bytes:
    with Image.open(base_image_path) as im:
        wm = embed_payload_to_image(im, payload_text, key=key, strength=strength)
    buf = io.BytesIO()
    if format.upper() == "WEBP":
        wm.save(buf, format="WEBP", quality=quality, method=4)
    elif format.upper() == "PNG":
        wm.save(buf, format="PNG")
    else:
        wm.save(buf, format=format)
    return buf.getvalue()


def extract_payload_from_images(
    original_path: str | Path,
    watermarked_path: str | Path,
    *,
    key: str,
    block: int = 16,
    repeat: int = 5,
    margin: int = 32,
    max_bytes: int = 40,
) -> dict:
    orig = Image.open(original_path).convert("RGB")
    wm = Image.open(watermarked_path).convert("RGB")
    if orig.size != wm.size:
        wm = wm.resize(orig.size)
    orig_arr = np.asarray(orig).astype(np.float32)
    wm_arr = np.asarray(wm).astype(np.float32)
    diff = (wm_arr - orig_arr).mean(axis=2)
    w, h = orig.size
    positions = block_positions(w, h, block, margin)
    total_bytes = 3 + 2 + max_bytes + 4
    bit_count = total_bytes * 8
    needed = bit_count * repeat
    if len(positions) < needed:
        return {"status": "image too small", "text": None, "confidence_score": 0.0}
    order = rng(key, "positions", w, h, block, margin, bit_count, repeat).permutation(len(positions))[:needed]
    decoded_bits = []
    scores = []
    for bit_i in range(bit_count):
        vals = []
        for rep_i in range(repeat):
            x, y = positions[int(order[bit_i * repeat + rep_i])]
            c = chip(key, bit_i, rep_i, block)
            vals.append(float((diff[y : y + block, x : x + block] * c).mean()))
        s = float(np.mean(vals))
        scores.append(abs(s))
        decoded_bits.append(1 if s > 0 else 0)
    raw = bits_to_bytes(decoded_bits)
    text, status = parse_fixed_payload(raw)
    return {
        "status": status,
        "text": text,
        "confidence_score": float(np.mean(scores) / (np.std(scores) + 1e-6)),
        "block": block,
        "repeat": repeat,
        "max_bytes": max_bytes,
    }
