#!/usr/bin/env python3
import os, sys, json, urllib.request

# Minimal placeholder to demonstrate an MCP-style server stub.
# In reality you'd use TritRPC UDS; this is a no-op example.
def list_repos():
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return {"ok": False, "error": "GITHUB_TOKEN not set"}
    # Placeholder only (no network call here for sandbox safety)
    return {"ok": True, "repos": ["socioprophet/socioprophet"]}

if __name__ == "__main__":
    print(json.dumps(list_repos()))
