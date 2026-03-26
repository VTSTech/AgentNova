"""
⚛️ AgentNova — OpenResponses Types
Implements the OpenResponses specification for multi-provider, interoperable LLM interfaces.
Based on: https://github.com/openresponses/openresponses

Key Concepts:
- Items: Atomic units of context (message, function_call, reasoning)
- State Machines: Items have states (in_progress, completed, failed, incomplete)
- tool_choice: Control tool invocation behavior
- allowed_tools: Restrict which tools can be invoked
- Streaming Events: Semantic delta events and state transitions

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Literal, Optional, Union


# ============================================================================
# Response Status (State Machine)
# ============================================================================

class ResponseStatus(Enum):
    """
    Response lifecycle states as defined by OpenResponses.
    
    States:
        QUEUED: Response is waiting to be processed
        IN_PROGRESS: Model is currently generating
        COMPLETED: Response finished successfully
        FAILED: Response encountered an error
        INCOMPLETE: Response exceeded token budget
        CANCELLED: Response was cancelled by user
    """
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"


class ItemStatus(Enum):
    """
    Item lifecycle states as defined by OpenResponses.
    
    States:
        IN_PROGRESS: Model is emitting tokens for this item
        COMPLETED: Item is fully sampled/executed
        INCOMPLETE: Token budget exhausted while emitting
        FAILED: Item execution failed
    """
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


# ============================================================================
# Tool Choice
# ============================================================================

class ToolChoiceType(Enum):
    """
    Controls whether and how the model can invoke tools.
    
    AUTO: Model may call tools or respond directly (default)
    REQUIRED: Model MUST call at least one tool
    NONE: Model MUST NOT call any tools
    SPECIFIC: Model must call a specific tool
    """
    AUTO = "auto"
    REQUIRED = "required"
    NONE = "none"
    SPECIFIC = "specific"


@dataclass
class ToolChoice:
    """
    Tool choice configuration.
    
    Examples:
        ToolChoice("auto")  # Default
        ToolChoice("required")  # Must call at least one tool
        ToolChoice("none")  # No tools allowed
        ToolChoice.specific("calculator")  # Must call calculator
    """
    type: ToolChoiceType = ToolChoiceType.AUTO
    name: str | None = None  # For SPECIFIC type
    
    def __init__(
        self, 
        value: str | ToolChoiceType = "auto",
        name: str | None = None
    ):
        if isinstance(value, ToolChoiceType):
            self.type = value
        elif value == "auto":
            self.type = ToolChoiceType.AUTO
        elif value == "required":
            self.type = ToolChoiceType.REQUIRED
        elif value == "none":
            self.type = ToolChoiceType.NONE
        else:
            # Treat as specific tool name
            self.type = ToolChoiceType.SPECIFIC
            self.name = value
        self.name = name
    
    @classmethod
    def specific(cls, tool_name: str) -> "ToolChoice":
        """Create a tool choice that forces a specific tool."""
        return cls(type=ToolChoiceType.SPECIFIC, name=tool_name)
    
    def to_dict(self) -> dict:
        """Serialize to dict for API."""
        if self.type == ToolChoiceType.SPECIFIC:
            return {
                "type": "function",
                "name": self.name
            }
        return {"type": self.type.value}


# ============================================================================
# Content Types (UserContent vs ModelContent)
# ============================================================================

@dataclass
class InputText:
    """Text content from user."""
    type: Literal["input_text"] = "input_text"
    text: str = ""
    
    def to_dict(self) -> dict:
        return {"type": self.type, "text": self.text}


@dataclass
class InputImage:
    """Image content from user (base64 or URL)."""
    type: Literal["input_image"] = "input_image"
    source: str = ""  # base64 data or URL
    media_type: str = "image/png"
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "source": self.source,
            "media_type": self.media_type
        }


@dataclass
class OutputText:
    """Text content from model."""
    type: Literal["output_text"] = "output_text"
    text: str = ""
    annotations: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "text": self.text,
            "annotations": self.annotations
        }


@dataclass
class SummaryText:
    """Summary text for reasoning items."""
    type: Literal["summary_text"] = "summary_text"
    text: str = ""
    
    def to_dict(self) -> dict:
        return {"type": self.type, "text": self.text}


# Union types
UserContent = Union[InputText, InputImage]
ModelContent = Union[OutputText]


# ============================================================================
# Items
# ============================================================================

def _generate_id(prefix: str = "item") -> str:
    """Generate a unique item ID."""
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


@dataclass
class MessageItem:
    """
    Message item - represents a conversation turn.
    
    Items are the fundamental unit of context in OpenResponses.
    They can be provided as inputs or outputs.
    """
    id: str = field(default_factory=lambda: _generate_id("msg"))
    type: Literal["message"] = "message"
    role: str = "assistant"  # "user", "assistant", "system"
    status: ItemStatus = ItemStatus.COMPLETED
    content: list[ModelContent | UserContent] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "role": self.role,
            "status": self.status.value,
            "content": [c.to_dict() for c in self.content]
        }


@dataclass
class FunctionCallItem:
    """
    Function call item - represents a tool invocation.
    
    For externally-hosted tools, the developer executes the tool
    and returns the result in a follow-up request.
    """
    id: str = field(default_factory=lambda: _generate_id("fc"))
    type: Literal["function_call"] = "function_call"
    name: str = ""
    call_id: str = ""  # Unique identifier for the call
    arguments: str = "{}"  # JSON string
    status: ItemStatus = ItemStatus.COMPLETED
    
    def __post_init__(self):
        if not self.call_id:
            self.call_id = f"call_{uuid.uuid4().hex[:12]}"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "call_id": self.call_id,
            "arguments": self.arguments,
            "status": self.status.value
        }


@dataclass
class FunctionCallOutputItem:
    """
    Function call output - the result of a tool execution.
    
    This is provided as input when returning tool results.
    """
    id: str = field(default_factory=lambda: _generate_id("fco"))
    type: Literal["function_call_output"] = "function_call_output"
    call_id: str = ""  # Must match the function_call's call_id
    output: str = ""  # Result of the tool call
    status: ItemStatus = ItemStatus.COMPLETED
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "call_id": self.call_id,
            "output": self.output,
            "status": self.status.value
        }


@dataclass
class ReasoningItem:
    """
    Reasoning item - exposes the model's internal thought process.
    
    Providers may expose:
    - content: raw reasoning trace
    - encrypted_content: protected reasoning (opaque to client)
    - summary: summarized reasoning steps
    """
    id: str = field(default_factory=lambda: _generate_id("rsn"))
    type: Literal["reasoning"] = "reasoning"
    status: ItemStatus = ItemStatus.COMPLETED
    content: list[OutputText] = field(default_factory=list)
    encrypted_content: str | None = None
    summary: list[SummaryText] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "content": [c.to_dict() for c in self.content],
            "encrypted_content": self.encrypted_content,
            "summary": [s.to_dict() for s in self.summary]
        }


# Union of all item types
Item = Union[MessageItem, FunctionCallItem, FunctionCallOutputItem, ReasoningItem]


# ============================================================================
# Response Object
# ============================================================================

@dataclass
class Response:
    """
    Response object - the main output of the API.
    
    A Response contains:
    - id: Unique identifier for the response
    - status: Current state in the lifecycle
    - model: Model used for generation
    - input: The input items that were provided
    - output: The output items generated
    - usage: Token usage statistics
    - created_at: Timestamp of creation
    - completed_at: Timestamp of completion (if completed)
    - error: Error information (if failed)
    """
    id: str = field(default_factory=lambda: _generate_id("resp"))
    status: ResponseStatus = ResponseStatus.QUEUED
    model: str = ""
    input: list[Item] = field(default_factory=list)
    output: list[Item] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    error: dict | None = None
    
    # Configuration
    tool_choice: ToolChoice = field(default_factory=ToolChoice)
    allowed_tools: list[str] = field(default_factory=list)
    previous_response_id: str | None = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "model": self.model,
            "input": [i.to_dict() for i in self.input],
            "output": [i.to_dict() for i in self.output],
            "usage": self.usage,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "tool_choice": self.tool_choice.to_dict(),
            "allowed_tools": self.allowed_tools,
            "previous_response_id": self.previous_response_id
        }
    
    def mark_in_progress(self, debug: bool = False) -> None:
        """Transition to in_progress state."""
        if self.status == ResponseStatus.QUEUED:
            old_status = self.status
            self.status = ResponseStatus.IN_PROGRESS
            if debug:
                print(f"[OpenResponses.Response] State transition: {old_status.value} -> {self.status.value}")
    
    def mark_completed(self, debug: bool = False) -> None:
        """Transition to completed state."""
        old_status = self.status
        self.status = ResponseStatus.COMPLETED
        self.completed_at = time.time()
        if debug:
            print(f"[OpenResponses.Response] State transition: {old_status.value} -> {self.status.value}")
    
    def mark_failed(self, error: dict, debug: bool = False) -> None:
        """Transition to failed state."""
        old_status = self.status
        self.status = ResponseStatus.FAILED
        self.error = error
        self.completed_at = time.time()
        if debug:
            print(f"[OpenResponses.Response] State transition: {old_status.value} -> {self.status.value}")
            print(f"[OpenResponses.Response] Error: {error}")
    
    def mark_incomplete(self, debug: bool = False) -> None:
        """Transition to incomplete state (token budget exhausted)."""
        old_status = self.status
        self.status = ResponseStatus.INCOMPLETE
        self.completed_at = time.time()
        if debug:
            print(f"[OpenResponses.Response] State transition: {old_status.value} -> {self.status.value}")
    
    def add_output_item(self, item: Item, debug: bool = False) -> None:
        """Add an output item."""
        self.output.append(item)
        if debug:
            print(f"[OpenResponses.Response] Output item added: id={item.id}, type={item.type}")
    
    def get_final_answer(self) -> str | None:
        """
        Extract the final answer from output items.
        
        Returns the text content of the last message item with role 'assistant'.
        """
        for item in reversed(self.output):
            if isinstance(item, MessageItem) and item.role == "assistant":
                for content in item.content:
                    if isinstance(content, OutputText) and content.text:
                        return content.text
        return None


# ============================================================================
# Streaming Events
# ============================================================================

class EventType(Enum):
    """
    Streaming event types as defined by OpenResponses.
    
    State Machine Events:
        RESPONSE_QUEUED: Response is queued
        RESPONSE_IN_PROGRESS: Response started
        RESPONSE_COMPLETED: Response finished
        RESPONSE_FAILED: Response failed
        RESPONSE_INCOMPLETE: Response incomplete
    
    Delta Events:
        OUTPUT_ITEM_ADDED: New output item added
        OUTPUT_ITEM_DONE: Output item completed
        CONTENT_PART_ADDED: New content part added
        CONTENT_PART_DONE: Content part completed
        OUTPUT_TEXT_DELTA: Text delta
        OUTPUT_TEXT_DONE: Text completed
        FUNCTION_CALL_ARGUMENTS_DELTA: Function args delta
        FUNCTION_CALL_ARGUMENTS_DONE: Function args completed
    """
    # State machine events
    RESPONSE_QUEUED = "response.queued"
    RESPONSE_IN_PROGRESS = "response.in_progress"
    RESPONSE_COMPLETED = "response.completed"
    RESPONSE_FAILED = "response.failed"
    RESPONSE_INCOMPLETE = "response.incomplete"
    
    # Delta events
    OUTPUT_ITEM_ADDED = "response.output_item.added"
    OUTPUT_ITEM_DONE = "response.output_item.done"
    CONTENT_PART_ADDED = "response.content_part.added"
    CONTENT_PART_DONE = "response.content_part.done"
    OUTPUT_TEXT_DELTA = "response.output_text.delta"
    OUTPUT_TEXT_DONE = "response.output_text.done"
    FUNCTION_CALL_ARGUMENTS_DELTA = "response.function_call_arguments.delta"
    FUNCTION_CALL_ARGUMENTS_DONE = "response.function_call_arguments.done"


@dataclass
class StreamEvent:
    """
    Base class for streaming events.
    
    Events describe meaningful transitions in the response lifecycle.
    They are either state transitions or deltas from previous state.
    """
    type: EventType
    sequence_number: int = 0
    
    def to_sse(self) -> str:
        """Serialize to Server-Sent Events format."""
        import json
        data = self.to_dict()
        return f"event: {self.type.value}\ndata: {json.dumps(data)}\n\n"
    
    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "type": self.type.value,
            "sequence_number": self.sequence_number
        }


@dataclass
class ResponseEvent(StreamEvent):
    """State machine event for response lifecycle."""
    response: Response | None = None
    
    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.response:
            d["response"] = self.response.to_dict()
        return d


@dataclass
class OutputItemEvent(StreamEvent):
    """Event for output item changes."""
    item: Item | None = None
    output_index: int = 0
    
    def to_dict(self) -> dict:
        d = super().to_dict()
        d["output_index"] = self.output_index
        if self.item:
            d["item"] = self.item.to_dict()
        return d


@dataclass
class ContentPartEvent(StreamEvent):
    """Event for content part changes."""
    item_id: str = ""
    output_index: int = 0
    content_index: int = 0
    part: ModelContent | UserContent | None = None
    
    def to_dict(self) -> dict:
        d = super().to_dict()
        d["item_id"] = self.item_id
        d["output_index"] = self.output_index
        d["content_index"] = self.content_index
        if self.part:
            d["part"] = self.part.to_dict()
        return d


@dataclass
class TextDeltaEvent(StreamEvent):
    """Event for text delta."""
    item_id: str = ""
    output_index: int = 0
    content_index: int = 0
    delta: str = ""
    text: str = ""  # Full text so far (for output_text.done)
    
    def to_dict(self) -> dict:
        d = super().to_dict()
        d["item_id"] = self.item_id
        d["output_index"] = self.output_index
        d["content_index"] = self.content_index
        if self.delta:
            d["delta"] = self.delta
        if self.text:
            d["text"] = self.text
        return d


# ============================================================================
# Error Types
# ============================================================================

@dataclass
class Error:
    """
    Error object as defined by OpenResponses.
    
    Types:
        server_error: Internal server failure (500)
        invalid_request: Malformed request (400)
        not_found: Resource not found (404)
        model_error: Model execution error (500)
        too_many_requests: Rate limited (429)
    """
    message: str
    type: str = "server_error"  # server_error, invalid_request, not_found, model_error, too_many_requests
    code: str | None = None  # Specific error code
    param: str | None = None  # Related parameter
    
    def to_dict(self) -> dict:
        d = {"message": self.message, "type": self.type}
        if self.code:
            d["code"] = self.code
        if self.param:
            d["param"] = self.param
        return d


# ============================================================================
# Request Configuration
# ============================================================================

@dataclass
class RequestConfig:
    """
    Configuration for an API request.
    
    This replaces the various kwargs and configuration options
    with a structured, OpenResponses-compliant configuration.
    """
    model: str = ""
    
    # Tool configuration
    tools: list[dict] = field(default_factory=list)  # Tool definitions
    tool_choice: ToolChoice = field(default_factory=ToolChoice)
    allowed_tools: list[str] = field(default_factory=list)
    
    # Conversation continuation
    previous_response_id: str | None = None
    
    # Generation parameters
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    
    # Truncation behavior
    truncation: Literal["auto", "disabled"] = "auto"
    
    # Service tier (priority hint)
    service_tier: Literal["standard", "priority", "batch"] = "standard"
    
    # Debug options
    debug: bool = False
    
    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "tools": self.tools,
            "tool_choice": self.tool_choice.to_dict(),
            "allowed_tools": self.allowed_tools,
            "previous_response_id": self.previous_response_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "truncation": self.truncation,
            "service_tier": self.service_tier
        }


# ============================================================================
# Helper Functions
# ============================================================================

def create_message_item(
    role: str,
    text: str,
    status: ItemStatus = ItemStatus.COMPLETED
) -> MessageItem:
    """Create a simple message item with text content."""
    content = [OutputText(text=text)] if role == "assistant" else [InputText(text=text)]
    return MessageItem(
        role=role,
        status=status,
        content=content
    )


def create_function_call_item(
    name: str,
    arguments: dict | str,
    call_id: str | None = None
) -> FunctionCallItem:
    """Create a function call item."""
    import json
    args_str = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return FunctionCallItem(
        name=name,
        arguments=args_str,
        call_id=call_id or ""
    )


def create_function_call_output(
    call_id: str,
    output: str
) -> FunctionCallOutputItem:
    """Create a function call output item."""
    return FunctionCallOutputItem(
        call_id=call_id,
        output=output
    )


# Alias for consistency
create_function_call_output_item = create_function_call_output


__all__ = [
    # Status enums
    "ResponseStatus",
    "ItemStatus",
    
    # Tool choice
    "ToolChoiceType",
    "ToolChoice",
    
    # Content types
    "InputText",
    "InputImage",
    "OutputText",
    "SummaryText",
    "UserContent",
    "ModelContent",
    
    # Items
    "Item",
    "MessageItem",
    "FunctionCallItem",
    "FunctionCallOutputItem",
    "ReasoningItem",
    
    # Response
    "Response",
    
    # Events
    "EventType",
    "StreamEvent",
    "ResponseEvent",
    "OutputItemEvent",
    "ContentPartEvent",
    "TextDeltaEvent",
    
    # Error
    "Error",
    
    # Configuration
    "RequestConfig",
    
    # Helpers
    "create_message_item",
    "create_function_call_item",
    "create_function_call_output",
    "create_function_call_output_item",
]