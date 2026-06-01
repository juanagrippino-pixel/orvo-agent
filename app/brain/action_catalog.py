"""Canonical D2C action-key catalog for operator and workflow projections.

This module is the service-layer source of truth for registered action keys.
Transports, workflow dry-runs, WhatsApp/report copy, and future executors should
project from this catalog instead of duplicating action metadata locally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.brain.security.redaction import redact_secrets

ActionMode = Literal["manual", "suggestion", "approval_required"]
ActionSideEffect = Literal["none", "case_transition", "case_comment", "operator_request", "external"]


@dataclass(frozen=True)
class ActionDefinition:
    """Registered action-key metadata.

    ``mode`` and ``side_effect`` describe what a workflow/executor would do after
    approval, idempotency, and audit gates. Projection callers must still respect
    ``api_enabled``; a registered action key is not automatically executable.
    """

    action_key: str
    label: str
    mode: ActionMode
    side_effect: ActionSideEffect
    api_enabled: bool = False
    api_mode: str | None = None
    status_effect: str | None = None
    requires_reason: bool = False
    requires_comment: bool = False
    input_fields: tuple[str, ...] = field(default_factory=tuple)
    requires_approval: bool = False
    case_families: tuple[str, ...] = field(default_factory=tuple)
    notes: str | None = None

    def operator_projection(self) -> dict[str, Any]:
        """Return the redacted stable contract used by internal operator APIs."""

        payload: dict[str, Any] = {
            "action_key": self.action_key,
            "label": self.label,
            "mode": self.api_mode or self.mode,
            "api_enabled": self.api_enabled,
            "status_effect": self.status_effect,
            "requires_reason": self.requires_reason,
            "requires_comment": self.requires_comment,
            "approval_required": self.requires_approval,
        }
        if self.input_fields:
            payload["input_fields"] = list(self.input_fields)
        if self.case_families:
            payload["case_families"] = list(self.case_families)
        if self.notes:
            payload["notes"] = self.notes
        redacted = redact_secrets(payload)
        return redacted if isinstance(redacted, dict) else payload


_ACTION_DEFINITIONS: tuple[ActionDefinition, ...] = (
    ActionDefinition(
        "acknowledge_case",
        "Acknowledge case",
        "manual",
        "case_transition",
        api_enabled=True,
        api_mode="manual_operator_mutation",
        status_effect="acknowledged",
    ),
    ActionDefinition(
        "add_comment",
        "Add comment",
        "manual",
        "case_comment",
        api_enabled=True,
        api_mode="manual_operator_mutation",
        requires_comment=True,
    ),
    ActionDefinition(
        "assign_owner",
        "Assign owner",
        "manual",
        "operator_request",
        api_enabled=True,
        api_mode="manual_operator_mutation",
        input_fields=("assignee_ref",),
    ),
    ActionDefinition(
        "dismiss_case",
        "Dismiss case",
        "manual",
        "case_transition",
        api_enabled=True,
        api_mode="manual_operator_mutation",
        status_effect="dismissed",
        requires_reason=True,
    ),
    ActionDefinition(
        "mark_in_progress",
        "Mark in progress",
        "manual",
        "case_transition",
        api_enabled=True,
        api_mode="manual_operator_mutation",
        status_effect="in_progress",
    ),
    ActionDefinition(
        "resolve_case",
        "Resolve case",
        "manual",
        "case_transition",
        api_enabled=True,
        api_mode="manual_operator_mutation",
        status_effect="resolved",
        requires_reason=True,
    ),
    ActionDefinition(
        "request_follow_up",
        "Request follow-up",
        "manual",
        "operator_request",
        api_mode="manual_operator_action",
    ),
    ActionDefinition(
        "request_external_action",
        "Request external action",
        "approval_required",
        "external",
        api_mode="approval_required_disabled",
        requires_reason=True,
        requires_approval=True,
        notes="Registered but disabled until governed approvals and durable idempotency exist.",
    ),
    ActionDefinition(
        "check_storefront",
        "Check storefront",
        "suggestion",
        "none",
        api_mode="suggestion_only",
        case_families=("sales_drop", "spend_without_orders"),
    ),
    ActionDefinition(
        "review_campaigns",
        "Review campaigns",
        "suggestion",
        "none",
        api_mode="suggestion_only",
        case_families=("spend_without_orders", "channel_mix_shift"),
    ),
    ActionDefinition(
        "confirm_stock",
        "Confirm stock",
        "suggestion",
        "none",
        api_mode="suggestion_only",
        case_families=("stockout_risk",),
    ),
    ActionDefinition(
        "pause_promotion",
        "Pause promotion",
        "approval_required",
        "external",
        api_mode="approval_required_disabled",
        requires_approval=True,
        case_families=("stockout_risk", "spend_without_orders"),
        notes="Recommendation only until approved automation exists.",
    ),
    ActionDefinition(
        "refresh_credentials",
        "Refresh credentials",
        "manual",
        "operator_request",
        api_mode="manual_operator_action",
        case_families=("data_stale",),
    ),
    ActionDefinition(
        "retry_connector",
        "Retry connector",
        "manual",
        "operator_request",
        api_mode="manual_operator_action",
        case_families=("data_stale",),
    ),
    ActionDefinition(
        "inspect_pending_orders",
        "Inspect pending orders",
        "suggestion",
        "none",
        api_mode="suggestion_only",
        case_families=("fulfillment_backlog",),
    ),
    ActionDefinition(
        "reply_pending_chats",
        "Reply pending chats",
        "suggestion",
        "none",
        api_mode="suggestion_only",
        case_families=("unanswered_conversations",),
    ),
)

ACTION_CATALOG: dict[str, ActionDefinition] = {definition.action_key: definition for definition in _ACTION_DEFINITIONS}
API_ENABLED_CASE_ACTION_KEYS: tuple[str, ...] = tuple(
    definition.action_key for definition in _ACTION_DEFINITIONS if definition.api_enabled
)


def workflow_action_registry() -> dict[str, ActionDefinition]:
    """Return registered action metadata for workflow dry-run validation."""

    return dict(ACTION_CATALOG)


def list_case_action_catalog(*, business_id: str) -> dict[str, Any]:
    """Return the internal operator action contract for one business.

    This is a projection over registered action keys. It explicitly marks catalog
    actions that are not enabled in this API slice so clients do not infer
    executable capabilities from docs or owner-facing copy.
    """

    redacted = redact_secrets(
        {
            "business_id": business_id,
            "api_enabled_action_keys": list(API_ENABLED_CASE_ACTION_KEYS),
            "actions": [definition.operator_projection() for definition in _ACTION_DEFINITIONS],
        }
    )
    return redacted if isinstance(redacted, dict) else {}
