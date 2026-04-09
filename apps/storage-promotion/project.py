#!/usr/bin/env python3
import json, sys

promoted = json.load(sys.stdin)

nodes = []
edges = []

for e in promoted["entities"]:
    nodes.append({"id": e["id"]})

c = promoted["claim"]
edges.append({
  "from": f"ent:user:{c['subject']}",
  "to": f"ent:role:{c['object']}",
  "type": c['type']
})

print(json.dumps({"nodes": nodes, "edges": edges}, indent=2))
