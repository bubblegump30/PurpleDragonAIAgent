# v0.6.4 Verification

135 Python regression tests passed. The launcher was inspected to confirm that it uses python.exe, validates the environment before reuse, supports a hidden launch and retains a visible fallback. It no longer calls pythonw.exe. Windows BAT execution is not available in this Linux environment.

The prior v0.6.3 native rendering and bridge checks remain applicable because the frontend and desktop bridge are unchanged.

Extract into a fresh folder and run Run-PurpleDragonAI.bat. Do not copy the old .venv folder; the launcher prepares its own environment. Copy configuration, workspace and logs only if migrating existing data.
