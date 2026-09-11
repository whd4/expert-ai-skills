"""Data plane: create a session, stream it, and drive it to a real stop.

This is the half that costs money, so every session created here carries a
hard `budget`. There is no unbudgeted path in this module - a session with no
ceiling is how an agent loop quietly turns into a bill.

The loop implements the documented client patterns:
  * stream-first, then send (a stream opened after the send misses early events)
  * lossless reconnect - `events.list()` history is read on every (re)connect,
    deduped by event ID, and DISPATCHED through the same path as live events.
    SSE has no replay: an event emitted while the stream was down exists only
    in history, and a pending tool ask found there must be answered from there
    or the session deadlocks.
  * the correct idle gate - `session.status_idle` alone is NOT done; the session
    idles transiently while it waits on you. A `requires_action` idle carries
    `stop_reason.event_ids` naming exactly what it is waiting on; anything
    listed there that we have not yet answered gets answered.
  * every `agent.custom_tool_use`, and every `agent.tool_use` / `agent.mcp_tool_use`
    with `evaluated_permission == "ask"`, is answered exactly once.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from . import config

CONSOLE_URL = "https://platform.claude.com/workspaces/{workspace}/sessions/{session_id}"

# stop_reason.type values on session.status_idle. `requires_action` is the only
# one that means "keep reading"; everything else means the turn is over.
STOP_REQUIRES_ACTION = "requires_action"
TERMINAL_STOP_REASONS = frozenset({"end_turn", "retries_exhausted", "budget_reached"})

# Both built-in and MCP tool calls can be gated by `always_ask`; the
# confirmation shape is the same for both.
CONFIRMABLE_TOOL_EVENTS = frozenset({"agent.tool_use", "agent.mcp_tool_use"})

APPROVE_ASK = "ask"
APPROVE_ALLOW = "allow-all"
APPROVE_DENY = "deny-all"

CONTINUE, STOP = "continue", "stop"


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
    answered: int = 0
    denied: int = 0
    reconnects: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "stop_reason": self.stop_reason,
            "terminated": self.terminated,
            "tool_calls": self.tool_calls,
            "answered": self.answered,
            "denied": self.denied,
            "reconnects": self.reconnects,
            "errors": self.errors,
            "text": "".join(self.text),
        }


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field off an SDK model or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


# --------------------------------------------------------------------------
# create
# --------------------------------------------------------------------------


def create_session(
    client: Any,
    agent_id: str,
    environment_id: str,
    budget_dollars: float,
    title: str | None = None,
    vault_ids: list[str] | None = None,
    resources: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    agent_version: int | None = None,
) -> Any:
    """Create a budgeted, idle session.

    `initial_events` is deliberately NOT used: it starts the agent loop inside
    the create call, so the session is born `running` and the first events land
    before any stream is attached. We create idle, attach the stream, then send.

    When `agent_version` is known (apply records it), the session is pinned to
    it, so a concurrent `apply` cannot change what an already-planned run does.
    """
    if budget_dollars is None or budget_dollars <= 0:
        raise ValueError("a session budget is required - refusing to create an uncapped session")

    agent_ref: Any = agent_id
    if agent_version:
        agent_ref = {"type": "agent", "id": agent_id, "version": int(agent_version)}

    body: dict[str, Any] = {
        "agent": agent_ref,
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
    return client.beta.sessions.create(**body)


# --------------------------------------------------------------------------
# run loop
# --------------------------------------------------------------------------


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
        print(f"\n  [approve] AUTO-ALLOWED {tool_name!r} (--approve allow-all)", file=stream_out)
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


@dataclass
class _Loop:
    """Mutable state shared by the history drain and the live tail."""

    client: Any
    session_id: str
    approve: str
    handler: Callable[[str, dict[str, Any]], str]
    out: Any
    outcome: SessionOutcome
    seen: set[str] = field(default_factory=set)
    by_id: dict[str, Any] = field(default_factory=dict)
    answered: set[str] = field(default_factory=set)

    def send(self, event: dict[str, Any]) -> None:
        self.client.beta.sessions.events.send(session_id=self.session_id, events=[event])

    def answer(self, event: Any) -> bool:
        """Resolve one pending tool event. Returns True if something was sent."""
        event_id = _attr(event, "id")
        event_type = _attr(event, "type")
        if not event_id or event_id in self.answered:
            return False

        payload: dict[str, Any] | None = None
        if event_type == "agent.custom_tool_use":
            result = self.handler(_attr(event, "name", ""), _attr(event, "input", {}) or {})
            payload = {
                "type": "user.custom_tool_result",
                "custom_tool_use_id": event_id,
                "content": [{"type": "text", "text": result}],
            }
        elif event_type in CONFIRMABLE_TOOL_EVENTS and _attr(event, "evaluated_permission") == "ask":
            decision, message = _decide(event, self.approve, self.out)
            payload = {"type": "user.tool_confirmation", "tool_use_id": event_id, "result": decision}
            if decision == "deny":
                self.outcome.denied += 1
                if message:
                    payload["deny_message"] = message
        if payload is None:
            return False

        # Multiagent sessions: echo the originating thread so the answer lands
        # on the thread that asked.
        thread_id = _attr(event, "session_thread_id")
        if thread_id:
            payload["session_thread_id"] = thread_id

        self.send(payload)
        self.answered.add(event_id)
        self.outcome.answered += 1
        return True

    def dispatch(self, event: Any) -> str:
        """Fold one event in - from history or live - and say whether to stop."""
        event_id = _attr(event, "id")
        event_type = _attr(event, "type")

        # Dedupe gates rendering/counting only. Answering is gated by
        # `answered`, and terminal checks always run, so a terminal or pending
        # event replayed from history is never skipped.
        if event_id and event_id not in self.seen:
            self.seen.add(event_id)
            self.by_id[event_id] = event
            _handle(event, self.outcome, self.out)
        elif not event_id:
            _handle(event, self.outcome, self.out)

        if event_type == "agent.custom_tool_use" or event_type in CONFIRMABLE_TOOL_EVENTS:
            self.answer(event)
            return CONTINUE

        if event_type == "session.status_terminated":
            self.outcome.terminated = True
            return STOP

        if event_type == "session.status_idle":
            stop = _attr(event, "stop_reason") or {}
            reason = _attr(stop, "type")
            self.outcome.stop_reason = reason
            if reason != STOP_REQUIRES_ACTION:
                if reason not in TERMINAL_STOP_REASONS:
                    self.outcome.errors.append(f"unrecognised stop_reason {reason!r} - treating as terminal")
                return STOP
            # Waiting on us. The idle names exactly what it is waiting on;
            # answer anything there we have not already settled (covers a
            # pending ask whose own event we somehow never saw).
            for pending_id in _attr(stop, "event_ids", None) or []:
                if pending_id in self.answered:
                    continue
                pending = self.by_id.get(pending_id)
                if pending is None:
                    self.outcome.errors.append(
                        f"session is waiting on event {pending_id} which is not in history"
                    )
                    continue
                self.answer(pending)
            return CONTINUE

        return CONTINUE


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
    outcome = SessionOutcome(session_id=session_id)
    loop = _Loop(
        client=client,
        session_id=session_id,
        approve=approve,
        handler=custom_tool_handler or _default_custom_tool_handler,
        out=stream_out,
        outcome=outcome,
    )
    sent_prompt = False

    for attempt in range(max_reconnects + 1):
        try:
            with client.beta.sessions.events.stream(session_id=session_id) as stream:
                # The stream is open and buffering server-side. Drain history
                # first, through the same dispatch as the live tail.
                history, history_error = _fetch_history(client, session_id)
                if history_error:
                    outcome.errors.append(f"history read failed: {history_error}")
                    print(f"\n  [history] {history_error} - continuing on the live stream only",
                          file=stream_out)
                for event in history:
                    if loop.dispatch(event) == STOP:
                        return outcome

                if prompt and not sent_prompt:
                    loop.send({"type": "user.message", "content": [{"type": "text", "text": prompt}]})
                    sent_prompt = True

                for event in stream:
                    if loop.dispatch(event) == STOP:
                        return outcome

            # Stream ended without a terminal event - reconnect and re-read.
            if attempt >= max_reconnects:
                outcome.errors.append("stream ended without a terminal event")
                return outcome
            outcome.reconnects += 1
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # network drop, proxy reset, heartbeat timeout
            if attempt >= max_reconnects:
                outcome.errors.append(f"stream failed after {attempt + 1} attempts: {exc}")
                return outcome
            outcome.reconnects += 1
            print(
                f"\n  [stream] {type(exc).__name__}: reconnecting "
                f"({attempt + 1}/{max_reconnects})",
                file=stream_out,
            )

    return outcome


def _fetch_history(client: Any, session_id: str) -> tuple[list[Any], str | None]:
    """Every persisted event so far. Iterating the pager auto-paginates."""
    try:
        page = client.beta.sessions.events.list(session_id=session_id)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    if isinstance(page, list):
        return page, None
    try:
        return list(page), None
    except TypeError:
        data = _attr(page, "data")
        return (list(data) if data is not None else []), None


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
        error = _attr(event, "error")
        message = _attr(error, "message") if error is not None else None
        message = message or _attr(event, "message") or _attr(error, "type") or "unknown error"
        outcome.errors.append(str(message))
        print(f"\n  [error] {message}", file=stream_out)

    elif event_type == "session.usage":
        usage = _attr(event, "usage")
        cost = _attr(usage, "list_cost") if usage is not None else None
        if cost is not None:
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
