FROM python:3-slim

LABEL "org.opencontainers.image.authors"="41898282+github-actions[bot]@users.noreply.github.com"
LABEL "org.opencontainers.image.source"="https://github.com/andrius/chatgpt-cli"
LABEL "org.opencontainers.image.description"="chatgpt-cli client"

RUN apt-get update && apt-get install -y --no-install-recommends \
  libcairo2-dev \
  libgirepository1.0-dev \
  libglib2.0-dev \
  wl-clipboard \
  xclip \
  xsel \
  && rm -rf /var/lib/apt/lists/*

# Install PyGObject and any additional Python packages
RUN pip install --no-cache-dir pygobject

WORKDIR /app
COPY . ./
RUN pip install --no-cache-dir -r requirements.txt

ENV XDG_CONFIG_HOME /data

WORKDIR ${XDG_CONFIG_HOME}
VOLUME ${XDG_CONFIG_HOME}

ENTRYPOINT ["python", "/app/src/chatgpt.py"]
