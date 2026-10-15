# v0.6.6 Verification

142 Python regression tests passed. JavaScript syntax and Python compilation passed.

The native WebView UI was tested using Qt Chromium on Linux at device-pixel ratios 1, 1.5 and 2. At each scale the checks passed for UI readiness, a real workspace task, settings navigation, keyboard focus, Ctrl+2 navigation, mandatory approval visibility, cancellation without writing, and complete bottom-control visibility across three viewport sizes.

Upgrade tests verified invalid-configuration rejection, destination backup, preserved source files and workspace location, and refusal to import while the target app folder is locked. Runtime tests verified duplicate-instance locking, stale-error clearance after UI readiness, and audit-cache invalidation.

Windows BAT launch, Microsoft Edge WebView2, Windows OS display scaling, monitor changes and hardware keyboard navigation remain subject to the included WINDOWS-ACCEPTANCE.md checklist. The automated reports explicitly record their test platform and pending Windows manual acceptance. No claim of completed Windows certification is made.
