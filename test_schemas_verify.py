"""Verify schemas.py models work correctly."""
from agent.schemas import (
    ChatRequest, ChatResponse, ToolCallInfo,
    ResponseMetadata, SessionInfo, SSEEvent
)
from pydantic import ValidationError
from datetime import datetime

print("All models imported successfully")

# Test ChatRequest basic creation
req = ChatRequest(message="hello")
print(f"ChatRequest created: message='{req.message}', stream={req.stream}")

# Test validation: empty message rejected
try:
    ChatRequest(message="")
    print("ERROR: empty message should be rejected")
except ValidationError as e:
    print(f"OK: empty message rejected ({e.error_count()} error)")

# Test validation: temperature > 2.0 rejected
try:
    ChatRequest(message="hi", temperature=3.0)
    print("ERROR: temperature=3.0 should be rejected")
except ValidationError as e:
    print(f"OK: temperature=3.0 rejected ({e.error_count()} error)")

# Test validation: max_tokens <= 0 rejected
try:
    ChatRequest(message="hi", max_tokens=-1)
    print("ERROR: max_tokens=-1 should be rejected")
except ValidationError as e:
    print(f"OK: max_tokens=-1 rejected ({e.error_count()} error)")

# Test validation: top_p > 1.0 rejected
try:
    ChatRequest(message="hi", top_p=1.5)
    print("ERROR: top_p=1.5 should be rejected")
except ValidationError as e:
    print(f"OK: top_p=1.5 rejected ({e.error_count()} error)")

# Test ChatResponse creation
tool_info = ToolCallInfo(
    tool_name="rag_search",
    input_params={"query": "test"},
    output_summary="Found 3 docs",
    duration_ms=150.0
)
meta = ResponseMetadata(
    provider="vllm-local",
    model="Qwen/Qwen2.5-7B-Instruct",
    tokens_used=100,
    duration_ms=500.0,
    used_rag=True
)
resp = ChatResponse(
    reply="Hello!",
    session_id="sess-123",
    trace_id="trace-456",
    tool_calls=[tool_info],
    metadata=meta
)
print(f"ChatResponse created: reply='{resp.reply}', trace_id='{resp.trace_id}'")

# Test SessionInfo
session = SessionInfo(
    session_id="sess-789",
    created_at=datetime.utcnow(),
    last_active_at=datetime.utcnow(),
    message_count=5
)
print(f"SessionInfo created: session_id='{session.session_id}', count={session.message_count}")

# Test SSEEvent
event = SSEEvent(event="token", data='{"content": "hi"}')
print(f"SSEEvent created: event='{event.event}', data='{event.data}'")

# Test duration_ms >= 0 validation
try:
    ToolCallInfo(
        tool_name="test", input_params={},
        output_summary="x", duration_ms=-1.0
    )
    print("ERROR: negative duration_ms should be rejected")
except ValidationError as e:
    print(f"OK: negative duration_ms rejected ({e.error_count()} error)")

print("\nAll validations passed!")
