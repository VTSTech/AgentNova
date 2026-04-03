"""
AgentNova - Ollama Model Registry
Discovers Ollama models by reading manifests and mapping names to GGUF blob paths.

Ollama stores models as:
  ~/.ollama/models/manifests/registry.ollama.ai/<library>/<repo>/<tag>  (JSON manifest)
  ~/.ollama/models/blobs/sha256-<digest>                                (raw GGUF data)

Each manifest's "model" layer (mediaType: application/vnd.ollama.image.model)
points to a blob that IS the complete GGUF file - usable directly by llama-server.

No conversion or copying needed.

Written by VTSTech - https://www.vts-tech.org
"""

from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Default Ollama model storage paths
OLLAMA_MODELS_DIR = Path(os.environ.get("OLLAMA_MODELS", os.path.expanduser("~/.ollama/models")))
OLLAMA_MANIFESTS_DIR = OLLAMA_MODELS_DIR / "manifests" / "registry.ollama.ai"
OLLAMA_BLOBS_DIR = OLLAMA_MODELS_DIR / "blobs"

# GGUF magic number: "GGUF" in little-endian = 0x46475547
_GGUF_MAGIC = 0x46475547


@dataclass
class OllamaModel:
    """Represents a discovered Ollama model."""
    name: str               # e.g. "qwen2.5:7b"
    repo: str               # e.g. "qwen2.5"
    tag: str                # e.g. "7b"
    blob_path: Path         # absolute path to the GGUF blob
    size_bytes: int         # model layer size from manifest
    weight_quant: str       # detected weight quant (e.g. "Q4_K_M", "Q8_0", "F16")
    manifest_path: Path     # path to the manifest file
    model_digest: str       # sha256 digest of the model blob

    @property
    def size_human(self) -> str:
        """Return human-readable size string."""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 ** 2:
            return f"{self.size_bytes / 1024:.1f} KB"
        elif self.size_bytes < 1024 ** 3:
            return f"{self.size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{self.size_bytes / (1024 ** 3):.1f} GB"

    @property
    def exists(self) -> bool:
        """Check if the blob file exists on disk."""
        return self.blob_path.exists()


def _detect_weight_quant(blob_path: Path) -> str:
    """Read GGUF header to detect weight quantization - cleaner implementation.

    Scans KV metadata pairs for "general.file_type" which maps to
    GGML quant type constants.
    """
    try:
        with open(blob_path, "rb") as f:
            magic = struct.unpack("<I", f.read(4))[0]
            if magic != _GGUF_MAGIC:
                return _filename_heuristic(blob_path)

            version = struct.unpack("<I", f.read(4))[0]
            if version < 2 or version > 3:
                return _filename_heuristic(blob_path)

            n_tensors = struct.unpack("<Q", f.read(8))[0]
            n_kv = struct.unpack("<Q", f.read(8))[0]

            file_type = None

            for _ in range(n_kv):
                # Read key string
                # GGUF strings include trailing null byte in length - must strip
                key_len = struct.unpack("<Q", f.read(8))[0]
                key = f.read(key_len).decode("utf-8", errors="replace").rstrip('\x00')

                # Read value type
                val_type = struct.unpack("<I", f.read(4))[0]

                # Read value based on GGUF value type
                # Official type table from ggml.h (gguf_type enum):
                #   0=UINT8  1=INT8  2=UINT16  3=INT16  4=UINT32  5=INT32
                #   6=FLOAT32  7=BOOL  8=STRING  9=ARRAY  10=UINT64  11=INT64  12=FLOAT64
                if val_type == 8:  # GGUF_TYPE_STRING
                    val_len = struct.unpack("<Q", f.read(8))[0]
                    f.read(val_len)  # skip string value data
                elif val_type == 4:  # GGUF_TYPE_UINT32
                    val = struct.unpack("<I", f.read(4))[0]
                    if key == "general.file_type":
                        file_type = val
                elif val_type == 5:  # GGUF_TYPE_INT32
                    f.read(4)
                elif val_type == 6:  # GGUF_TYPE_FLOAT32
                    f.read(4)
                elif val_type == 7:  # GGUF_TYPE_BOOL
                    f.read(1)
                elif val_type == 0:  # GGUF_TYPE_UINT8
                    f.read(1)
                elif val_type == 1:  # GGUF_TYPE_INT8
                    f.read(1)
                elif val_type == 2:  # GGUF_TYPE_UINT16
                    f.read(2)
                elif val_type == 3:  # GGUF_TYPE_INT16
                    f.read(2)
                elif val_type == 9:  # GGUF_TYPE_ARRAY
                    arr_type = struct.unpack("<I", f.read(4))[0]
                    arr_len = struct.unpack("<Q", f.read(8))[0]
                    # Skip array elements based on element type
                    for _ in range(arr_len):
                        if arr_type == 8:  # STRING
                            elem_len = struct.unpack("<Q", f.read(8))[0]
                            f.read(elem_len)
                        elif arr_type in (4, 5, 6):  # UINT32, INT32, FLOAT32
                            f.read(4)
                        elif arr_type == 7:  # BOOL
                            f.read(1)
                        elif arr_type in (10, 11, 12):  # UINT64, INT64, FLOAT64
                            f.read(8)
                        elif arr_type in (0, 1):  # UINT8, INT8
                            f.read(1)
                        elif arr_type in (2, 3):  # UINT16, INT16
                            f.read(2)
                        elif arr_type == 9:  # nested ARRAY (rare)
                            # Nested arrays: recursively skip (simplified - just break)
                            break
                        else:
                            break  # Unknown element type
                elif val_type == 10:  # GGUF_TYPE_UINT64
                    f.read(8)
                elif val_type == 11:  # GGUF_TYPE_INT64
                    f.read(8)
                elif val_type == 12:  # GGUF_TYPE_FLOAT64
                    f.read(8)
                else:
                    # Unknown value type - can't parse further reliably
                    # Fall through to filename heuristic
                    import sys
                    print(f"  [GGUF debug] unknown value_type={val_type} for key='{key}'", file=sys.stderr)
                    break

                # Early exit once we have the answer
                if file_type is not None:
                    break

            if file_type is not None:
                return _gguf_file_type_to_name(file_type)

    except (OSError, struct.error, UnicodeDecodeError, OverflowError):
        pass

    return _filename_heuristic(blob_path)


# GGUF file_type constants (from ggml.h / ggml.py)
_GGUF_FILE_TYPES = {
    0: "F32",
    1: "F16",
    2: "Q4_0",
    3: "Q4_1",
    5: "Q4_1_SOME_K",
    6: "Q4_2",  # removed
    7: "Q4_3",  # removed
    8: "Q5_0",
    9: "Q5_1",
    10: "Q8_0",
    11: "Q8_1",
    12: "Q2_K",
    13: "Q3_K",
    14: "Q3_K_S",
    15: "Q3_K_M",
    16: "Q3_K_L",
    17: "Q4_K_S",
    18: "Q4_K_M",
    19: "Q5_K_S",
    20: "Q5_K_M",
    21: "Q6_K",
    22: "IQ2_XXS",
    23: "IQ2_XS",
    24: "IQ3_XXS",
    25: "IQ1_S",
    26: "IQ4_NL",
    27: "IQ3_S",
    28: "IQ2_S",
    29: "IQ4_XS",
    30: "I8",
    31: "I16",
    32: "I32",
    33: "I64",
    34: "F64",
    35: "IQ1_M",
    36: "BF16",
    # TQ types (TheTom's turboquant fork)
    37: "TQ4_1S",
    38: "TQ3_1S",
}


def _gguf_file_type_to_name(file_type: int) -> str:
    """Convert GGUF file_type constant to human-readable name."""
    return _GGUF_FILE_TYPES.get(file_type, f"UNKNOWN({file_type})")


def _filename_heuristic(blob_path: Path) -> str:
    """Fallback: detect quant from filename."""
    name = blob_path.stem.lower().replace("-", "").replace("_", "")
    # Sort by specificity (longer matches first)
    candidates = [
        ("iq4xs", "IQ4_XS"), ("iq4nl", "IQ4_NL"), ("iq4_nl", "IQ4_NL"),
        ("iq3xxs", "IQ3_XXS"), ("iq3s", "IQ3_S"), ("iq3_s", "IQ3_S"),
        ("iq2xxs", "IQ2_XXS"), ("iq2xs", "IQ2_XS"), ("iq2_s", "IQ2_S"),
        ("iq1m", "IQ1_M"), ("iq1_s", "IQ1_S"),
        ("q4km", "Q4_K_M"), ("q4_ks", "Q4_K_S"), ("q4_k_m", "Q4_K_M"),
        ("q5km", "Q5_K_M"), ("q5ks", "Q5_K_S"), ("q5_k_m", "Q5_K_M"),
        ("q6k", "Q6_K"), ("q6_k", "Q6_K"),
        ("q3km", "Q3_K_M"), ("q3ks", "Q3_K_S"), ("q3kl", "Q3_K_L"),
        ("q8_0", "Q8_0"), ("q8_1", "Q8_1"),
        ("q4_0", "Q4_0"), ("q4_1", "Q4_1"),
        ("q5_0", "Q5_0"), ("q5_1", "Q5_1"),
        ("q2_k", "Q2_K"), ("q3_k", "Q3_K"),
        ("f16", "F16"), ("bf16", "BF16"), ("f32", "F32"),
        ("tq41s", "TQ4_1S"), ("tq4_1s", "TQ4_1S"),
        ("tq31s", "TQ3_1S"), ("tq3_1s", "TQ3_1S"),
    ]
    for pattern, label in candidates:
        if pattern in name:
            return label
    return "UNKNOWN"


def _resolve_blob_path(digest: str) -> Path:
    """Convert a manifest digest to a blob file path.

    Manifest uses "sha256:<hex>" format.
    Blob file is stored as "sha256-<hex>" (colon replaced with dash).
    """
    return OLLAMA_BLOBS_DIR / digest.replace(":", "-")


def _parse_ollama_name(model_name: str) -> tuple[str, str]:
    """Parse an Ollama model name into (repo, tag).

    Examples:
        "qwen2.5:7b"           -> ("qwen2.5", "7b")
        "llama3.1:8b"          -> ("llama3.1", "8b")
        "mistral:7b-instruct"  -> ("mistral", "7b-instruct")
        "library/qwen2.5:7b"   -> ("qwen2.5", "7b")
    """
    if "/" in model_name:
        # Handle "library/qwen2.5:7b" format
        parts = model_name.split("/")
        model_name = parts[-1] if parts[-1] else parts[-2]

    if ":" in model_name:
        repo, tag = model_name.split(":", 1)
        return repo, tag

    # No tag - use "latest"
    return model_name, "latest"


def discover_models(
    ollama_dir: Optional[Path] = None,
    only_existing: bool = True,
) -> list[OllamaModel]:
    """Discover all Ollama models and map them to GGUF blob paths.

    Args:
        ollama_dir: Override Ollama models directory (default: ~/.ollama/models)
        only_existing: Only return models whose blob files exist on disk

    Returns:
        List of OllamaModel objects sorted by name
    """
    global OLLAMA_MANIFESTS_DIR, OLLAMA_BLOBS_DIR

    if ollama_dir:
        OLLAMA_MANIFESTS_DIR = ollama_dir / "manifests" / "registry.ollama.ai"
        OLLAMA_BLOBS_DIR = ollama_dir / "blobs"

    if not OLLAMA_MANIFESTS_DIR.exists():
        return []

    models: list[OllamaModel] = []

    # Walk the manifests directory
    # Structure: registry.ollama.ai/<library>/<repo>/<tag>
    for library_dir in sorted(OLLAMA_MANIFESTS_DIR.iterdir()):
        if not library_dir.is_dir():
            continue
        for repo_dir in sorted(library_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            for tag_file in sorted(repo_dir.iterdir()):
                if not tag_file.is_file():
                    continue

                # The tag file is the manifest JSON
                try:
                    manifest = json.loads(tag_file.read_text())
                except (json.JSONDecodeError, OSError):
                    continue

                repo = repo_dir.name
                tag = tag_file.name
                name = f"{repo}:{tag}"

                # Find the model layer (GGUF blob)
                model_layer = None
                for layer in manifest.get("layers", []):
                    if layer.get("mediaType") == "application/vnd.ollama.image.model":
                        model_layer = layer
                        break

                if not model_layer:
                    continue

                digest = model_layer.get("digest", "")
                size = model_layer.get("size", 0)
                blob_path = _resolve_blob_path(digest)

                # Detect weight quantization
                if blob_path.exists():
                    weight_quant = _detect_weight_quant(blob_path)
                else:
                    weight_quant = "UNKNOWN"

                model = OllamaModel(
                    name=name,
                    repo=repo,
                    tag=tag,
                    blob_path=blob_path,
                    size_bytes=size,
                    weight_quant=weight_quant,
                    manifest_path=tag_file,
                    model_digest=digest,
                )

                if only_existing and not model.exists:
                    continue

                models.append(model)

    return models


def find_model(
    model_name: str,
    ollama_dir: Optional[Path] = None,
) -> Optional[OllamaModel]:
    """Find a specific Ollama model by name.

    Args:
        model_name: Ollama model name (e.g. "qwen2.5:7b")
        ollama_dir: Override Ollama models directory

    Returns:
        OllamaModel if found, None otherwise
    """
    repo, tag = _parse_ollama_name(model_name)
    all_models = discover_models(ollama_dir=ollama_dir, only_existing=False)

    for model in all_models:
        if model.repo == repo and model.tag == tag:
            return model

    # Fuzzy match on just the repo part
    for model in all_models:
        if model.repo == repo:
            return model

    # Fuzzy match on full name
    for model in all_models:
        if model_name in model.name or model.name in model_name:
            return model

    return None


def recommended_turbo_config(weight_quant: str) -> dict[str, str]:
    """Get recommended TurboQuant config based on weight quantization.

    Based on TheTom's turboquant_plus findings:
    - Q8_0/F16/BF16 weights -> symmetric turbo (best compression)
    - Q4_K_M and lower -> asymmetric (keep K at q8_0, compress V only)

    Returns:
        Dict with 'cache_type_k' and 'cache_type_v' keys
    """
    wq = weight_quant.upper().replace("-", "_").replace(" ", "")

    # High-quality weights: symmetric is safe
    high_quality = {"F32", "F16", "BF16", "Q8_0", "Q8_1", "TQ4_1S", "TQ3_1S", "I8", "I16", "I32"}

    if wq in high_quality:
        return {
            "cache_type_k": "turbo3",
            "cache_type_v": "turbo3",
            "mode": "symmetric",
            "reason": f"{weight_quant} weights: symmetric turbo3/turbo3 safe",
        }

    # TurboQuant weight types: these are already compressed, go easy on KV
    if wq.startswith("TQ"):
        return {
            "cache_type_k": "q8_0",
            "cache_type_v": "turbo4",
            "mode": "asymmetric",
            "reason": f"{weight_quant} weights: asymmetric q8_0/turbo4 (double-quant protection)",
        }

    # Lower bit weights: asymmetric to protect attention quality
    return {
        "cache_type_k": "q8_0",
        "cache_type_v": "turbo4",
        "mode": "asymmetric",
        "reason": f"{weight_quant} weights: asymmetric q8_0/turbo4 (K compression stacks too much error)",
    }


__all__ = [
    "OllamaModel",
    "OLLAMA_MODELS_DIR",
    "OLLAMA_MANIFESTS_DIR",
    "OLLAMA_BLOBS_DIR",
    "discover_models",
    "find_model",
    "recommended_turbo_config",
    "_parse_ollama_name",
    "_resolve_blob_path",
]
