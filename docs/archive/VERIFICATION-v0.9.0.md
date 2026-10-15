# v0.9.0 verification

- Full Python regression suite: 203 tests passed.
- JavaScript syntax check and Python compilation passed.
- Native Linux Qt WebView verifier: 25 checks passed, including real Security Center profile changes, blocked writes, static review, protected .env access and live status.
- Retained native workspace/team handoff, mandatory approval/cancellation, local-model HTTP fixture, local Git fixture and three viewport/bottom-control checks.
- 21 new scope/security regressions cover file/model/index protection, resolved aliases and prefix boundaries, malformed scopes, settings atomicity, busy guards, scope persistence/reset, mandatory approval preservation, report redaction/limits, Git current/index/metadata guards, export approval, encrypted storage boundary, metadata isolation and blocked model access.
- DPAPI ciphertext writes were simulated for cross-platform tests; actual Windows encryption is not claimed verified. Non-Windows plaintext fallback refusal was tested.
- Pending: real Windows Edge WebView2/DPI, DPAPI storage save/replace/delete, Windows Sandbox execution/feature availability and live LM Studio/GitHub acceptance.
- No new images generated; existing artwork remains intact.

Commands: `python3 -m unittest discover -s tests -q`; `node --check frontend/app.js`; `python3 -m compileall -q purple_dragon_agent verify_windows.py`.
Native evidence: `verification-results/native-verification-090.json`.
