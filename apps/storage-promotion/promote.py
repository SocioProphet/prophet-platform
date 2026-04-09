#!/usr/bin/env python3
import json, sys

obs = json.load(sys.stdin)

payload = obs["normalized_payload"]

entities = [
  {"id": f"ent:user:{payload['subject']}"},
  {"id": f"ent:role:{payload['object']}"}
]

claim = {
  "id": f"clm:{payload['subject']}-{payload['object']}",
  "type": payload['action'],
  "subject": payload['subject'],
  "object": payload['object']
}

result = {
  "entities": entities,
  "claim": claim
}

print(json.dumps(result, indent=2))
