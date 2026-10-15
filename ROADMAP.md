# Purple Dragon AI Agent Roadmap

## v0.1.0 — Agent Foundation
- Agent execution loop
- Tool registry
- Permission gateway
- Workspace sandbox
- Audit log
- Local model connector
- Desktop control panel

## v0.1.1 — UI/UX Foundation Polish
- Neo Purple desktop interface

## v0.1.2 — Foundation Reliability
- Plan validation, main-thread event dispatch and process boundary controls

## v0.1.3 — High-DPI Interface & 3D Controls
- Raised buttons and startup DPI awareness

## v0.1.4 — Startup Repair
- Tcl-compatible tuple padding

## v0.1.5 — Windows Reliability & UI Verification
- Scrollable configuration pages, wrapped paths and correct disabled buttons
- Settings migration/validation, startup diagnostics and Windows verifier
- Windows visual acceptance remains pending

## v0.2.0 — Local File & Workspace Agent
- Bounded project metadata indexing and UTF-8 file previews
- Durable staged change sets and human-approved diffs
- Manual text snapshots and automatic change recovery snapshots
- Conflict-aware reviewed rollback and interrupted-apply recovery
- Windows visual acceptance remains pending

## v0.3.0 — Coding Agent
- Selected-source analysis and local-model planning using actual file context
- Validated full-file code proposals displayed as unified diffs
- Conservative offline Python function rename
- Language detection and Python/JSON syntax checks
- Human-reviewed application with full-context freshness guards
- Windows visual acceptance and live LM Studio verification remain pending

## v0.4.0 — Terminal + Test Runner
- Fixed Python test commands, streaming console, timeouts and cancellation
- Mandatory host-trust approval, framework detection and failure triage
- Explicit failure-to-Coding handoff and approval on each retry
- Optional Windows Sandbox unittest session export
- Windows/Sandbox runtime validation pending; arbitrary commands remain blocked

## v0.5.0 — Memory & Project Context
- Project-scoped local notes, decisions and bounded outcome history
- Keyword-ranked context preview and opt-in planner/coding integration
- User-controlled context/history switches and approval-gated memory changes
- Revision/generation guards and scoped clearing
- Windows visual acceptance and live model-context verification pending

## v0.6.0 — Research/Web Agent
- Approved user-supplied public HTTPS URLs with explicit domain allow/deny rules
- Bounded cached text, source IDs, retrieval timestamps and hashes
- Data-only source-cited research drafts and staged brief export
- Network approval, private-address/redirect refusal and reference-only content handling
- Windows visual and live-network/model acceptance pending; no autonomous crawling/search

## v0.6.6 — Windows Reliability & UI Verification
- UI readiness, startup timeout, runtime diagnostics and duplicate-instance prevention
- Safe settings upgrade with backup and retained workspace location
- Keyboard controls, viewport bounds, approval cancellation and display-scale checks
- Windows-native manual acceptance remains pending

## v0.6.7 — Local Model Connection Center
- Explicit local-server model discovery and available-model picker
- Selected-model inference smoke test, error classification and last-check status
- Session-local verification invalidation on configuration changes
- Actual LM Studio and Windows acceptance pending

## v0.7.0 — Git + GitHub Agent
- Workspace repository inspection, working/staged diffs and reviewed local branches/commits
- PR preparation with committed diff and stale remote-head/base checks
- Approval-gated GitHub HTTPS push, PR creation and draft/published release creation
- Windows and live GitHub acceptance pending

## v0.8.0 — Multi-Agent System
- Implemented bounded sequential coordinator and five role specialists
- Selected file/source scopes, opt-in proposals/tests, live handoffs and cancellation
- Shared permission gateway; failed/denied tools block later specialists
- Security heuristics and Release checklist explicitly limited; no certification
- 182 automated tests and native Linux WebView checks passed
- Windows and live LM Studio acceptance pending

## v0.9.0 — Security, Sandbox & Permission Center
- Implemented persistent path/tool denials and existing fine-grained Allow / Ask / Deny editor
- Implemented restrictive session profiles that preserve base policies and approvals
- Implemented Windows DPAPI secrets storage foundation; provider credential dispatch remains future work
- Implemented bounded static review and Security specialist integration
- Added execution-boundary status and mandatory reviewed Sandbox export; no automatic Sandbox launch
- 203 automated tests and 25 native Linux WebView checks passed
- Actual Windows DPAPI, Sandbox execution and display acceptance pending

## v0.9.5 — Release Candidate & Recovery
- Implemented local release integrity report with explicit pending acceptance
- Implemented automatic/manual configuration checkpoints and reviewed recovery
- Implemented renderer-independent damaged-settings recovery launcher
- Exposed existing conflict-aware workspace snapshot rollback controls
- 224 Python tests and 29 native Linux WebView checks passed
- Windows, live model/remote service and actual Sandbox/DPAPI acceptance pending

## v1.0.0 — Stable Permission-Controlled AI Platform
- Implemented hardened bridge/job status handling with retained permission/recovery contracts
- Implemented declarative Plugin API v1 and reviewed workflow execution
- Added Windows portable/recovery build pipeline and per-user installer definition
- Added manual CI artifact build and source/frozen integrity profiles; no automatic publication
- 245 Python tests and 32 native Linux WebView checks passed
- Actual Windows installer build/installed-app acceptance, DPAPI/Sandbox and live-service verification pending; public Windows stability is not certified

## v1.0.1 — Bug Fixes & Code Polish
- Corrected multiline inputs, stale reviews, recovery-list handling, worker lifecycle and audit polling
- Tightened direct file access, credential names, request isolation, settings destination and model validation
- Exposed the frozen host-test limitation; source tests retain existing approvals
- 262 automated tests and 35 native Linux WebView checks passed
- Windows installer/frozen GUI/DPAPI/Sandbox and live services still require actual target acceptance

## v1.0.2 — Windows Verification Compatibility
- Validated interpreter selection and visible source verification preflight
- Explicit byte-preserving newline writes and AST capability errors
- 268 normal/emulated-text-write tests and 35 Linux native checks passed
- Actual Windows acceptance pending

## v1.1.0 — In-app Guide
Searchable offline section help, contextual F1, replayable tour and local onboarding preferences.

## v1.2.0 — Conversation Center
Local saved chats, searchable history, rename/delete, recent dialogue context, code/copy controls and cooperative cancellation.

## v1.3.0 — Local Model Center 2.0
Generation controls, model-specific settings, honest connection diagnostics and loading/timeout guidance.

## v1.4.0 — Project Workspace 2.0
Searchable file tree, explicit selected coding context, full structured staged reviews and unsaved-form guards.

## v1.5.0 — Coding & Validation 2.0
Validated source context, reviewable multi-file reports, stronger stale-source checks and structured test outcomes.

## v1.6.0 — Agent Planning Center
Reviewable fixed plans, per-step progress, cooperative pause/cancel, explicit handoffs and reviewed failed-step retries.

### v1.7.0 — Memory & Research 2.0

Memory & Research 2.0 adds searchable notes and decisions, revision-checked editing and deletion with approval, and age-based review reminders. Preview selected project memory before using it. Research now previews the exact system and source context, rejects changed context before synthesis, and opens citations as cached source text. The session-only last attempted model request shows serialized input (or an explicitly truncated prefix); it does not prove the server received or used it. Cached research is untrusted context, and citations require human verification.

### v1.8.0 — Desktop Experience & Accessibility

Saved display preferences offer Fit, Readable (at least 100%) and Large (at least 125%) modes. Larger modes scroll horizontally and vertically instead of reducing text below the chosen scale. Stronger contrast affects live controls and content; original reference artwork is unchanged. Reduced motion also follows the operating-system preference. Keyboard users get a skip-to-content button, visible focus, focused section headings, named scrollable results, and navigation shortcuts. Covered conversation controls leave the tab order. Permission dialogs retain priority. These are accessibility improvements, not a claim of full WCAG or screen-reader certification.

### v1.9.0 — Windows Reliability & Release Trust

Release Trust provides read-only local integrity evidence, manifest SHA-256, runtime/dependency versions, WebView2 registry hints on Windows, and startup-log metadata. The copyable report excludes saved settings, workspace text, credentials, absolute executable paths and raw logs. Publisher identity remains explicitly unverified; source code has no Authenticode signature to inspect. Manifest verification now requires every referenced frontend script and stylesheet. Setup retains a local setup log; startup diagnostics safely bound and decode damaged logs. Application lock I/O errors are distinguished from duplicate instances, and lock handles close even when unlock fails.

### v2.0.0 — Purple Dragon AI Agent 2.0

Purple Dragon AI Agent 2.0 consolidates the existing platform around a new Platform Center under Tools. Its canonical section catalog links Workspace, Coding, Tests, Agent Planning, Memory, Research, Git, Plugins, Security, Recovery, Settings and Activity. A passive overview shows the last model verification state, last file-index count, task/approval state, session restrictions, saved policy counts and context settings. Suggested next steps explain missing setup without performing it. A guided inspect → validate/propose → review/apply → test → inspect-results workflow makes the approval boundaries visible. Advanced tool arguments remain available in a collapsible section.
