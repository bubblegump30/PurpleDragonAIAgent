# v1.0.0 verification

- Full Python suite: 245 tests passed; 21 new plugin/platform regressions.
- JavaScript syntax and Python compilation passed.
- Native Linux Qt WebView: 32 checks passed; new checks cover actual plugin review, mandatory approval and real controlled workflow tools.
- Retained workspace/team handoffs, three viewport/bottom-control checks, navigation/focus, approval/cancellation, source-model/Git fixtures, security scope/review, settings restore and local integrity UI checks.
- Plugin regressions cover schemas/API versions, privileged/unknown tools, explicit inputs/path traversal, source changes before/during approval, mandatory approvals even under Allow, Deny, expiry, one-use reviews, cancellation, output bounds, state-copy isolation, symlinks and real gateway failure stops.
- Platform regressions cover frozen/source manifest profiles, private/build-data exclusions, frozen config path selection, malformed bridge requests and failure reporting when no tools execute.
- Source package SHA-256 manifest and ZIP integrity passed after final packaging.
- Windows PowerShell/Inno/PyInstaller build was not executable in this Linux environment. Actual EXE/setup compilation, frozen GUI/install/upgrade/uninstall and real Windows DPAPI/Sandbox/live integrations remain pending.

Evidence: verification-results/native-verification-100.json. Checks: python3 -m unittest discover -s tests -q; node --check frontend/app.js; python3 -m compileall -q purple_dragon_agent recover_settings.py verify_windows.py release_check.py build_manifest.py; python3 release_check.py.
No new images were generated; existing reference artwork and icon were retained.
