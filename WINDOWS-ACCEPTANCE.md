# Windows acceptance checks

Run Run-PurpleDragonAI.bat, then close the app and run Verify-Windows.bat. Confirm that windows-verification.json records Windows as the native platform and that all automated checks passed.

Manual checks on your PC:

1. Cold-start twice. Confirm one usable window opens, without a console remaining visible or a missing-pythonw error.
2. Reopen while the same release is running. Confirm the duplicate instance is rejected clearly.
3. Maximize, restore, resize and minimize. Confirm the complete Send button, composer, model picker and footer cards remain visible.
4. At Windows display scales of 100%, 125%, 150% and 200%, restart the app and check readable text and control alignment. Record only scales actually tested.
5. Use Tab, Shift+Tab, Enter and Space to navigate and activate controls. Check Ctrl+1, Ctrl+2, Ctrl+, and Ctrl+Enter.
6. Trigger a staged file change in a disposable workspace. Press Escape on the approval dialog and confirm the operation is rejected. No workspace file should change before an explicit reviewed application.
7. Close the app and import a previous configuration into a fresh release folder. Confirm the backup, restored policies and unchanged existing workspace. Keep the old folder if the workspace is inside it.

Windows acceptance is pending until these checks are performed on Windows. No unrestricted autonomous mode was added.

## v0.8.0 team checks
- Start selected Coding/Security/Release specialists with a small file; verify handoff order and scrolling.
- Deny a requested Coding proposal/test: later specialists must stop.
- Cancel while approval is visible: dialog must close and later specialists must stop.
- With LM Studio, approve a staged Coding proposal and cited Research draft; review output and citations manually.
- Apply proposal separately, run approved QA tests against applied files, and verify the report distinguishes tests from previews.

## v0.9.0 center checks
- Switch Read-only/Sandbox export only/Standard and verify actual tools match restrictions. Scope resets on restart and persists across settings and workspace changes.
- Add a denied folder; test a file inside it and a similarly named allowed folder. Verify protected `.env`/key files are omitted from Sandbox input, snapshots and model source context.
- Run Security review with a harmless sample risky pattern; verify findings show line/category and no source value.
- Save, replace and delete a test credential on Windows. Confirm `.secret` bytes differ from plaintext and no value appears in app state/audit/config; credential injection is not implemented.
- Deny Sandbox export approval, then approve a new export. Inspect mapped folders, disabled networking/clipboard and read-only input/Python before opening `.wsb` manually.
- Run a tiny trusted unittest inside Windows Sandbox; inspect untrusted Results JSON/log; close Sandbox to stop. Do not treat executable discovery as verification.


## v0.9.5 recovery checks
- Create and list settings checkpoints; verify model/destination/policy changes are visible in the restore review.
- Deny restore and confirm no writes; approve a fresh restore and confirm runtime settings and disk agree.
- Modify checkpoint/current configuration after review; confirm stale recovery is blocked. Wait over five minutes and confirm review expiry.
- Test offline reset with a damaged configuration in a disposable installation; preserve original bytes and original project data.
- Verify Read-only/Sandbox session profiles block settings restore, and Standard does not bypass restore_settings Deny.
- Modify one copied frontend file: candidate checks must report drift. Re-extract the clean ZIP rather than replacing its manifest.
- Confirm Recover-Settings.bat chooses a working runtime if the private environment is missing/broken; it must not require opening the GUI.

## v1.0.0 platform and installer checks
- List/preview/run both bundled plugin manifests; inspect exact tool scopes and inputs. Deny plugin_run and a nested tool to confirm downstream stop. Exercise cancellation during an approval.
- Update a manifest after review and confirm stale execution is refused; test protected inputs through Source Review.
- Build actual Windows binaries and installer with Build-Windows.ps1 -Installer, then run the installed frozen GUI and recovery executable.
- Validate per-user installation, retained data on upgrade/uninstall, recovery/rollback after upgrade and release manifest profiles.
- Confirm unsigned distribution wording and complete RELEASE-ACCEPTANCE.md before publishing a public Windows release.

## v1.0.1 regression checks
- Enter two paths on separate lines; verify both appear in source/security review.
- Start a plugin preview, edit the form before it returns, and confirm a new review is required.
- Switch workspaces/settings after preparing a review; confirm the old review is refused.
- Click a settings checkpoint; corrupt a disposable checkpoint and confirm healthy entries remain selectable.
- Verify source host tests run with approval; verify frozen host test controls are unavailable with explanatory guidance rather than launching another app instance.
- Confirm final-tool cancellation and audit/storage errors leave the queue usable and report completed effects accurately.

## v1.0.2 reported-error regression
- Run Build-Windows.bat with an older Python first in PATH and a compatible private environment: confirm the printed interpreter is the compatible private one.
- With no compatible interpreter, confirm the source launcher stops before tests with an install instruction.
- Run all source tests on Windows, including rename collisions/shadowing and source-context/memory checks that assert LF content.
- Confirm existing CRLF source files remain unchanged before approval and staged rename proposals retain CRLF.

## v1.3.0 Local Model Center 2.0
- Verify numeric controls and copied diagnostics under Windows Edge WebView2.
- Load a model in LM Studio manually, list identifiers, run inference and inspect timing.
- Save two model profiles, switch identifiers, activate each and check generation controls.
- Confirm timeout guidance for a deliberately unavailable/loading model and inspect LM Studio logs.
- Confirm low response-token limits show an incomplete-output notice when the server returns finish_reason=length.

## v1.5.0 Coding & Validation 2.0
- Validate two selected source files, externally edit one, and confirm generation is refused before contacting the model.
- Generate, fully review and separately approve a valid two-file proposal; confirm neither file changes before approval.
- Confirm a selected unchanged dependency modified after staging prevents apply.
- Preview unittest/pytest and a timeout, approve a trusted disposable test suite, and inspect counts/failure names against raw output.
- Check cancellation, timeout, empty discovery, truncated output and copy-summary behavior on Windows.

## v1.6.0 Agent Planning Center
- Prepare a plan and confirm no tool/model execution occurs before Start reviewed plan.
- Pause during a trusted long tool: verify the tool finishes, the next step waits, and the queue reports Paused. Resume and cancel a paused run.
- Deny a tool, inspect its blocked step, prepare a retry, and confirm prior successes are not repeated.
- For host-test retry, confirm a new approval appears and denial prevents execution.
- Change settings in the same workspace: confirm blocked state remains but old review tokens are refused.
- Restart the app: confirm session plan state is not represented as resumable.

## v1.7.0 acceptance (pending on Windows)

Check Memory search, edit/save approval, conflict refusal and age reminders. Preview enabled/disabled memory context. In Research, preview selected cached sources, reject changed context, generate a cited draft and open each cached citation. Check the last attempted model request panel at 100%, 125% and 150% DPI; confirm scrolling reaches its bottom and Escape closes it. Confirm Plugins still opens and runs through its approval gate.

## v1.8.0 manual acceptance (pending)

Use keyboard only at 100%, 125%, 150% and 200% Windows display scale. Check Tab/Shift+Tab, skip-to-content, Alt+1..4, F1 and Ctrl+Alt+A; ensure unsaved edits still prompt. In Readable/Large modes scroll to all four corners and verify bottom controls remain reachable. Test preference persistence across restart and reset. Check high contrast and OS reduced-motion. Use Narrator/NVDA to inspect labels, heading focus, result regions and status announcements. Verify Allow/Deny remain separately operated and an arriving approval closes display settings with Deny focused. Original artwork may not adapt to forced colors; validate on Windows before claiming support.

## v1.9.0 acceptance (pending on Windows)

Run first-install and offline restart in a user-writable folder containing spaces and non-ASCII characters. Simulate failed pip setup and inspect logs/setup.log. Run Diagnose-Startup.bat with corrupt settings and confirm it preserves them. Run Verify-Release.bat before/after controlled frontend drift; expect a nonzero failure exit after mismatch. Check registry hints on x64 Windows with/without WebView2 and compare actual GUI launch; hints alone are not acceptance. Compare correct and incorrect SHA-256 values with Verify-Download.ps1 and verify failures return nonzero. Check duplicate instances and restart after forced termination. Build frozen artifacts on Windows, verify real Authenticode status separately, and record installer/upgrade/recovery/uninstall and SmartScreen behavior before public distribution. Never claim signing or Defender acceptance from a local hash check.

## v2.0.0 acceptance (pending)

Open Tools/Alt+2 and verify all twelve Platform Center cards route correctly with keyboard and pointer. Confirm overview metadata follows model disable/configure/test, workspace indexing, session restrictions, tasks and approvals without claiming continuous verification. Opening the center must not index files, call a model or execute tools. Follow the coding workflow through proposal, full review, mandatory apply approval and separate test approval; verify actual files/results. Exercise advanced-form unsaved warnings, guided help, Large/readable scrolling and all retained 1.x workflows before distribution.

Window sizing refresh (pending actual Windows check): confirm native title bar and edge/corner resizing, maximize within the work area with taskbar available, native title-bar double-click restore, Snap between monitors, and 800×500 minimum sizing. Confirm the in-app duplicate window controls are hidden. Check Windows taskbar auto-hide settings separately if it still retracts. Test all Windows DPI scales and Fit/Readable/Large modes after resizing.
