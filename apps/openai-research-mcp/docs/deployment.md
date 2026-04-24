# Deployment notes

Recommended order:
1. put the service behind a gateway that validates identity
2. prefer trusted identity headers only behind that gateway
3. use detached object storage for artifacts
4. expose a remote MCP or HTTP facade over HTTPS
5. publish only after freezing compatible tool schemas

Local bring-up in this lane is intentionally simpler than production.
