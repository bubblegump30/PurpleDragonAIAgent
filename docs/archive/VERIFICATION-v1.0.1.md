# v1.0.1 verification

- Python: 262 tests passed, including 17 new bug/fault-isolation regressions.
- JavaScript syntax and Python compilation passed.
- Native Linux Qt WebView: 35 checks passed. Added actual multiline selected-file review, clickable recovery checkpoint and rejection of an edited form's delayed plugin review.
- Retained team/plugin approval/tool integration, settings restore/integrity, security scope, local-model/Git fixtures, keyboard/navigation and three viewport/bottom-control checks.
- Local release manifest and ZIP integrity validated after final packaging.
- Windows installer build/installed GUI, DPAPI, Sandbox and live-service acceptance remain pending. Frozen host-test execution is blocked with explicit source-runtime guidance.

Evidence: verification-results/native-verification-101.json. Details: AUDIT-v1.0.1.md.
Commands: python3 -m unittest discover -s tests -q; node --check frontend/app.js; python3 -m compileall -q purple_dragon_agent recover_settings.py verify_windows.py release_check.py build_manifest.py; python3 release_check.py.
No new artwork was generated. The reference interface and existing icon were retained.
