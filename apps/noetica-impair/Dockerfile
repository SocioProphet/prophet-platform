# GPU batch image for the impairment rig.
#
# Base is the CUDA-enabled pytorch image rather than the platform's usual
# python:3.12-slim, because every GPU workload in this estate already runs on
# pytorch/pytorch or rayproject/ray-ml and pip-installing CUDA torch into a slim base
# would pull ~2GB and pin a different CUDA than the node driver.
#
# Image name MUST stay "noetica-impair" and match the apps/<dir> name: gitops-promote
# keys the sha- tag rewrite off that convention.
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/cache/hf \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# LICENSE comes along because pyproject declares license = { file = "LICENSE" };
# without it the editable install fails with "License file does not exist".
COPY pyproject.toml LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps -e .

# The platform runs containers as uid 10001 with a read-only root filesystem; the
# GKE plane mounts emptyDirs at /cache and /tmp for the HF cache and scratch.
RUN useradd -m -u 10001 impair && mkdir -p /cache /out && chown -R impair /cache /out /app
USER impair

# Batch job, not a service: no port, no /healthz. Configuration arrives as env vars
# (see planes/base.py RunJob.to_env).
ENTRYPOINT ["python", "-m", "noetica_impair.experiments.run_matrix"]
