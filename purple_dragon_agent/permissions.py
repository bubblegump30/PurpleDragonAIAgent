from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

VALID = {"allow", "ask", "deny"}

@dataclass(frozen=True)
class Decision:
    action: str
    policy: str
    approved: bool
    reason: str

class PermissionEngine:
    def __init__(self, policies: dict[str, str], approval_callback: Callable[[str, dict], bool] | None = None):
        self._policies = dict(policies)
        self.restricted = set()
        self._approval_callback = approval_callback

    def policy_for(self, action: str) -> str:
        if action in self.restricted: return "deny"
        value = self._policies.get(action, "deny")
        return value if value in VALID else "deny"

    def set_policy(self, action: str, policy: str) -> None:
        if policy not in VALID:
            raise ValueError(f"Invalid policy: {policy}")
        self._policies[action] = policy

    def snapshot(self) -> dict[str, str]:
        return dict(self._policies)

    def check(self, action: str, context: dict | None = None, *, require_approval: bool = False) -> Decision:
        context = context or {}
        policy = self.policy_for(action)
        if policy == "allow" and not require_approval:
            return Decision(action, policy, True, "Allowed by policy.")
        if policy == "deny":
            return Decision(action, policy, False, "Denied by policy.")
        if self._approval_callback is None:
            return Decision(action, policy, False, "Approval required but no approval handler is available.")
        approved = bool(self._approval_callback(action, context))
        return Decision(action, policy, approved, "Approved by user." if approved else "Rejected by user.")
