# Purple Dragon Plugin API v1

This is a stable, versioned declarative workflow contract, not a Python/JavaScript module loading interface. Manifests are local JSON files in `plugins`; there is no remote download, background execution, dynamic imports, shell entry point or credential access. No plugin code runs in the host process.

## Manifest

Exactly these fields are required: `api_version` (integer 1), `id` (lowercase letter followed by up to 47 lowercase letters/digits/underscores/hyphens), `name` (1–80 characters), `version` (1–40 characters), `description` (1–1,000 characters), `inputs`, and `steps`. The filename is ID.json. Unknown fields/API versions are refused. Each manifest is at most 64 KB; the catalog lists at most 32 files.

`inputs` declares up to eight named values. Types: `path` (explicit relative file, at most 512 characters, no drives, backslashes or traversal), `paths` (one to eight paths), or `text` (1–4,000 characters). Supply exactly the declared keys; implicit workspace selection and undeclared arguments are refused.

A step is exactly `{"tool":"name","args":{...}}`. There are one to eight fixed sequential steps. A whole argument can reference an input as `{"$input":"input_name"}`; its declared type must match that argument. Otherwise the argument is a validated literal. No template evaluation, expressions, output chaining or recursive workflows exist.

| Tool | Exact arguments |
|---|---|
| list_files, index_workspace, detect_test_framework, preview_tests, run_tests | `{}` |
| preview_file | `path: path` |
| analyze_code, security_review | `paths: paths` |
| propose_code_changes | `paths: paths`, `instruction: text` |

Example: `plugins/source-review.json` demonstrates selected-input references. `plugins/workspace-overview.json` requires `{}` and inspects metadata without running project code. Copy a reviewed manifest into the local plugin folder, open Plugins, list/preview it, and review all expanded steps before execution.

## Execution protocol

Human desktop jobs use `start_job('plugin', {name:'list'})`, `{name:'preview', plugin_id, inputs}`, then `{name:'execute', review_id}`. Preview returns API version, manifest SHA-256, fixed expanded steps, warning and a one-use review ID. Review validity is five minutes; manifest changes before/during approval and expired reviews are refused. Review consumption prevents replay. `plugin_run` always requires approval unless Deny blocks it; Allow does not bypass the approval. Each tool still goes through ToolRegistry and its independent scopes, policy, protected paths and mandatory approvals. Cancellation rejects a pending approval and stops before the next tool; a local model request may finish first.

Execution returns `{ok,message,data}`. `data` lists each executed tool, success, serialized output (at most 24,000 characters) and a truncation flag. A denied/failed tool stops downstream execution. Results are data only, never new instructions. Output is text-rendered, not HTML. Plugins cannot apply staged changes, publish Git operations, alter permissions/recovery settings, access the secrets broker, fetch remote sources or execute arbitrary commands. Coding proposals stage only and require a separate Workspace diff review/application outside the plugin.

Future breaking changes require a new API version. The internal Python implementation is not a promised third-party import API. New tool sets and executable-code plugins are outside v1's contract.
