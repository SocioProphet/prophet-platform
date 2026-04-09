#!/usr/bin/env python3
import json, datetime, hashlib

payload = {
  "subject": "user123",
  "action": "has_role",
  "object": "admin"
}

payload_str = json.dumps(payload, sort_keys=True)
now = datetime.datetime.utcnow().isoformat()

obs = {
  "version": "0.1",
  "observation_id": "obs:demo:1:v1",
  "source_system": "storage-promotion",
  "observed_at": now,
  "normalized_payload": payload,
  "content_hash": hashlib.sha256(payload_str.encode()).hexdigest(),
  "identity_hash": hashlib.sha256("obs:demo:1:v1".encode()).hexdigest(),
  "state": "active",
  "created_at": now
}

print(json.dumps(obs, indent=2))
