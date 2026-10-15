# Security Policy

## Reporting a vulnerability

Please avoid posting vulnerability details, working exploits, credentials or private project data in public issues or pull requests.

If this repository's **Security** tab offers **Report a vulnerability**, use that private reporting flow. Private reporting may not be enabled. Otherwise, open a minimal issue titled **Private security contact requested**, with no vulnerability details, and ask @bubblegump30 to arrange a private channel. Do not send secrets to an address or account that has not been verified as the maintainer's intended contact.

Once a private channel is established, provide the affected release/commit, platform, expected security boundary, minimal reproduction and potential impact. Use synthetic data and redact tokens, personal information and local paths. Coordinate disclosure with the maintainer before publishing exploit details. There is no guaranteed response or remediation deadline, and this project does not offer a bug bounty.

## Version scope

Please reproduce against the latest published source or current `main` when safe. The current development line is v2.0.x; older releases may require an upgrade before investigation. This is a community-maintained project, not a security-certified platform or a guaranteed long-term support service.

## Important boundaries

- SAFE MODE and mandatory approvals must remain active. A model response never authorizes an operation.
- Built-in workspace and protected-path controls are application boundaries, not an operating-system sandbox.
- Approved host tests run with the user's account access. Do not approve untrusted code assuming it is isolated.
- Research text, model replies, cached sources and test output are untrusted inputs.
- The Windows DPAPI vault foundation does not make prompts, conversations, logs or all app data encrypted.
- Local manifests and SHA-256 values detect differences against an expected value; they do not prove publisher identity. Windows installer, signing, SmartScreen, DPAPI and Sandbox acceptance are documented separately and must not be inferred from Linux tests.

Do not upload `config/user_config.json`, workspaces, conversations, private-secrets, recovery backups, or raw diagnostic logs when reporting publicly. Review screenshots and logs before sharing.
