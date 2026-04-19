#!/usr/bin/env bash
set -euo pipefail

uvicorn main:app --host 127.0.0.1 --port 8080 --reload
