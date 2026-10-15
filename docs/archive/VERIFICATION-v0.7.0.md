# v0.7.0 Verification

172 Python regression tests passed. Git tests used real temporary repositories for inspection, diffs, branch creation, staged-only commits, stale-index rejection, single-use proposals, pinned author identity, hook/fsmonitor suppression, repository boundaries and Git LFS refusal.

Mocked remote tests verified exact push refs without force or credential arguments, PR payloads and remote-head checks, release payloads and mismatched tag rejection, destination-change guards, mandatory action approval and scoped network denial. No live GitHub repository was modified or published during verification.

Native Qt WebView tests on Linux passed for the Git panel, local operation preview, and an approval-backed branch creation in a temporary repository, alongside existing model, keyboard, approval and viewport checks.

GitHub CLI authentication, actual HTTPS push/API interoperability and Windows Git process lifetime behavior remain subject to local/live acceptance. Windows Edge WebView2 and Git/gh availability must be checked on the user's PC. Run Verify-Windows.bat with Git installed for temporary-project UI checks.
