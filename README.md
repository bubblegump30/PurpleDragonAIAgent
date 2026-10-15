# Purple Dragon AI Agent v2.0.0

## Start

Extract this ZIP into a new folder. Run **Run-PurpleDragonAI.bat**.

The first run automatically creates a private Python environment and installs the desktop WebView renderer. Internet access is needed for this one-time setup. Later starts use the installed environment and open without the console window.

The launcher uses python.exe; pythonw.exe is not required. Python 3.12 or 3.13 is recommended. Python 3.10 or newer and Microsoft Edge WebView2 Runtime are required on Windows. If setup or startup fails, run **Diagnose-Startup.bat**. A startup failure is saved in logs/startup-error.log and shown in a Windows dialog.

## Reference design

The supplied neon design is used directly as the artwork skin. Its framing, dragon core, sidebar icons, mode cards and header are retained at their original coordinates. Actual conversation messages, editable inputs, tool pages, task state, model settings and audit entries replace the sample content. No new images were generated.

The native window is frameless, with working minimize, maximize, close and header dragging. The reference proportions scale together to fit the window. Wider or taller windows may have black margins so the artwork is not distorted.

Runtime values replace sample metrics and conversation; GPU, VRAM and context telemetry are shown as not reported. One controlled job runs at a time; a team job coordinates sequential specialists with live handoffs.

## Working controls

- Chat: send a controlled task; Ctrl+Enter also sends it. With the local model disabled, start with `scan workspace` or use the Tools pages.
- Agents: configure and start a coordinated team; inspect live specialist handoffs and cancel the workflow. Creative Tools remains available from the Chat mode cards.
- Tools: workspace files, code analysis and proposals, reviewed file application, snapshots, approved tests, domain-controlled research, permissions and audit history.
- Plugins: list, preview and approve local declarative Plugin API v1 workflows; all tool scopes and mandatory approvals remain active.
- Memory: review and save project notes and decisions.
- Settings: configure LM Studio, research domains, project context and permissions.
- Search: navigate to tools or find text in the current conversation.

SAFE MODE remains active. Allow / Ask / Deny policies and mandatory approvals still govern the original Python tools. No arbitrary shell commands or unrestricted autonomous mode were added.

## Upgrade

To keep your existing project, copy only `config/user_config.json`, `workspace`, and `logs` from your prior folder into this new folder. Keep the new `config/default_config.json` and renderer files. Recovery data already stored outside the app folder remains in its existing location.

## Verify

Run **Verify-Windows.bat** after the first successful setup. It runs the tests and opens a temporary verification window to check the native bridge, a real workspace task, navigation and three viewport sizes. See **VERIFICATION.md** for current checks. Historical reports are retained in **docs/archive/**.

The bottom layout is completed in code beyond the cropped reference artwork. The entire 1672 x 1010 canvas, including the Send button and footer cards, fits the available viewport.

## Reliability and upgrade

Only one instance can run from a given release folder. Close the app before running Verify-Windows.bat or importing settings.

After extracting this release and preparing it once with Run-PurpleDragonAI.bat, close the app and run Upgrade-From-Previous.bat. Enter your previous release folder when prompted. The helper validates settings before writing, backs up any existing destination configuration, and retains the previous workspace location. Keep the previous folder if it contains that workspace. It does not copy old dependencies or alter the previous installation.

Keyboard shortcuts: Ctrl+1 opens Chat, Ctrl+2 opens Tools, Ctrl+, opens Settings, Ctrl+Enter sends the current task. Escape leaves a tool page; closing an approval dialog rejects the operation.

Diagnose-Startup.bat is read-only. Verify-Windows.bat uses temporary project data and saves windows-verification.json. Automated checks do not replace the manual Windows display-scale checklist in WINDOWS-ACCEPTANCE.md.

## Local Model Connection Center

Open Settings and enter the local LM Studio OpenAI-compatible endpoint, normally http://127.0.0.1:1234/v1/chat/completions.

1. Press Refresh models / test server. This saves the local-model fields and requests a bounded read-only model list. The connector can remain disabled for this discovery check.
2. Choose an identifier from Models reported by the saved local server. Enable the connector if you intend to use it.
3. Press Test selected model. This saves your selection and sends a tiny inference prompt. It sends no workspace files, memory or tools; LM Studio may load the selected model to answer it.
4. A successful response marks the selected model Verified for this session. Changing endpoint, identifier or enabled state invalidates this result. The timestamp reflects the last test; this is not continuous monitoring.

A model appearing in the list is not proof that inference works. Server authentication tokens are not supported in this release; an authentication error is reported without sending credentials. GPU/VRAM/context telemetry remains not reported. No model downloads, server launch commands or unrestricted autonomous mode were added.

## Git + GitHub Agent

Open Tools → Git. The selected workspace must contain the repository. Enter its relative folder name, or `.` when the workspace itself is the repository root. Git must be installed and available on PATH.

Inspect the repository or read working/staged diffs. For a write, choose the operation, fill its fields and press Prepare review. Read the complete proposal in the output pane, then press Execute reviewed proposal. Every write requires explicit approval even when its policy is Allow. Changing form inputs invalidates the displayed proposal.

- Branch: creates a branch at the reviewed commit without switching the current branch.
- Commit: commits only changes already staged in your Git client. Configure user.name and user.email locally in the repository; this agent does not read global identity configuration.
- Push: sends the reviewed commit to the current branch of the validated GitHub origin, without force or automatic tag pushing. Git LFS upload hooks are unsupported; use your Git client for LFS pushes.
- Pull request: prepares title/body and a committed diff using a locally available base branch. The reviewed head and base must match GitHub when creating the PR; fetch/push externally if necessary before preparing a new review.
- Release: creates the reviewed draft or published release. The reviewed commit must already exist on GitHub. An existing tag must resolve to that same commit.

Remote operations require GitHub CLI (gh), already authenticated externally with your GitHub account. This release does not install Git/gh, start login, or publish anything automatically. Push and publish-release policies remain Deny by default. Set the specific policy to Ask under Permissions when you want to use it; GitHub network access has its own mandatory approval.

Only regular .git directories inside the workspace are supported. Linked worktrees, alternate object stores, repository config includes, URL rewrite rules, and custom repository HTTP/credential configurations are rejected. Existing hooks are not executed by these commands. This controlled Git command surface is not an OS sandbox.

After an interrupted or failed remote write, inspect the remote state before preparing another operation. GitHub can accept a request even if the response is lost; the agent does not automatically retry consumed proposals.

## v0.8.0 — Multi-Agent System

Open **Agents**, enter a goal, select specialist roles, and enter file paths and cached source IDs (one per line). Review that scope and press **Start reviewed team**.

- Coordinator orders selected specialists, caps execution at 32 tool calls and checks a 15-minute budget between calls. Local model/approval waits may extend elapsed time; this is not a hard process deadline.
- Coding analyzes selected files. The optional local-model proposal requires the existing approval gateway and only stages changes.
- Research reads selected cached sources and creates an approval-gated cited draft. Fetch sources through the Research page first.
- QA detects and previews supported Python tests. Opt-in execution requires approval. Tests run against current workspace files, not unapplied staged changes.
- Security scans selected current files for five risky API patterns. Findings need manual review; this heuristic is not a vulnerability audit or certification.
- Release indexes the current workspace and reports the remaining review, applied-file testing, Windows verification and Git publication steps. It does not certify readiness or publish.

Specialists run sequentially because they share the approval channel and local model. No self-spawning agents, arbitrary shell commands, automatic file application or remote writes are exposed. A denied or failed tool blocks later specialists. Cancellation rejects a pending approval and stops before the next tool; an active local-model request may finish first. Completed handoffs remain visible during the session and step outcomes enter the audit log.

The team continues to use existing Allow / Ask / Deny policies. To apply a staged proposal, leave Agents and review its diff in Workspace, approve application, then rerun QA against applied files. A completed team run can contain skipped work and is not proof of release readiness.

## v0.9.0 — Security, Sandbox & Permission Center

Open **Tools → Security**, or search for `security`.

1. Select a session profile. Standard uses saved policies; Read-only workspace blocks mutation, host tests, remote writes and Sandbox export; Sandbox export only preserves approved export while blocking workspace mutation, host tests and remote writes. Profiles restrict permissions; they cannot grant permissions or remove mandatory approvals. Profiles reset to Standard when the app restarts and survive settings/workspace changes during the session.
2. Configure protected file/folder prefixes and disabled tools. Rules are saved separately from the existing Allow / Ask / Deny policies. Denied paths are exact relative filenames or folder prefixes; no glob patterns. `apply_changes` and `git_execute` are also accepted tool restrictions.
3. Review selected source files. The report flags dynamic code, shell execution, unsafe deserialization, disabled TLS verification, likely embedded secrets and private-key material. Findings show categories and line numbers only. The review is limited to eight files, 80 KB and 100 findings, with explicit truncation. It is a heuristic, not security certification.
4. Check the execution boundary and export approved Windows Sandbox tests. Export is now a mandatory approval even when its policy is Allow. The app does not launch Sandbox; open the exported `.wsb` manually on a supported configured Windows PC. Executable presence does not prove feature readiness.
5. Save named credentials in the local encrypted storage foundation. Windows current-user DPAPI is required; non-Windows platforms refuse saving, with no plaintext fallback. Values are never returned through UI state, audit events, models or agent tools. This release does not inject stored credentials into providers; LM Studio and Git authentication remain unchanged. Values are briefly present in process memory while entered/encrypted; memory wiping is not guaranteed.

By default, built-in file tools exclude `.env`/`.env.*`, SSH/cloud credential folders and private key extensions. Broker `.secret` files and the `private-secrets` folder stay protected even if the ordinary switch is disabled. Rules cover resolved aliases and carry through source context, indexing, snapshots and Sandbox input export. Protected inputs are omitted from indexes/exports rather than copied. Git uses subprocesses, so a separate preflight refuses protected paths found in current workspace files, the selected index or any local history. Protected `.git` metadata also blocks Git. This can block a whole repository; use an external Git client or explicitly revise scope settings if needed. The checks inspect local history only and are bounded by the existing Git output limits.

These scopes govern built-in app access. They are not an operating-system sandbox: approved host tests can access other host files under your account. Windows Sandbox networking/clipboard are disabled; project input and Python are mapped read-only, and only the session Results folder is mapped writable. Treat results as untrusted files and never execute them. Existing saved snapshots, audit/history, model replies and cached research are not retroactively scrubbed by new path rules.

Credential ciphertext is stored in `private-secrets` in the release folder. Settings upgrade does not copy that folder. Keep the previous installation and re-enter credentials after upgrading; do not put credentials in prompts or workspace sources. Never share that folder in a release ZIP.

Reference specifications: [Windows Sandbox configuration](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file), [Windows CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).

Real Windows Edge WebView2/DPI, DPAPI save/replace/delete and Windows Sandbox execution remain pending. Linux native UI checks do not validate those Windows facilities.


## v0.9.5 — Release Candidate & Recovery

Open **Tools → Recovery** (or search `recovery`).

- **Candidate checks** verify bundled file sizes and SHA-256 values against `RELEASE-MANIFEST.json`, report missing/changed files, and list outstanding platform acceptance. These local checksums are not signed authenticity proof or stable-release certification. `release_check.py` provides the same read-only report from the command line; source/Windows verification launchers also check integrity.
- **Settings checkpoints** preserve normalized settings and an absolute workspace destination. Persistent settings/workspace saves create checkpoints first. The UI lists the latest 100; older checkpoint files are retained rather than automatically deleted. Checkpoints contain workspace locations, policy/model/research settings and other configuration metadata, not credential vault values or project file contents. Protect this folder from sharing.
- **Settings recovery** shows destination, changed sections, exact policies, model connection, research, memory and security settings before mandatory approval. The base `restore_settings` policy still applies, even when Allow. Recovery is blocked outside Standard session scope. A review expires after five minutes and rejects changes to the backup, disk configuration or active settings. The current valid settings get a rollback checkpoint and previous disk bytes get an inert raw `.bin` copy before the atomic replacement.
- **Offline recovery**: close all app instances and run `Recover-Settings.bat`. Choose a listed checkpoint ID, or enter `RESET`. Review the result and type `RESTORE` explicitly. It uses a working private Python environment or an installed Python launcher/interpreter, needs no desktop renderer, and holds the same release-folder instance lock. You can also run `python recover_settings.py --list`, `--backup-id ID`, or `--reset`. It refuses linked recovery files/folders and settings larger than 256 KB.
- **Default reset** restores default safe policies and disables the local connector. It retains a readable existing workspace setting; if the damaged JSON cannot be read, the default workspace in this release folder is used. It preserves damaged bytes, including semantically invalid settings, before replacement. No project files or credentials are deleted.
- **File recovery** exposes existing snapshots, rollback preparation, full diff review and approved restore. Pending edits must be applied/discarded first. Transaction snapshots refuse later conflicting edits; manual workspace snapshots restore reviewed current differences. New drift after preview is rejected at application.

Keep the prior release folder and workspace until Windows acceptance succeeds. The v0.9.5 candidate added recovery and integrity tooling. Current v1.0 implementation and distribution status appear below. Settings recovery changes configuration only; it does not recover application binaries, dependencies, workspace files, vault data or audit history. Recover a damaged package by re-extracting the original ZIP into a new folder, then importing settings through the existing upgrade helper.

`RELEASE-CANDIDATE-CHECKLIST.md` records the remaining checks required before v1.0.0. Do not regenerate the bundled manifest merely to dismiss unexpected drift. `build_manifest.py` is for maintainers deliberately packaging a reviewed source change.

## v1.0.0 — Stable Permission-Controlled AI Platform

This ZIP contains the v1.0 source platform. Extract it into a fresh folder and run Run-PurpleDragonAI.bat as before. For an existing project, keep the previous installation/workspace, then use Upgrade-From-Previous.bat after initial setup. Run integrity/Windows verification before using it as your primary installation.

Plugin API v1 is now implemented: local manifests describe one to eight fixed steps with explicit typed inputs. Open Plugins, list available IDs, prepare a scope review and approve the workflow. Bundled examples: `workspace-overview` with `{}`, and `source-review` with `{"paths":["source.py"]}`. Every step uses the same permission gateway. No external code, shell, policy changes, file application, Git publication or credential retrieval is exposed to plugins. See PLUGIN-API-v1.md.

The desktop bridge now rejects malformed operation names/types without starting a job. An unrecognized task with no executed tools reports failure rather than misleading success. The platform retains protected paths, review fingerprints, human-approved host tests, staged application, snapshot rollback, configuration recovery, bounded reports, single-job execution and sequential specialist teams.

### Windows build and installer pipeline

Build-Windows.bat remains a source verification launcher. To produce Windows artifacts, install Python 3.12 x64 and Inno Setup 6, then run `powershell -ExecutionPolicy Bypass -File .\Build-Windows.ps1 -Installer` on Windows. An internet connection is needed to install build dependencies; WebView2 must be available for the native verification step. The build stops on failed tests/integrity/native checks and refuses to overwrite staged runtime/user data. There is no skip-verification switch.

The pipeline uses a separate `.build-venv`, a portable onedir GUI executable, and a standalone onefile console recovery executable. It validates the frozen distribution through `PurpleDragonRecovery.exe --check-release`, produces a portable ZIP, optionally compiles an Inno per-user installer, and writes SHA-256 sidecars in dist. The installer defaults to LocalAppData\Programs\PurpleDragonAIAgent and does not require elevation; it creates app/recovery/uninstall shortcuts. Runtime configuration, logs, workspace and vault are not shipped inputs and are not explicitly deleted by the installer. Test upgrade/uninstall behavior before publication. The repository workflow is manual and uploads build artifacts only; it does not publish releases or request write access to repository contents.

**No Windows EXE/setup binary was built in this environment.** Build definitions are included; actual installer compilation, installed GUI/upgrade/uninstall, real DPAPI/Sandbox and live LM Studio/GitHub acceptance remain pending. The local source platform is tested; these pending facilities are not claimed verified stable. Artifacts built by the pipeline are unsigned. RELEASE-ACCEPTANCE.md is the current release gate checklist.

## v1.0.1 — Bug fixes & code polish

This maintenance build keeps the existing reference artwork, controls, SAFE MODE and approval requirements. Extract into a new folder; retain your previous workspace and use Upgrade-From-Previous.bat to import settings after initial setup.

Selected-file/source/path fields now accept both commas and separate lines. Recovery provides clickable valid checkpoints and keeps healthy settings/file checkpoints accessible when another record is damaged. Reviews are invalidated on core/settings/workspace changes; a delayed plugin/Git/settings preview cannot silently reactivate an edited selection.

Audit polling reads a bounded tail instead of the whole growing file, ignores malformed/scalar/deeply nested records, and tolerates unreadable logs in the status panel. A worker error is finalized even if writing its error audit record fails; failed thread creation releases the busy state. Audit failures still block tool execution where permission logging cannot be completed. If an error follows a tool effect, inspect state before retrying.

Direct workspace reads now reject links and hard links consistently with transaction previews. File listing prunes dependencies, version-control metadata and private build environments, and returns portable forward-slash paths. Manifests prune those directories before traversal and hash files in chunks. API payloads are copied before dispatch, unsupported fields/settings are rejected, and saves use the actual app folder. Credential names reject Windows device names and linked vault folders. Local-model settings reject invalid ports, query/fragment URLs, blank enabled-model identifiers and boolean temperatures.

A cancellation received while the final tool is finishing now reports cancelled rather than success; completed tool effects remain available and are not automatically rolled back. No permissions were loosened.

### Packaged test execution boundary

The frozen GUI executable is not a normal Python interpreter. Host test execution is explicitly unavailable in that runtime, so it cannot recursively launch the app as a test process. The Terminal page explains the limitation and disables the unsupported test/preview actions. Use the source installation with normal Python for host tests; packaged host-test support needs a separately validated interpreter integration. Sandbox export still requires Windows and a normal base Python installation. Actual installer compilation/installed-GUI, Windows DPAPI/Sandbox and live-service acceptance remain pending; this maintenance build does not claim those checks completed.

## v1.0.2 — Windows verification compatibility

The source verification launcher now prefers a validated project `.venv`, then compatible installed Python launcher versions, then a validated PATH interpreter. It requires Python 3.10+ and the standard AST pattern-matching APIs before importing application tests; it prints the selected version and executable. An incompatible runtime stops with instructions instead of producing AttributeError failures in rename tests. Run-PurpleDragonAI.bat also refuses an old private interpreter and prepares a compatible environment when available. If no compatible Python is installed, install Python 3.12 or 3.13 and rerun the app launcher. No older Python support or test skipping is implied.

Workspace text writes explicitly disable automatic newline translation. Supplied LF stays LF and supplied CRLF stays CRLF on every OS. Existing files, byte-level hashes, staged proposals and recovery checks retain their exact bytes; read behavior is unchanged. Offline rename now checks for its required AST APIs and gives an actionable error rather than AttributeError if invoked directly under an incompatible/shadowed AST module.

Extract this build into a new folder, run Run-PurpleDragonAI.bat to prepare the desktop environment, then run Build-Windows.bat. The latter verifies source and package integrity and does not build an EXE. Verify-Windows.bat uses the same source preflight before its native renderer checks. Recover-Settings.bat and diagnostics also use the runtime check. Keep the previous workspace and use the existing settings upgrade helper when needed.

268 tests passed normally and under simulated Windows pathlib write translation; 35 native Linux desktop checks passed. Simulation is not actual Windows execution. Windows batch selection, installer and remaining target-platform facilities still need actual Windows acceptance.

## In-app guide (v1.1.0)

Click **Guide · F1** in the header or press **F1** for the current section. Each section also has a Help button. Search offline help, read step-by-step instructions, or select **Start tour** to walk through every section. The welcome card can be dismissed and the tour reopened any time. Opening help preserves unsaved forms; only **Open this section** navigates away. Escape closes help. Permission dialogs take priority. Help never executes tools or changes permissions.

Includes LM Studio setup and connection troubleshooting, workspace and code review, host tests and Sandbox limits, research, Git/GitHub, multi-agent roles, plugins, memory, permissions, security, recovery and status indicators.

## v1.1.1 — Chat & Tool Reliability

Ordinary chat now answers in text without dispatching workspace tools. Code examples do not require a project file. Known commands (`list files`, `read test.txt`, `preview tests`, `run tests`, `git status`, and existing coding/research/memory commands) use deterministic routing even when a model is connected. For model-planned tools, explicitly use `plan task ...` and include real relative paths in the request. The whole plan is rejected before execution if it invents a file path. All normal tool schema, workspace, permission and mandatory approval checks remain active. Failed chat and invalid plans never fall back to unrelated tool execution. Task history can still be recorded locally under the existing memory policy.

## v1.2.0 — Conversation Center

Use **New chat** for a fresh conversation and **Saved chats** to reopen, search message text/titles, rename or permanently delete a chat after inline confirmation. Chats are stored locally per canonical workspace, up to 100 conversations and 200 messages per conversation, with a bounded 4 MB store. No automatic deletion occurs at capacity. Corrupt stores are preserved and reported rather than overwritten. Chats are plain local data, not encrypted; deletion does not clear the separate audit or task-memory history. Conversation data is excluded from release packages.

Ordinary model chat receives at most the latest 20 saved messages as reference; older messages remain readable locally. Prior messages never authorize tools. Code fences render as safe text with Copy code and Copy message controls. Raw HTML is not executed. Creative drafting remains a standalone writing request.

Stop task requests cancellation of a conversation job, denies a pending approval and prevents subsequent tool steps. An in-flight model HTTP request can take until its timeout to return; an already-running operation may finish. The app stays busy until that worker returns, discards a late answer and records the stopped status. Inspect effects of an already-started tool before retrying. This is not rollback.

## v1.3.0 — Local Model Center 2.0

Settings now exposes temperature (0–2), response limit (1–16,384 tokens; default 2048), and per-request timeout (1–300 seconds). These apply to ordinary model chat, drafting, coding proposals and explicit model plans. The connection smoke test still uses temperature 0 and at most 8 response tokens, with the full saved inference timeout. Discovery uses its own short timeout. A low response limit can truncate code or JSON; the model-reported `length` finish reason is surfaced in chat/draft output and diagnostics. Limits are requests to the server, not guaranteed response length or context capacity.

Precise, Balanced and Creative presets edit the form only. Save local model settings to activate them. Save profile & activate stores the three generation values under the exact model ID (up to 32 profiles). Selecting a listed model with a saved profile loads it into the form; save/test to activate. Load saved profile also works for a typed identifier. Deleting a saved profile leaves active settings unchanged. Profiles contain generation settings, not endpoints, secrets or models; saving one does not download or load a model. Existing configurations gain the default response limit and an empty profile catalog.

Show local diagnostics reads the saved target, generation settings, last check, failure code, model list, available request timings and last recognized finish reason. It makes no network call and contains no project files, permissions, workspace paths or credentials. Copy shown diagnostics copies the displayed report. Invalid legacy disabled endpoints are redacted. Clipboard behavior still needs target-Windows verification.

Listing is not proof that a model is loaded. A tiny successful inference verifies only that last request. The UI shows discovery/inference phase, elapsed time and request timeout during checks. Inference timeout guidance tells you to load the model manually in LM Studio and inspect Server Logs before retrying; discovery results are retained on inference failure. No automatic retries, model download, process startup, unload or hardware/context telemetry is claimed.

## v1.4.0 — Project Workspace 2.0

Workspace now has a searchable folder tree built from the permission-controlled file listing (up to 1000 files, with a visible limit notice). Search matches listed relative paths, not file contents. Refresh updates the listing and removes missing files from the selection. Choose folder still uses the native folder dialog and existing workspace boundaries. Linked/protected paths and ignored dependency/runtime folders retain their existing restrictions.

Check at most eight files, then choose Use selection in Coding. Selection is session-local to the workspace and does not send content to chat or a model. Coding shows one source path per line, preserving filenames with commas, and reads source only when you invoke the appropriate gateway tool. Existing source-size limits, protected paths and source-context hash guards remain active.

Opening files in the editor now uses strict UTF-8 text preview; binary/invalid UTF-8 files are refused instead of showing replacement characters that could be accidentally saved. Late reads do not overwrite editor contents changed during the request. A file read is inspection, Stage creates a pending proposal, Review shows it, and Apply requires separate approval. Editing a file/instruction form invalidates the UI review reference; the core still validates proposal IDs and current file hashes.

Full review now includes per-file create/modify/delete labels, exact before/after byte sizes, SHA-256 hashes and complete unified text diffs, including newline-only byte-change notices. Structured summaries are additive; the original full diff and mandatory approval/stale-state checks remain.

User edits to section forms trigger a Keep editing / Discard form edits & continue warning before navigation, workspace replacement, file replacement or the app’s custom Close button. Opening help does not leave the form. Escape chooses Keep editing, and permission dialogs take priority. Saving settings updates only the saved field baselines; unrelated unsaved settings remain dirty. Staged proposals are separate from form entries and are never applied by dismissing a warning. Form drafts are not persisted, and external OS termination/native window closure is not intercepted.

## v1.5.0 — Coding & Validation 2.0

In Coding, select one to eight existing source files, write an instruction and choose **Validate selected sources**. This reads through the permission gateway, checks Python parse/compile or JSON syntax where supported, reports other types as manual review, and captures exact source hashes. Validation never imports project modules or executes tests. Broken input syntax can still be sent for a requested repair; invalid generated Python/JSON replacements reject the entire proposal before any file is staged.

The Coding panel requires a validation matching its current files and instruction before **Propose staged changes**. It supplies those hashes to the core, which refuses stale or mismatched source context before contacting the model. Existing direct/CLI coding calls remain compatible and retain source consistency checks during context reading, after generation, at staging and at apply. A change to any selected dependency, even an unchanged file, still invalidates application. Validation is a stale-state constraint, not authorization to run tools.

Multi-file proposal reports show the model summary, per-file reasons and syntax-check results. Nothing is automatically applied. **Review full diff** shows complete diffs and dependency hashes; **Apply reviewed changes** still requires a separate permission decision. Source validation and proposal explanations are session UI reports; pending proposal files and their source dependency hashes retain existing durable recovery behavior.

Terminal now exposes framework and 1–600 second timeout controls. Preview the current command before requesting execution; changing options invalidates the UI preview. The gateway still constructs the exact fixed command and requires approval. Host tests execute current files on disk, not unapplied staged edits, with your account access. No arbitrary shell, automatic installation, automatic retry or automatic repair was added.

Completed runs have a parsed outcome, recognized counts, a bounded list of failure identifiers (first 20, each bounded), raw output and a copy-summary control. Counts/failure names are heuristics from untrusted process output, not independent evidence or a security certification. Empty discovery, unrecognized success output, truncation, cancellation and timeout are not labeled passed. Raw output remains bounded to the most recent 100 KB. Existing saved test-result files now include the structured summary. Cancellation continues using the runner’s process-tree controls.

Fixed an asynchronous UI race in which a completed tool result could be marked handled before its requesting UI attached. Completion is now consumed only by the matching request.

## v1.6.0 — Agent Planning Center

Open **Agents**, enter a goal, select roles and explicit paths/cached source IDs, then choose **Prepare plan · no tools**. Inspect the exact fixed sequential steps, inputs, skipped work and limits before **Start reviewed plan**. Preparing does not read source, contact a model or execute tools. Reviews are server-held immutable copies, expire after five minutes, and are consumed once. Editing the form requires a new review. The new desktop controls start a reviewed ID; existing direct team requests remain compatible and use the same fixed workflow and gateway.

Progress lists every pending/running/completed/failed/skipped step, actual tool-call count, active role, attempt and bounded role handoffs. Roles remain deterministic sequential specialists, not parallel agents or an open-ended autonomous planner. Coding proposals and QA host tests are opt-in; all permission/mandatory approval gates remain. A Coding proposal is bound to hashes from that run’s source analysis. Release performs indexing/checklist work only; completion is not release certification. No application, commit, push or publication step was added.

**Pause after current tool** requests a boundary pause. An active model/tool or pending permission decision must return first; it is not process suspension. While paused the task remains busy and the queue says Paused. **Resume plan** retains permissions and stale-source constraints. **Cancel plan** cancels an active test process through existing controls, releases pending approval, and prevents later steps. In-flight operations may finish and their effects remain. Pausing/cancelling never rolls back edits or other tool effects.

A blocked plan can **Prepare failed-step retry**. Review the prior error and remaining steps, then choose **Start reviewed retry**. Successful steps are not automatically replayed. A failed Coding proposal retry first analyzes its source again; a failed test retry first previews the command and still requires a new execution approval. An operation may have had effects before reporting failure: inspect evidence before agreeing to repeat it. Retries are bounded to three per chain. Cancelled or completed runs require a new plan, not a failed-step retry.

Each attempt permits up to 32 tool calls and a 900-second wall-clock budget, including paused time, checked between tools and while paused. This is not a hard preemption deadline for an active request. Same-workspace settings changes retain the terminal run summary but invalidate prepared reviews; prepare a fresh retry. Switching workspace resets the run state. Plans, handoffs and compact prior-attempt summaries are session-local and are not restart-resumable; existing audit logging and tool artifacts remain separate. Editing/leaving a form does not modify or cancel a running plan.

## v1.7.0 — Memory & Research 2.0

Memory & Research 2.0 adds searchable notes and decisions, revision-checked editing and deletion with approval, and age-based review reminders. Preview selected project memory before using it. Research now previews the exact system and source context, rejects changed context before synthesis, and opens citations as cached source text. The session-only last attempted model request shows serialized input (or an explicitly truncated prefix); it does not prove the server received or used it. Cached research is untrusted context, and citations require human verification.

Open Memory to search, edit, or preview notes. Open Tools → Research, fetch permitted sources, select up to five cached sources, preview the exact context, then request a cited draft. Refresh the preview after changing the question or sources.

## v1.8.0 — Desktop Experience & Accessibility

Saved display preferences offer Fit, Readable (at least 100%) and Large (at least 125%) modes. Larger modes scroll horizontally and vertically instead of reducing text below the chosen scale. Stronger contrast affects live controls and content; original reference artwork is unchanged. Reduced motion also follows the operating-system preference. Keyboard users get a skip-to-content button, visible focus, focused section headings, named scrollable results, and navigation shortcuts. Covered conversation controls leave the tab order. Permission dialogs retain priority. These are accessibility improvements, not a claim of full WCAG or screen-reader certification.

Open **Display & accessibility** in the sidebar or press **Ctrl+Alt+A**. Choose a scale, contrast and motion settings, then save. Restore display defaults returns to Fit. Shortcuts: Alt+1 Chat, Alt+2 Tools, Alt+3 Workspace, Alt+4 Settings. F1 opens section help. Navigation still checks unsaved edits; no shortcut grants approval.

## v1.9.0 — Windows Reliability & Release Trust

Release Trust provides read-only local integrity evidence, manifest SHA-256, runtime/dependency versions, WebView2 registry hints on Windows, and startup-log metadata. The copyable report excludes saved settings, workspace text, credentials, absolute executable paths and raw logs. Publisher identity remains explicitly unverified; source code has no Authenticode signature to inspect. Manifest verification now requires every referenced frontend script and stylesheet. Setup retains a local setup log; startup diagnostics safely bound and decode damaged logs. Application lock I/O errors are distinguished from duplicate instances, and lock handles close even when unlock fails.

Open Tools → Recovery → **Inspect release trust**, or run **Verify-Release.bat** in a source installation. Frozen builds use the Recovery screen. No tools are installed and no permissions change. Use Diagnose-Startup.bat locally for detailed startup errors; review its raw output before sharing. Failed dependency setup is retained in logs/setup.log.

The accompanying ZIP .sha256 file records archive bytes. To compare with an independently trusted expected value, run `powershell -NoProfile -File .\Verify-Download.ps1 -Archive "path-to-zip" -ExpectedSHA256 "64-hex-characters"`. Without ExpectedSHA256 the helper only calculates the hash. Matching a checksum from the same download location does not prove publisher identity. This release includes no signing certificate and makes no Defender or SmartScreen acceptance claim.

## v2.0.0 — Purple Dragon AI Agent 2.0

Purple Dragon AI Agent 2.0 consolidates the existing platform around a new Platform Center under Tools. Its canonical section catalog links Workspace, Coding, Tests, Agent Planning, Memory, Research, Git, Plugins, Security, Recovery, Settings and Activity. A passive overview shows the last model verification state, last file-index count, task/approval state, session restrictions, saved policy counts and context settings. Suggested next steps explain missing setup without performing it. A guided inspect → validate/propose → review/apply → test → inspect-results workflow makes the approval boundaries visible. Advanced tool arguments remain available in a collapsible section.

Open **Tools** or press **Alt+2** for the Platform Center. Opening it performs no file discovery, model inference or tool execution. All section links retain unsaved-form warnings. Review/approval, source freshness, local-model settings, saved conversations, accessibility and release trust carry forward from the 1.x releases. This is a source release; actual Windows acceptance and signing remain pending.

Windows window sizing: the standard native title bar provides drag edges/corners, Snap and maximize/restore within the desktop work area. Minimum window size is reduced to 800×500 (or the available screen size). Use Fit for the full design at smaller sizes, or Readable/Large with scrolling. The in-app duplicate window buttons are hidden on Windows.

Chat layout refresh: all sidebar navigation uses the same control style; six dashboard status cards use complete surfaces instead of text patches. The model selector appears once, in the conversation header. The composer uses a compact Send button and Ctrl+Enter remains available.
