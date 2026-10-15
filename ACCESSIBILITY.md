# Accessibility

Purple Dragon AI Agent aims to make its local AI workflows usable through clear text, consistent controls and keyboard navigation while retaining the Neo Purple visual identity.

## Implemented features

- Keyboard navigation, visible focus, a skip-to-content control and accessible names on key controls.
- Section shortcuts: Alt+1 Chat, Alt+2 Tools, Alt+3 Workspace, Alt+4 Settings; F1 opens help and Ctrl+Alt+A opens Display & accessibility.
- Ctrl+Enter sends the current message. Permission dialogs retain separate Allow and Deny decisions.
- Saved Fit, Readable and Large modes. Readable uses at least 100% scale and Large at least 125%; scrolling exposes content that exceeds the window.
- Stronger contrast for live text/controls and reduced-motion preferences, including the operating-system reduced-motion setting.
- Native Windows window borders for resizing and standard maximize/restore behavior, plus labelled scrollable results and focus restoration.

## Known limitations and verification

The artwork still contains raster text and decorative details that do not fully adapt to zoom, forced colors or screen readers. Fit mode can make text too small on a small window; use Readable or Large with scrolling instead. Some dense views and dynamic status changes may still present barriers.

Automated and native Linux Qt checks do not establish Windows Edge WebView2, Narrator/NVDA, high-DPI or forced-colors compatibility. Actual Windows assistive-technology acceptance remains pending. No full WCAG conformance or accessibility certification is claimed. See `WINDOWS-ACCEPTANCE.md` and `VERIFICATION.md` for evidence and outstanding checks.

## Report a barrier

Use the bug-report template and include the affected section/control, app version, Windows version, display scale, display mode, input method and assistive technology/version when relevant. Explain what you expected, what happened, and a minimal reproduction. Screenshots are optional; redact personal data. Do not include medical information or a diagnosis to justify an accessibility request.

Accessibility improvements are welcome through the same [contribution process](CONTRIBUTING.md). Maintainers will assess reports, but no response or remediation deadline is guaranteed.
