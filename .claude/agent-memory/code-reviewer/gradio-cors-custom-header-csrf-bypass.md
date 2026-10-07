---
name: gradio-cors-custom-header-csrf-bypass
description: Gradio 6.x CustomCORSMiddleware on launcher :7860 echoes any Origin + requested headers when Host is not localhost, so custom-header CSRF guards (X-Plant-HMI) are bypassed via LAN/Tailscale IP
metadata:
  type: project
---
Gradio's CustomCORSMiddleware (launcher port 7860, bound 0.0.0.0) treats any Origin as valid when the request Host is not localhost/127.0.0.1/0.0.0.0. Preflight then returns ACAO=<attacker origin>, Allow-Credentials true, Allow-Headers=<whatever requested>. Verified 2026-09-26 with curl OPTIONS (Host: 192.168.1.50:7860, Origin: https://evil.example).

**Why:** a "require custom header" CSRF guard on any route mounted into the Gradio app only protects localhost access; via LAN/Tailscale IP or DNS rebinding the guard is void.

**How to apply:** when reviewing write routes on the launcher (plant HMI control, etc.), require an Origin/Sec-Fetch-Site same-origin check in the handler, not only a custom header. See [[plant-hmi-review-notes]].
