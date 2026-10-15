# v2.0.0 — Purple Dragon AI Agent 2.0

Purple Dragon AI Agent 2.0 consolidates the existing platform around a new Platform Center under Tools. Its canonical section catalog links Workspace, Coding, Tests, Agent Planning, Memory, Research, Git, Plugins, Security, Recovery, Settings and Activity. A passive overview shows the last model verification state, last file-index count, task/approval state, session restrictions, saved policy counts and context settings. Suggested next steps explain missing setup without performing it. A guided inspect → validate/propose → review/apply → test → inspect-results workflow makes the approval boundaries visible. Advanced tool arguments remain available in a collapsible section.

Added shared backend catalog/status contracts and passive-API regression tests. Closing display settings now restores focus immediately, avoiding an intermittent delay. Preserved the Neo Purple artwork and all permission gates. No installer publication or external release was performed.

# v1.9.0 — Windows Reliability & Release Trust

Release Trust provides read-only local integrity evidence, manifest SHA-256, runtime/dependency versions, WebView2 registry hints on Windows, and startup-log metadata. The copyable report excludes saved settings, workspace text, credentials, absolute executable paths and raw logs. Publisher identity remains explicitly unverified; source code has no Authenticode signature to inspect. Manifest verification now requires every referenced frontend script and stylesheet. Setup retains a local setup log; startup diagnostics safely bound and decode damaged logs. Application lock I/O errors are distinguished from duplicate instances, and lock handles close even when unlock fails.

# v1.8.0 — Desktop Experience & Accessibility

Saved display preferences offer Fit, Readable (at least 100%) and Large (at least 125%) modes. Larger modes scroll horizontally and vertically instead of reducing text below the chosen scale. Stronger contrast affects live controls and content; original reference artwork is unchanged. Reduced motion also follows the operating-system preference. Keyboard users get a skip-to-content button, visible focus, focused section headings, named scrollable results, and navigation shortcuts. Covered conversation controls leave the tab order. Permission dialogs retain priority. These are accessibility improvements, not a claim of full WCAG or screen-reader certification.

# v1.7.0 — Memory & Research 2.0

Memory & Research 2.0 adds searchable notes and decisions, revision-checked editing and deletion with approval, and age-based review reminders. Preview selected project memory before using it. Research now previews the exact system and source context, rejects changed context before synthesis, and opens citations as cached source text. The session-only last attempted model request shows serialized input (or an explicitly truncated prefix); it does not prove the server received or used it. Cached research is untrusted context, and citations require human verification.

Restored Plugins routing after a desktop regression check. Existing permission gates and Neo Purple styling remain.

# v1.6.0 — Agent Planning Center

- Added immutable, expiring, one-use previews of fixed sequential role plans.
- Added visible per-step state, tool counts, attempts and bounded role evidence.
- Added cooperative pause/resume and paused cancellation with honest queue status.
- Added reviewed failed-step retries with fresh coding context/test preview and unchanged approval gates.
- Bounded retry chains; retained terminal state across same-workspace settings changes while invalidating reviews.
- Kept SAFE MODE and all existing workspace/source/permission restrictions.

# v1.5.0 — Coding & Validation 2.0

- Added source validation with hashes and stale-preflight refusal before model requests.
- Added multi-file coding reports and dependency hashes in full diff review.
- Added framework/timeout controls and preview invalidation.
- Added structured test outcomes, recognized counts, bounded failures and copy-summary controls.
- Kept raw output and existing approval, source-context, staging and execution guards.
- Fixed fast tool-completion delivery races.

# v1.4.0 — Project Workspace 2.0

- Added searchable, bounded project tree and explicit eight-file coding selection.
- Added structured full per-file reviews with change labels, byte sizes and hashes.
- Added unsaved section-form warnings and permission-dialog priority.
- Prevented late reads from replacing newer editor contents; editor reads now require UTF-8 text.
- Preserved existing proposal, source-context, workspace and approval guards.

# v1.3.0 — Local Model Center 2.0

- Added validated generation controls, response limits and exact-ID model profiles.
- Added explicit form presets and save/load/delete profile controls.
- Added local-only copyable diagnostics with honest model listing and verification semantics.
- Fixed the hidden 60-second inference-test timeout cap and preserved discovery on inference failure.
- Added elapsed/phase feedback, actionable timeout/engine guidance and output-limit notices.

# v1.2.0 — Conversation Center

- Added bounded atomic local conversations isolated by workspace, search, rename, deletion confirmation and reopen.
- Added recent conversation reference for ordinary model chat without granting tool authority.
- Added safe fenced code rendering and clipboard controls.
- Added cooperative Stop with visible pending semantics and late-answer suppression.

# v1.1.1 — Chat & Tool Reliability

- Separated ordinary text answers from explicit model tool planning.
- Kept known commands deterministic with or without a connected model.
- Rejected unrequested planned paths before dispatching any step.
- Removed obsolete run_command from the model planner allowlist.
- Added actionable failure messages without unrelated fallback actions.

# v1.1.0 — In-app Guide

- Added searchable offline help for every section, contextual F1 and section Help buttons.
- Added a dismissible welcome card and replayable step-by-step tour.
- Preserves unsaved forms and gives real approval dialogs priority.
- Added model setup troubleshooting and clear execution/recovery boundary explanations.

# v1.0.2 — Windows Verification Compatibility

- Fixed Build-Windows.bat choosing an unsupported PATH interpreter ahead of the private environment.
- Added shared Python 3.10+/AST selection and a source preflight that prints the actual interpreter before discovering tests.
- Added version checks to app setup, native verification, diagnostics and offline recovery paths.
- Fixed Workspace.write_text translating LF to CRLF implicitly on Windows; supplied LF/CRLF are now preserved exactly.
- Replaced raw missing-AST AttributeError with a clear rename compatibility error while retaining pattern-binding safety checks.
- Added six compatibility regressions. 268 tests passed normally and under Windows text-write emulation; 35 native Linux WebView checks passed.
- Actual Windows batch/runtime/installer acceptance remains pending.

# v1.0.1 — Bug Fixes & Code Polish

- Fixed newline-separated selections and added a clickable checkpoint list.
- Invalidated cached reviews after settings/workspace changes and rejected asynchronously stale form reviews.
- Prevented frozen app binaries from being launched as Python test interpreters; surfaced the unsupported runtime boundary.
- Fixed final-tool cancellation success reporting and stuck jobs after audit/worker-start failures.
- Bounded audit-tail reads, filtered corrupt/non-object records and kept valid recovery entries visible alongside damaged records.
- Unified workspace link/hard-link protections, directory pruning and path formatting.
- Fixed application-folder settings persistence, request isolation and schema checks; validated model parameters/authority consistently.
- Rejected Windows device credential names and linked vault folders.
- Pruned build environments before manifest traversal, streamed hashes and removed unused imports.
- 262 Python tests and 35 native Linux WebView checks passed. Windows installer/runtime/live-service acceptance remains pending.

# v1.0.0 — Stable Permission-Controlled AI Platform

- Added stable declarative Plugin API v1: strict fixed-tool manifests, typed selected inputs, reviewed scopes, mandatory workflow/tool approvals, drift/expiry/replay guards, cancellation and bounded text output.
- Added working Plugins UI and two bundled workflows; executable code and remote plugin loading remain unavailable.
- Hardened bridge operation validation and corrected success reporting for tasks that execute no tools.
- Added frozen executable path support and distinct source/frozen distribution manifests with streaming integrity checks.
- Added Windows PyInstaller portable/recovery packaging, per-user Inno installer definition, SHA-256 sidecars and a manual read-only GitHub build workflow.
- Added refusal to overwrite build folders containing runtime/user data.
- 245 Python tests and 32 native Linux WebView checks passed; actual Windows installer compilation/installation and remaining Windows/live-service acceptance are pending.

# v0.9.5 — Release Candidate & Recovery

- Added Tools → Recovery with candidate integrity checks, settings checkpoints/reviewed restore and existing workspace snapshot rollback controls.
- Added automatic settings checkpoints before persistent settings/workspace changes.
- Added mandatory policy-controlled settings recovery, five-minute review expiry, source/disk/effective-state guards, pre-restore checkpoints and exact raw-byte preservation.
- Added Recover-Settings.bat and a renderer-independent offline CLI for corrupted JSON/invalid settings.
- Added SHA-256 release manifest and read-only release_check.py; verification launchers fail on drift instead of rebuilding the manifest.
- Added 21 recovery regressions, including actual offline CLI recovery, failed-write preservation and file-as-workspace refusal.
- 224 Python tests and 29 native Linux WebView checks passed. Real Windows acceptance remains pending; this is a source release candidate.

# v0.9.0 — Security, Sandbox & Permission Center

- Added session profiles, persistent denied-path/tool scopes, and honest execution-boundary status.
- Added default secret-file protection to the central workspace resolver; protected aliases are blocked and indexes/exports omit protected inputs.
- Added bounded static security reports with findings only, integrated into the team's Security specialist.
- Added Windows current-user DPAPI credential storage foundation with metadata-only desktop access, no plaintext fallback and no model/tool retrieval.
- Added mandatory Sandbox export approval and a direct center control.
- Added protected-path Git preflight covering current files, index and local history, including denied Git metadata.
- Added 21 security regressions; full suite: 203 tests passed. Native Linux WebView: 25 checks passed.
- Actual Windows DPAPI, Sandbox execution and Windows display acceptance remain pending.

# v0.8.0 — Multi-Agent System

- Added a bounded coordinator with Coding, Research, QA, Security and Release specialists.
- Added role/scope selection, opt-in staged coding and approved test execution, live handoffs and cancellation in Agents.
- Enforced deterministic role tools through the existing permission gateway; denial/failure stops downstream work.
- Bounded visible report sizes and prevented cancellation-before-worker-start from being cleared.
- Added ten workflow regression tests and two native desktop team checks.
- Sequential execution; Windows and live LM Studio acceptance remain pending.

# v0.7.0 — Git + GitHub Agent

- Added a Git + GitHub panel under Tools, and Git mode navigation under Agents.
- Added repository status, branches, recent commits, working diffs and staged diffs.
- Added local review proposals for branch creation, staged-only commits, pushes, pull requests and releases.
- Added mandatory action approvals and a separate scoped GitHub network approval for remote writes.
- Checks repository HEAD, current branch and full staged-object identifiers again before executing a reviewed operation; changed destinations and stale proposals are rejected.
- Pins commit author identity to the reviewed repository-local name and email.
- Disables repository hooks, external diff helpers, textconv, signing, credential helpers and interactive prompts for agent commands.
- Restricts remote writes to a validated github.com origin and uses the user's externally authenticated GitHub CLI account.
- Checks reviewed remote head/base commits before PR creation and an existing tag's resolved commit before release creation.
- Supports draft releases; push/release remain Deny by default. No force push, clone, pull, fetch, index staging, branch switching or Git LFS upload hooks are exposed.
- Cancels bounded Git subprocesses when the app closes; consumed write proposals are never automatically replayed.

# v0.6.7 — Local Model Connection Center

- Added explicit, asynchronous local-server discovery using the OpenAI-compatible /v1/models endpoint.
- Added an available-model picker with manual identifier entry retained.
- Added a separate tiny inference smoke test for the selected model; no workspace context or tool definitions are sent.
- Displays configured, testing, server-reachable, no-models, error and inference-verified states.
- Displays the last-check time and measured listing/inference latency; verification is session-local and is reset when model configuration changes.
- Classifies unreachable servers, timeouts, authentication requirements, missing endpoints, blocked redirects, malformed responses and missing models.
- Restricts discovery to loopback destinations, disables proxies and redirects, and bounds response sizes and model identifiers.
- Retains permission gates, the reference interface, completed bottom layout and Windows launcher fixes.

# v0.6.6 — Windows Reliability & UI Verification

- Waits for an actual UI-bridge readiness signal; a stalled renderer closes with a recorded startup error instead of remaining inert.
- Clears stale startup errors when the frontend connects successfully.
- Uses an OS-held app-folder lock to prevent simultaneous instances and configuration imports while the app is running.
- Fits initial window geometry and minimum size to the available logical display dimensions, including smaller screens.
- Added Ctrl+1 (Chat), Ctrl+2 (Tools), Ctrl+, (Settings), and Escape to leave a tool page. Approval cancellation remains rejection.
- Validates the Windows Python/.NET bridge before reusing the private environment.
- Added read-only runtime diagnostics for the interpreter, frontend files, settings and dependency versions.
- Added Upgrade-From-Previous.bat: validated settings import, automatic destination backup and retained workspace location. Previous application files, dependencies and workspace contents are not copied or modified.
- Expanded native verification to cover readiness, focus, keyboard shortcuts, approval cancellation and full bottom-control bounds.
- Avoids rereading the full audit log during unchanged idle polling.

# v0.6.5 — Complete Bottom Layout

- Extended the design canvas from 941 to 1010 logical pixels; the cropped reference no longer determines the control boundary.
- Completed the composer frame, full Send button, model picker, workspace footer and memory footer in HTML/CSS.
- Updated viewport fitting and initial native window height to include the completed bottom edge.
- Retained the v0.6.4 console-interpreter launcher repair.

# v0.6.4 — Windows Launcher Repair

- Launches with the validated private-environment python.exe; no dependency on pythonw.exe or its missing base executable.
- Hides the console using Windows Start-Process; falls back to a visible launch if necessary.
- Validates both the interpreter and WebView import before reuse.
- Rebuilds only a broken private dependency environment, retaining project configuration, workspace and recovery data.
- Prefers installed Python 3.13, 3.12, 3.11 or 3.10 for new environment setup.
- The reference UI and existing agent tools are unchanged.

# v0.6.3 — Supplied Reference UI

- Replaced the visible Tk approximation with a frameless native WebView desktop shell.
- Reused the supplied reference artwork intact for detailed neon framing, icons, dragon core, mode cards and header.
- Added real HTML controls over the artwork: conversation history, task composer, model settings, modes and status panels.
- Added working workspace, coding, test, research, memory, permission and audit pages in the new shell.
- Preserved the existing workspace sandbox, tool registry, mandatory approval gates, policy engine, local-model endpoint restrictions and recovery mechanisms.
- Added approval IDs with single-use resolution and rejection on shutdown.
- Rendered all tool, model and file output as inert text.
- Added one-time desktop dependency setup, startup diagnostics and current native verification.
- Removed the reference's sample statistics and sample discussion from the visible UI; runtime values and honest unavailable labels replace them.

# v0.6.2 — Reference Interface Implementation

- Three-column conversation dashboard follows the supplied neon interface.
- Supplied dragon artwork reused in the masthead and central core. No AI-generated images.
- Scalable angular panel borders, cyan and purple accents, dark conversation and composer.
- Mode buttons open existing working pages; recent actions come from the audit log.
- Model configuration, permissions, workspace and task indicators show real state.
- Sidebar retains all existing tools. Right column hides on narrower windows to preserve the conversation.
- No invented GPU metrics, context capacity, multi-agent capabilities or task queue.

# v0.6.1 — Neo Purple Visual Polish

- Richer black and plum surfaces with clean purple edges.
- Raised primary controls with layered upper highlights and lower shadow.
- Recessed task editor and clearer status-card depth.
- Selected navigation outlines and coordinated dark scrollbars.
- Existing SAFE MODE, approvals, tools and data remain functional.

# Changelog

## v0.1.1 — UI/UX Foundation Polish

### Added
- Full Neo Purple dark interface
- Single-window sidebar navigation
- Dashboard status cards
- Dedicated Permission Center
- Improved dark Agent Output console
- Improved Activity/Audit console
- Refined local-model Settings page
- About page and creator credit
- Purple Dragon application icon
- Clear SAFE MODE status throughout the UI

### Improved
- Better spacing and visual hierarchy
- More readable workspace path/status
- Improved action buttons with layered neon/3D styling
- Cleaner task workflow
- More visible permission state
- Dashboard updates after workspace/settings/permission changes

### Security
- No unrestricted mode added
- Existing permission gateway retained
- Workspace sandbox retained
- Dangerous/unavailable capabilities remain denied by default

## v0.1.3 — High-DPI Interface & 3D Controls
- Native raised buttons with bevel, shadow, focus, hover and pressed feedback.
- Startup Windows DPI awareness and proportional pixel layout scaling.
- Centered page headings, improved secondary-text contrast and recessed task field.
- Segoe UI/Consolas native text; no rasterized lettering or text glow.

## v0.1.4 — Startup Repair
- Preserve Tcl-compatible tuple padding during DPI scaling.
- Startup error logging and visible Windows error notification.
- Diagnostic launcher and real Tcl padding-parser regression tests.

## v0.1.5 — Windows Reliability & UI Verification
- Scrollable permissions/settings and wrapping workspace/status text.
- Correct disabled button hover/leave behavior.
- DPI-scaled wrap distances and canvas artwork.
- Backward-compatible configuration defaults, fail-closed invalid policies,
  actionable corrupt-settings errors, and atomic settings persistence.
- Python/py fallback for source verification and a temporary-data Windows GUI verifier.
- Clear stale startup logs after successful startup.

## v0.2.0 — Local File & Workspace Agent
- Workspace page with metadata index, file editor/preview and read-only diff review.
- Durable staged change sets; model writes stage only and human approval applies them.
- SHA-256 stale-source/review guards, atomic file replacement and interrupted-apply recovery.
- Per-workspace manual text snapshots, automatic change snapshots and reviewed rollback.
- Linked-path, hardlink, file-count and content-size limits.
- Audit events and permission controls for new operations; read policies enforced during staging.
- Updated Windows GUI verifier and transactional regression tests.

## v0.3.0 — Coding Agent
- Coding page for selected-source analysis and local LM Studio code proposals.
- Bounded real-source context, complete-response validation and per-file explanations.
- Python parse/compile and strict JSON checks without project code execution.
- Conservative offline top-level Python function rename preserving comments/strings/attributes.
- Full context hashes retained through staging/application, including unchanged selected files.
- Permission-controlled generation, staged unified diffs, human approval and existing rollback.
- Coding regression suite and expanded Windows smoke verifier.

## v0.4.0 — Terminal + Test Runner
- Fixed unittest/pytest detection, command previews and explicit host-execution approval.
- Streaming 100 KB console, bounded timeouts, cancellation and process lifetime cleanup.
- Windows kill-on-close Job Object with gated bootstrap; no arbitrary shell support.
- Failure triage, persistent bounded run results and explicit failure-to-Coding handoff.
- Optional unlaunched Windows Sandbox unittest export with copied read-only inputs,
  disabled networking/clipboard and a dedicated writable results share.
- Real process regression tests and expanded GUI verifier; Windows/Sandbox runtime pending.

## v0.5.0 — Memory & Project Context
- Project-scoped local SQLite notes, decisions and bounded outcome history.
- Search, context preview, entry editing/deletion and scoped clearing in a new Memory page.
- Optional keyword-ranked model reference context, disabled by default, with source IDs.
- History recording controls and no automatic copying of file/tool/model output bodies.
- Mandatory approval and revision/generation guards for memory changes/deletion/clearing.
- Backward-compatible memory settings and expanded regression/Windows smoke checks.

## v0.6.0 — Research/Web Agent
- Research page with user-controlled domain policy, URL preview and approved public HTTPS fetches.
- Pinned public-address connections, TLS hostname verification and bounded DNS/response reads.
- No redirects/proxies/cookies/auth headers/downloads/scripts or automatic link following.
- Project-scoped retained text sources with timestamps, hashes and instruction-like-content flags.
- Cached-source draft briefs with validated source IDs and optional local-model synthesis.
- Staged brief export through existing human-reviewed file changes and snapshot recovery.
- Approval-gated cache clearing, scrollable navigation and expanded regression/verifier coverage.
