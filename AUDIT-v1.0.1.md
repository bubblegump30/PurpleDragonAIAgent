# v1.0.1 audit and fixes

Reviewed areas: desktop bridge/job lifecycle, settings/recovery, workspace and transactional file access, test process controls, audit polling, local model discovery/inference, research transport, project memory, Git operations, specialist/plugin workflows, frontend form/review behavior and release packaging. Existing permission, host-trust, network/domain and review gates are retained.

Reproduced regressions corrected:
- A documented multiline file selection was treated as one path.
- Core rebuilds left plugin review IDs usable against changed app/workspace settings.
- A slow review response could restore a cached proposal after editing its form.
- Frozen host tests tried to reuse the app executable as a Python interpreter.
- Failed audit error logging and thread creation could leave the app permanently busy.
- Final-tool cancellation could finish with a success status.
- Polling parsed the whole audit file and allowed JSON scalars into UI event rendering.
- Damaged settings/file checkpoint records could block access to valid recovery entries.
- Direct reads allowed aliases/hard links that file previews already rejected.
- Injected app directories did not control the settings save destination.
- Request dictionaries were shared with the asynchronous worker; extra fields/unknown settings were silently accepted or misused.
- Credential device names and linked vault folders were not rejected.
- Local-model endpoint/parameter checks differed between discovery and task execution.
- Manifest/listing traversal entered directories later excluded from output.

Validation: 262 Python tests including 17 new fault/recovery/validation regressions; 35 native Linux Qt WebView checks including multiline selection, checkpoint clicking and edited-form review invalidation; JavaScript syntax/Python compilation; final local manifest and ZIP integrity.

The command-block regression was updated to patch the real subprocess API after removing an unused module alias, preserving its guarantee that arbitrary commands never execute. Native verification now waits for frontend idle before clicking the next asynchronous action, and confirms that a stale-form test actually started a new job.

Limits: no actual Windows installer compile/install/upgrade/uninstall, real DPAPI/Sandbox or live LM Studio/GitHub run was available here. Source runtime tests passed. Frozen host tests are deliberately unavailable until a separate interpreter integration is validated. This report does not assert that every possible bug has been eliminated.
