"""
Shared CLI arguments for AgentNova example scripts.

All test/example scripts can use these standard arguments:
  --force-react       Force ReAct text-based tool calling
  --use-mf-sys        Use Modelfile system prompt
  --model MODEL       Model override
  --debug             Enable debug output
  --acp               Enable ACP integration
  --num-ctx TOKENS    Context window size
  --num-predict TOKENS Max tokens to generate
  --fast              Fast mode preset (ctx=2048, predict=256)

Usage in example scripts:
    import argparse
    from agentnova.shared_args import add_shared_args, parse_shared_args

    parser = argparse.ArgumentParser(description="My test script")
    add_shared_args(parser)
    args = parser.parse_args()
    config = parse_shared_args(args)

Then use config.force_react, config.num_ctx, etc.
"""

import argparse
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SharedConfig:
    """Parsed shared configuration from CLI args or env vars."""
    force_react: bool = False
    use_modelfile_system: bool = False
    model: Optional[str] = None
    debug: bool = False
    acp: bool = False
    num_ctx: Optional[int] = None
    num_predict: Optional[int] = None
    fast: bool = False

    def __post_init__(self):
        """Apply --fast preset if specified."""
        if self.fast:
            if self.num_ctx is None:
                self.num_ctx = 2048
            if self.num_predict is None:
                self.num_predict = 256

    @property
    def model_options(self) -> dict:
        """Get model options dict for Agent constructor."""
        opts = {}
        if self.num_ctx is not None:
            opts["num_ctx"] = self.num_ctx
        if self.num_predict is not None:
            opts["num_predict"] = self.num_predict
        return opts


def add_shared_args(parser: argparse.ArgumentParser) -> None:
    """Add shared arguments to an argument parser.

    Args:
        parser: The ArgumentParser to add arguments to.
    """
    parser.add_argument(
        "--force-react",
        action="store_true",
        help="Force ReAct text-based tool calling for all models",
    )
    parser.add_argument(
        "--use-mf-sys",
        action="store_true",
        dest="use_modelfile_system",
        help="Use the system prompt from the model's Modelfile",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        metavar="MODEL",
        help="Model to use (overrides AGENTNOVA_MODEL env var)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )
    parser.add_argument(
        "--acp",
        action="store_true",
        help="Enable ACP (Agent Control Panel) integration",
    )
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        metavar="TOKENS",
        help="Context window size",
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=None,
        metavar="TOKENS",
        help="Maximum tokens to generate",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode: num_ctx=2048, num_predict=256",
    )


def parse_shared_args(args) -> SharedConfig:
    """Parse shared args into a SharedConfig, falling back to env vars.

    Args:
        args: Parsed argparse Namespace object.

    Returns:
        SharedConfig with values from args or env vars.
    """
    return SharedConfig(
        force_react=getattr(args, "force_react", False) or os.environ.get("AGENTNOVA_FORCE_REACT", "0") == "1",
        use_modelfile_system=getattr(args, "use_modelfile_system", False) or os.environ.get("AGENTNOVA_USE_MF_SYS", "0") == "1",
        model=getattr(args, "model", None) or os.environ.get("AGENTNOVA_MODEL"),
        debug=getattr(args, "debug", False) or os.environ.get("AGENTNOVA_DEBUG", "0") == "1",
        acp=getattr(args, "acp", False) or os.environ.get("AGENTNOVA_ACP", "0") == "1",
        num_ctx=getattr(args, "num_ctx", None) or _env_int("AGENTNOVA_NUM_CTX"),
        num_predict=getattr(args, "num_predict", None) or _env_int("AGENTNOVA_NUM_PREDICT"),
        fast=getattr(args, "fast", False) or os.environ.get("AGENTNOVA_FAST", "0") == "1",
    )


def _env_int(name: str) -> Optional[int]:
    """Read an integer from an environment variable."""
    val = os.environ.get(name)
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return None
