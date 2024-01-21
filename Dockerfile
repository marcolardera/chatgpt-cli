FROM python:3-slim

LABEL "org.opencontainers.image.authors"="41898282+github-actions[bot]@users.noreply.github.com"
LABEL "org.opencontainers.image.source"="https://github.com/andrius/chatgpt-cli"
LABEL "org.opencontainers.image.description"="chatgpt-cli client"

WORKDIR /app
COPY . ./
RUN pip install --no-cache-dir -r requirements.txt

ENV XDG_CONFIG_HOME /data

WORKDIR ${XDG_CONFIG_HOME}
VOLUME ${XDG_CONFIG_HOME}

ENTRYPOINT ["python", "/app/src/chatgpt.py"]
