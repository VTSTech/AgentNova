"""
⚛️ AgentNova R02 — Memory
Manages conversation history with a configurable sliding window and
optional LLM-based summarization to compress older turns.

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class Message:
    role: Role
    content: str
    tool_calls: list[dict] | None = None   # assistant tool invocations
    tool_call_id: str | None = None        # for tool-result messages
    name: str | None = None               # tool name for result messages

    def to_dict(self) -> dict:
        d: dict = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d

    @staticmethod
    def from_dict(d: dict) -> "Message":
        return Message(
            role=d["role"],
            content=d.get("content", ""),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
        )


class Memory:
    """
    Stores conversation turns and exposes a windowed view for the LLM.

    Parameters
    ----------
    system_prompt : str
        Injected as the first message every time `to_messages()` is called.
    max_turns : int
        Maximum number of user/assistant turns to keep in the active window.
        Older turns are archived (and optionally summarized).
    summary_model_fn : callable, optional
        If provided, called with (archived_text: str) -> summary: str
        when turns are archived. The summary is prepended as context.
    """

    def __init__(
        self,
        system_prompt: str = "",
        max_turns: int = 20,
        summary_model_fn=None,
    ):
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self._summary_model_fn = summary_model_fn

        self._history: list[Message] = []
        self._archived_summary: str = ""

    # ------------------------------------------------------------------ #
    #  Writing                                                             #
    # ------------------------------------------------------------------ #

    def add(self, role: Role, content: str, **kwargs) -> Message:
        msg = Message(role=role, content=content, **kwargs)
        self._history.append(msg)
        self._maybe_compress()
        return msg

    def add_user(self, content: str) -> Message:
        return self.add("user", content)

    def add_assistant(self, content: str, tool_calls: list[dict] | None = None) -> Message:
        return self.add("assistant", content, tool_calls=tool_calls)

    def add_tool_result(self, name: str, content: str, tool_call_id: str = "") -> Message:
        return self.add("tool", content, name=name, tool_call_id=tool_call_id)

    # ------------------------------------------------------------------ #
    #  Reading                                                             #
    # ------------------------------------------------------------------ #

    def to_messages(self) -> list[dict]:
        """Return the message list ready to pass to Ollama."""
        messages = []

        # System prompt (always first)
        sys_content = self.system_prompt
        if self._archived_summary:
            sys_content = (
                f"{sys_content}\n\n"
                f"=== Earlier conversation summary ===\n{self._archived_summary}"
            )
        if sys_content:
            messages.append({"role": "system", "content": sys_content})

        # Active history window
        for msg in self._history:
            messages.append(msg.to_dict())

        return messages

    def last_assistant_message(self) -> Message | None:
        for msg in reversed(self._history):
            if msg.role == "assistant":
                return msg
        return None

    def clear(self):
        self._history.clear()
        self._archived_summary = ""

    def __len__(self):
        return len(self._history)

    # ------------------------------------------------------------------ #
    #  Compression                                                         #
    # ------------------------------------------------------------------ #

    def _count_turns(self) -> int:
        """Count user/assistant turn pairs."""
        return sum(1 for m in self._history if m.role == "user")

    def _maybe_compress(self):
        if self._count_turns() <= self.max_turns:
            return

        # Archive the oldest half of turns
        archive_target = self.max_turns // 2
        archived: list[Message] = []
        remaining: list[Message] = list(self._history)
        turns_removed = 0

        new_remaining = []
        for msg in remaining:
            if turns_removed < archive_target:
                archived.append(msg)
                if msg.role == "user":
                    turns_removed += 1
            else:
                new_remaining.append(msg)

        self._history = new_remaining
        archived_text = "\n".join(
            f"{m.role.upper()}: {m.content}" for m in archived
        )

        if self._summary_model_fn:
            summary = self._summary_model_fn(archived_text)
        else:
            # Naive truncation fallback
            summary = archived_text[:800] + ("..." if len(archived_text) > 800 else "")

        if self._archived_summary:
            self._archived_summary += f"\n\n{summary}"
        else:
            self._archived_summary = summary

    # ------------------------------------------------------------------ #
    #  Serialisation                                                       #
    # ------------------------------------------------------------------ #

    def snapshot(self) -> dict:
        return {
            "system_prompt": self.system_prompt,
            "archived_summary": self._archived_summary,
            "history": [m.to_dict() for m in self._history],
        }

    @classmethod
    def from_snapshot(cls, data: dict, **kwargs) -> "Memory":
        mem = cls(system_prompt=data.get("system_prompt", ""), **kwargs)
        mem._archived_summary = data.get("archived_summary", "")
        mem._history = [Message.from_dict(d) for d in data.get("history", [])]
        return mem
