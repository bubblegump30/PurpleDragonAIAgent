# v0.9.5 verification

- Python suite: 224 tests passed; includes 21 new recovery/integrity/CLI regressions.
- JavaScript syntax and Python compilation passed.
- Native Linux Qt WebView: 29 checks passed. New checks exercise actual checkpoint creation, rendered settings recovery approval, application and candidate integrity report.
- Existing checks retain file tasks, team handoffs, three viewport/bottom-control sizes, focus/navigation, approvals, model HTTP fixtures, local Git branch operations and security scope/review UI.
- Recovery coverage includes one-use reviews, expiry, source/disk/effective-state drift, exact corrupt-byte preservation, invalid-settings reset, existing workspace retention, path/link refusal, disk-write failure preservation, manifest omissions/traversal/drift, profile/approval gates, offline CLI execution and invalid workspace destinations.
- Bundled release manifest and ZIP integrity checked after final packaging.
- Remaining: actual Windows Edge WebView2/DPI, Windows DPAPI and Sandbox, live LM Studio and authenticated GitHub acceptance. This candidate is not certified stable.

Commands: `python3 -m unittest discover -s tests -q`; `node --check frontend/app.js`; `python3 -m compileall -q purple_dragon_agent recover_settings.py verify_windows.py release_check.py build_manifest.py`; `python3 release_check.py`.
Evidence: `verification-results/native-verification-095.json`.
No new images generated; existing artwork retained.
