# v2.0.0 release acceptance

This deliverable is the versioned source ZIP for Purple Dragon AI Agent 2.0. It preserves SAFE MODE and all human approval gates. Local verification evidence is recorded in VERIFICATION.md and verification-results. A version number does not certify the untested Windows build or publisher identity.

Before public Windows distribution, run WINDOWS-ACCEPTANCE.md on the target OS, build and smoke-test frozen artifacts, exercise install/upgrade/recovery/uninstall, check retained user data and accessibility, validate actual DPAPI/Sandbox, and verify live model/GitHub workflows. Record signing policy and actual Authenticode/SmartScreen behavior separately. Local hashes are not publisher authentication.

The provided build definitions remain available; no Windows installer or GitHub release was built or published in this environment. No self-updater, unrestricted autonomous mode or credential-provider injection is included. Back up existing user data and extract source releases into a fresh folder. Use the existing settings-import workflow to retain the prior workspace rather than overwriting an installation.
