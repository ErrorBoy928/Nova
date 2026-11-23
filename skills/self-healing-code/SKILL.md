---
name: self-healing-code
description: Automated diagnosis of syntax errors, runtime tracebacks, iterative code repairs, and regression prevention.
slash_command: /heal
keywords: debug, error, traceback, fix, bug, heal, compile, exception, test, crash
---

## Self-Healing Code Directives
- **Traceback Root Cause Analysis**: Locate exact filename, line number, and exception type from compiler or interpreter tracebacks.
- **Minimal Atomic Edits**: Never rewrite intact files from scratch when a targeted block edit can resolve the regression.
- **Verification Loop**: Re-run the compiler or test script immediately after applying a repair to confirm the fix before declaring completion.
- **Prevent Regressions**: Ensure imports, signature changes, and environment variables do not break dependent callers.
