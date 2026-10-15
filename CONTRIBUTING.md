# Contributing to Purple Dragon AI Agent

Thank you for helping improve this local-first, permission-controlled Windows AI agent, created by KyleAustin85.

## Start here

Read [README.md](README.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SECURITY.md](SECURITY.md). Use an issue template for reproducible bugs or focused feature requests. Discuss substantial changes before investing in a large implementation. For usage questions, see [SUPPORT.md](SUPPORT.md).

## Development and validation

1. Fork the repository and create a focused branch from current `main`.
2. Use Python 3.10 or newer; Python 3.12 or 3.13 is recommended. Install desktop dependencies in a private virtual environment using `requirements-desktop.txt`.
3. Run `python verify_source.py` for the source suite. On Windows, use `Verify-Windows.bat` for desktop verification and follow `WINDOWS-ACCEPTANCE.md` for manual checks. Desktop verification opens a temporary window and uses isolated test data.
4. Run `node --check` on changed frontend JavaScript files when Node.js is available. Do not install unrelated dependencies just to change styling.
5. Record precisely which checks ran, their platform, and any checks not performed. Linux checks or simulated Windows behavior do not establish actual Windows acceptance.

Use disposable test workspaces. Approved host tests can run code with your account access. Do not test against valuable project data without backups.

## Project boundaries

Preserve SAFE MODE, Allow/Ask/Deny policies, mandatory human approvals, workspace boundaries, protected paths, source-revision guards, and explicit review before application. Keep local-model context and network access bounded and visible. Never add credentials to source, prompts, examples, screenshots or logs. Do not add unrestricted autonomous execution, hidden remote calls, automatic publication, or an approval bypass.

Keep the existing Neo Purple identity, clear text, keyboard navigation and accessible names. Check the smallest supported window and relevant display scales after layout changes. Avoid image-only replacements for functional controls.

## Pull requests

Explain the problem, resulting behavior, and meaningful validation. Include screenshots for visible changes after removing private information. Keep unrelated refactors separate. Add regression coverage for substantive behavior changes; do not create tests that only restate cosmetic constants. Describe security or permission implications clearly.

Do not submit runtime settings, workspaces, conversations, audit logs, credential vaults, private environments or build output. Use the repository's existing exclusions. Maintainers regenerate `RELEASE-MANIFEST.json` only when deliberately packaging reviewed changes; do not regenerate it merely to dismiss unexplained drift.

Contributions are submitted under the project's [MIT License](LICENSE). Third-party dependencies retain their own licenses and notices. Do not contribute material you lack permission to share.
