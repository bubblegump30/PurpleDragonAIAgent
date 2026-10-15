# v0.6.3 verification

- 135 Python regression tests passed.
- JavaScript syntax check passed.
- Native pywebview 6.2.1 startup and JS-to-Python bridge verified with the Qt Chromium renderer on Linux.
- A real workspace-listing task completed through the native frontend and existing Python agent.
- Rendered UI visually inspected at the reference resolution of 1672 x 941.
- Browser-backed interaction checks passed: tool navigation, inert file-content display, mandatory approval dialog, explicit denial without file mutation, and settings navigation.
- Native viewport fit checked at 1672 x 941, 1280 x 800 and 1050 x 650.

The Windows Edge WebView2 host and first-run BAT installer cannot be executed in this Linux environment. Verify-Windows.bat provides the Windows-native checks after local setup. Image artwork preserves the supplied design exactly; live text, messages and honest app-status values differ from the sample content. The supplied screenshot is reused as an artwork skin, not shown as a nonfunctional mockup.
