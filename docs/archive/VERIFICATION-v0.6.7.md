# v0.6.7 verification

153 Python regression tests passed. JavaScript syntax and Python compilation passed.

Connection tests used a temporary local HTTP server to verify discovery, bounded inference, missing models, empty lists, invalid response schemas, authentication errors, missing endpoints, redirect refusal, timeouts, oversized replies, nonlocal endpoint rejection, and session verification invalidation after settings changes.

Native Qt WebView tests on Linux passed for the actual Settings model picker, server discovery, selected-model inference and Verified dashboard status, as well as the existing bridge, task, keyboard, approval and viewport checks.

Actual LM Studio interoperability and Windows Edge WebView2 acceptance remain pending on the user's PC. The local test fixture is not LM Studio and does not establish compatibility with every model or server configuration. Run Verify-Windows.bat for the automated local UI checks, then use the connection center with your LM Studio server.
