# v0.9.5 release candidate acceptance

Completed in the build environment: 224 Python regressions; JavaScript syntax/Python compilation; 29 native Linux Qt WebView checks; local integrity checks; temporary local-model/Git fixtures; approved settings recovery; offline damaged-JSON recovery.

Pending on the actual target Windows PC:
- Run source package integrity checks, Verify-Windows.bat and WINDOWS-ACCEPTANCE.md.
- Check Windows Edge WebView2 startup, keyboard focus, text clarity, scaling and complete bottom controls.
- Verify settings saves create checkpoints; restore requires fresh review and approval, and denied/stale recovery changes nothing.
- Close the app; intentionally damage a disposable configuration copy and recover with Recover-Settings.bat. Retain the original installation/workspace and confirm recovery preserves previous bytes.
- Verify snapshot rollback and conflict rejection on a disposable project, including interrupted file application recovery.
- Verify live LM Studio inference, staged coding and cited research output using explicitly selected inputs.
- Verify Windows DPAPI save/replace/delete and manually launched Windows Sandbox tests.
- Verify authenticated GitHub publication with reviewed destinations/commits and explicit approvals if public publication is intended.
- Validate an installer, signing/distribution policy and plugin API before any future stable/public promise. Those deliverables are not included in this source candidate.

Package hashes detect drift against the included local manifest. They do not prove publisher identity. Passing candidate checks is not completion of these pending acceptance tasks.
