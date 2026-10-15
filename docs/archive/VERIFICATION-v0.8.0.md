# v0.8.0 verification

- Python suite: 182 tests passed (`python3 -m unittest discover -s tests -q`).
- JavaScript syntax and Python compilation passed.
- Native Qt WebView verifier: 20 checks passed on Linux. Included the real team form and rendered handoffs, workspace task, keyboard/navigation, approvals, model fixtures, local Git branch and three viewport sizes.
- Workflow tests cover deterministic role order, tool scopes, opt-in execution, denial blocking, cancellation before/during work, pending-approval cancellation, bounded output, state isolation and real DesktopAPI integration.
- Model connection checks use a local HTTP fixture; Git checks use temporary local repositories.
- Real Windows Edge WebView2/DPI acceptance, live LM Studio coding/research output and live authenticated GitHub writes are pending.
- No new images were generated. Existing artwork is retained.
