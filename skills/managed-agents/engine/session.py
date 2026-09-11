"""Data plane: create a session, stream it, and drive it to a real stop.

This is the half that costs money, so every session created here carries a
hard `budget`. There is no unbudgeted path in this module - a session with no
ceiling is how an agent loop quietly turns into a bill.

The loop implements the documented client patterns:
  * stream-first, then send (a stream opened after the send misses early events)
  * lossless reconnect - read `events.list()` history and dedupe by event ID,
    because SSE has no replay
  * the correct idle gate - `session.status_idle` alone is NOT done; the session
    idles transiently while it waits on you
  * answer every `agent.custom_tool_use` and every `always_ask` `agent.tool_use`,
    or the session deadlocks waiting on a client that moved on
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from . import config

CONSOLE_URL = "https://platform.claude.com/workspaces/{workspace}/sessions/{session_id}"

# stop_reason values on session.status_idle that mean "stop reading".
TERMINAL_STOP_REASONS = frozenset({"end_turn", "retries_exhausted", "budget_reached"})

APPROVE_ASK = "ask"
APPROVE_ALLOW = "allow-all"
APPROVE_DENY = "deny-all"


def console_url(session_id: str, workspace: str = "default") -> str:
    """Link to the live Console trace.

    `workspace` is the workspace the API key belongs to - `default` is correct
    only when that is the org's Default workspace. The session response does not
    carry a workspace field, so this cannot be inferred.
    """
    return CONSOLE_URL.format(workspace=workspace, session_id=session_id)


@dataclass
class SessionOutcome:
    session_id: str
    stop_reason: str | None = None
    terminated: bool = False
    text: list[str] = field(default_factory=list)
    tool_calls: int = 0
    denied: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "stop_reason": self.stop_reason,
            "terminated": self.terminated,
            "tool_calls": self.tool_calls,
            "denied": self.denied,
            "errors": self.errors,
            "text": "".join(self.text),
        }


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field off an SDK model or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def create_session(
    client: Any,
    agent_id: str,
    environment_id: str,
    prompt: str,
    budget_dollars: float,
    title: str | None = None,
    vault_ids: list[str] | None = None,
    resources: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    """Create a budgeted session.

    `initial_events` is deliberately NOT used: it starts the agent loop inside
    the create call, so the session is born `running` and the first events land
    before any stream is attached. We create idle, attach the stream, then send.
    """
    if budget_dollars <= 0:
        raise ValueError("a session budget is required - refusing to create an uncapped session")

    body: dict[str, Any] = {
        "agent": agent_id,
        "environment_id": environment_id,
        "budget": config.budget_from_dollars(budget_dollars),
    }
    if title:
        body["title"] = title
    if vault_ids:
        body["vault_ids"] = vault_ids
    if resources:
        body["resources"] = resources
    if metadata:
        body["metadata"] = metadata

    # `prompt` is sent after the stream is open - see run_session().
    del prompt
    return client.beta.sessions.create(**body)


def _default_custom_tool_handler(name: str, tool_input: dict[str, Any]) -> str:
    """No handler registered: say so rather than leaving the session hanging."""
    del tool_input
    return (
        f"Tool {name!r} is declared on the agent but this client has no handler "
        "registered for it. Continue without it, or report that it is unavailable."
    )


def _decide(event: Any, mode: str, stream_out: Any) -> tuple[str, str | None]:
    """Resolve an always_ask tool call into (allow|deny, deny_message)."""
    tool_name = _attr(event, "name", "?")
    if mode == APPROVE_ALLOW:
        return "allow", None
    if mode == APPROVE_DENY:
        return "deny", "This client runs non-interactively and cannot approve tool calls."
    print(f"\n  [approve] agent wants to run {tool_name!r}", file=stream_out)
    print(f"  [approve] input: {_attr(event, 'input', {})}", file=stream_out)
    try:
        answer = input("  [approve] allow? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "deny", "Operator did not respond."
    if answer in {"y", "yes"}:
        return "allow", None
    return "deny", "Operator denied this call."


def run_session(
    client: Any,
    session_id: str,
    prompt: str | None = None,
    approve: str = APPROVE_ASK,
    custom_tool_handler: Callable[[str, dict[str, Any]], str] | None = None,
    stream_out: Any = None,
    max_reconnects: int = 3,
) -> SessionOutcome:
    """Stream a session to completion, answering everything it waits on."""
    stream_out = stream_out or sys.stdout
    handler = custom_tool_handler or _default_custom_tool_handler
    outcome = SessionOutcome(session_id=session_id)
    seen: set[str] = set()
    sent_prompt = False

    for attempt in range(max_reconnects + 1):
        try:
            with client.beta.sessions.events.stream(session_id=session_id) as stream:
                # Reconnect losslessly: the stream is open and buffering server
                # side, so drain history first and dedupe as the live tail
                # catches up. On the first pass this is usually empty.
                for event in _iter_history(client, session_id):
                    event_id = _attr(event, "id")
                    if event_id and event_id not in seen:
                        seen.add(event_id)
                        _handle(event, outcome, stream_out)

                if prompt and not sent_prompt:
                    client.beta.sessions.events.send(
                        session_id=session_id,
                        events=[
                            {"type": "user.message", "content": [{"type": "text", "text": prompt}]}
                        ],
                    )
                    sent_prompt = True

                for event in stream:
                    event_id = _attr(event, "id")
                    event_type = _attr(event, "type")

                    # Dedupe gates handling only. Terminal checks must run even
                    # for an already-seen event, or a terminal event replayed
                    # from history is skipped and the loop never exits.
                    if event_id is None or event_id not in seen:
                        if event_id:
                            seen.add(event_id)
                        _handle(event, outcome, stream_out)

                    if event_type == "agent.custom_tool_use":
                        result = handler(_attr(event, "name", ""), _attr(event, "input", {}) or {})
                        client.beta.sessions.events.send(
                            session_id=session_id,
                            events=[
                                {
                                    "type": "user.custom_tool_result",
                                    "custom_tool_use_id": event_id,
                                    "content": [{"type": "text", "text": result}],
                                }
                            ],
                        )
                        continue

                    if (
                        event_type == "agent.tool_use"
                        and _attr(event, "evaluated_permission") == "ask"
                    ):
                        decision, message = _decide(event, approve, stream_out)
                        payload: dict[str, Any] = {
                            "type": "user.tool_confirmation",
                            "tool_use_id": event_id,
                            "result": decision,
                        }
                        if decision == "deny":
                            outcome.denied += 1
                            if message:
                                payload["deny_message"] = message
                        client.beta.sessions.events.send(
                            session_id=session_id, events=[payload]
                        )
                        continue

                    if event_type == "session.status_terminated":
                        outcome.terminated = True
                        return outcome

                    if event_type == "session.status_idle":
                        stop = _attr(event, "stop_reason") or {}
                        reason = _attr(stop, "type")
                        outcome.stop_reason = reason
                        if reason == "requires_action":
                            # Waiting on us. The pending event was handled above
                            # (or will arrive next); keep reading.
                            continue
                        return outcome
            # Stream ended without a terminal event - reconnect and re-read.
            if attempt >= max_reconnects:
                outcome.errors.append("stream ended without a terminal event")
                return outcome
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # network drop, proxy reset, heartbeat timeout
            if attempt >= max_reconnects:
                outcome.errors.append(f"stream failed after {attempt + 1} attempts: {exc}")
                return outcome
            print(
                f"\n  [stream] {type(exc).__name__}: reconnecting "
                f"({attempt + 1}/{max_reconnects})",
                file=stream_out,
            )

    return outcome


def _iter_history(client: Any, session_id: str) -> list[Any]:
    try:
        page = client.beta.sessions.events.list(session_id=session_id)
    except Exception:
        return []
    data = _attr(page, "data")
    if data is not None:
        return list(data)
    try:
        return list(page)
    except TypeError:  # pragma: no cover
        return []


def _handle(event: Any, outcome: SessionOutcome, stream_out: Any) -> None:
    """Render one event and fold it into the outcome."""
    event_type = _attr(event, "type")

    if event_type == "agent.message":
        for block in _attr(event, "content", []) or []:
            if _attr(block, "type") == "text":
                text = _attr(block, "text", "")
                outcome.text.append(text)
                print(text, end="", flush=True, file=stream_out)

    elif event_type in {"agent.tool_use", "agent.mcp_tool_use", "agent.custom_tool_use"}:
        outcome.tool_calls += 1
        print(f"\n  [tool] {_attr(event, 'name', '?')}", file=stream_out)

    elif event_type == "session.error":
        message = _attr(event, "message") or str(_attr(event, "error", "unknown error"))
        outcome.errors.append(str(message))
        print(f"\n  [error] {message}", file=stream_out)

    elif event_type == "session.usage":
        usage = _attr(event, "usage") or {}
        cost = _attr(usage, "list_cost")
        if cost:
            print(f"\n  [usage] list cost so far: {config.format_cost(cost)}", file=stream_out)

    elif event_type == "agent.thread_context_compacted":
        print("\n  [context] compacted", file=stream_out)


def settle(client: Any, session_id: str, attempts: int = 10, delay: float = 0.2) -> str | None:
    """Wait for the queryable status to catch up with the stream.

    The SSE stream reports idle slightly before the session's status does, so a
    cleanup call fired straight off the stream intermittently 400s with
    "cannot delete/archive while running".
    """
    import time

    status = None
    for _ in range(attempts):
        try:
            session = client.beta.sessions.retrieve(session_id)
        except Exception:
            return None
        status = _attr(session, "status")
        if status != "running":
            return status
        time.sleep(delay)
    return status
