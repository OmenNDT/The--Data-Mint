"""Shared guard for every Plant HMI write route (setpoints, batch start/stop, alarm ack/shelve).

The launcher has no login (user decision), and Gradio's CORS accepts any Origin when the
page is opened by LAN/Tailscale IP, so a custom header alone is not enough against CSRF.
"""

import os
from typing import Optional
from urllib.parse import urlsplit, urlparse

from fastapi import HTTPException, Request

from .plant_comfyui_readers import is_local_address

SAME_SITE_FETCH_VALUES = {"same-origin", "none"}


def _host_allowed(host_header: str) -> bool:
    """DNS-rebinding guard: the Host must be this machine, not an attacker's domain.

    Allowed: IP literals held by this machine (loopback, LAN, Tailscale), single-label names
    (`localhost`, `sontn-x99`: a rebinding attack needs a public, dotted domain), and names
    listed in env PLANT_HMI_ALLOWED_HOSTS (comma separated, e.g. a Tailscale MagicDNS FQDN)."""
    name = urlsplit(f"//{host_header}").hostname or ""
    if not name:
        return False
    extra = {h.strip().lower() for h in os.getenv("PLANT_HMI_ALLOWED_HOSTS", "").split(",") if h.strip()}
    if name in extra:
        return True
    local = is_local_address(name)
    if local is not None:          # an IP literal or localhost: must be one of ours
        return local
    return "." not in name


def require_trusted_request(request: Request, x_plant_hmi: Optional[str]) -> None:
    """Rule H1: header check (blocks a plain cross-site form) plus an Origin/
    Sec-Fetch-Site same-site check (blocks the case where CORS itself is too
    permissive and a script could attach the header). Either mismatch -> 403.
    No Origin/Sec-Fetch-Site at all (e.g. curl, same-process test client) passes:
    those headers are added by browsers, never a proof of cross-origin intent."""
    if x_plant_hmi != "1":
        raise HTTPException(status_code=403, detail="thiếu header X-Plant-HMI: 1")
    if not _host_allowed(request.headers.get("host", "")):
        raise HTTPException(status_code=403, detail="Host không thuộc máy này (chặn DNS rebinding)")
    origin = request.headers.get("origin")
    if origin:
        origin_host = urlparse(origin).netloc
        host_header = request.headers.get("host", "")
        if not origin_host or origin_host != host_header:
            raise HTTPException(status_code=403, detail="Origin không khớp Host (chặn CSRF)")
    sec_fetch_site = request.headers.get("sec-fetch-site")
    if sec_fetch_site and sec_fetch_site not in SAME_SITE_FETCH_VALUES:
        raise HTTPException(status_code=403, detail="Sec-Fetch-Site cross-site bị chặn")
