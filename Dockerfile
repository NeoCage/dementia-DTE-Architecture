# Container image for the dementia Digital Twin Engine reference implementation.
#
# THIS IS NOT A MEDICAL DEVICE. Every figure this image produces comes from a
# synthetic data generator. No real patient data has ever been used, and none
# should be. Read DISCLAIMER.md before citing anything it prints.
#
# Build:  docker build -t dementia-dte .
# Run:    docker run --rm dementia-dte simulate --seed 42

# ---------------------------------------------------------------------------
# Stage 1 — build the distribution from source
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS build

WORKDIR /src

# Only the files the build backend needs, so a change to docs or tests does not
# invalidate this layer.
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src/ ./src/

RUN python -m pip install --no-cache-dir --upgrade pip build \
 && python -m build --wheel --outdir /dist

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# ADR-0004: the system must run on a modest CPU-only server. Nothing in this
# image requires a GPU, and nothing that does should be added to it.
LABEL org.opencontainers.image.title="dementia-DTE-Architecture" \
      org.opencontainers.image.description="Reference implementation of a Digital Twin Engine and Memory Anchoring Pipeline for dementia care. Research prototype, not a medical device, synthetic data only." \
      org.opencontainers.image.source="https://github.com/NeoCage/dementia-DTE-Architecture" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.authors="Kishan Das" \
      org.dte.not-a-medical-device="true" \
      org.dte.synthetic-data-only="true"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Run as a non-root user. Nothing in the reference implementation writes outside
# its working directory.
RUN useradd --create-home --uid 10001 dte

COPY --from=build /dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir /tmp/*.whl \
 && rm -f /tmp/*.whl

# The disclaimer travels with the image, not only with the repository.
COPY DISCLAIMER.md /usr/share/dte/DISCLAIMER.md

USER dte
WORKDIR /home/dte

# `dte` is the console script declared in pyproject.toml.
ENTRYPOINT ["dte"]
CMD ["--help"]
