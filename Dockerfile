# riff-radar container image.
# Works with both Docker and Podman:
#   podman build -t riff-radar .
#   docker build -t riff-radar .
FROM python:3.13-slim

WORKDIR /app

# Install the package itself. No runtime dependencies beyond the stdlib.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# All state (config + database + reports) lives under $HOME, so pointing
# HOME at /data means a single volume persists everything:
#   /data/.config/riff-radar/config.json
#   /data/.local/share/riff-radar/riff-radar.db
#   /data/.local/share/riff-radar/report.html
ENV HOME=/data
VOLUME ["/data"]

ENTRYPOINT ["riff-radar"]
CMD ["--help"]
