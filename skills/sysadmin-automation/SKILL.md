---
name: sysadmin-automation
description: Windows administration, silent PowerShell 5.1/7.x automation, process diagnostics, and zero window flickering.
slash_command: /sysadmin
keywords: powershell, windows, service, process, disk, registry, network, ping, netstat, task, admin
---

## Windows SysAdmin Directives
- **Zero Flickering (CREATE_NO_WINDOW)**: All subprocess executions must run silently without popping black command prompt windows.
- **Strict Error Action**: Prepend `$ErrorActionPreference = 'Stop'` to PowerShell scripts to prevent partial pipeline failures.
- **Telemetry & Validation**: Test path existence (`Test-Path`), process status (`Get-Process`), and disk quotas before executing destructive operations.
- **Clean Output Parsing**: Format output into clean JSON or structured tabular key-value lines for easy programmatic parsing.
