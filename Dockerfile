FROM python:3-slim

LABEL "org.opencontainers.image.authors"="andrius@tcp.agency,karolis@tcp.agency"
LABEL "org.opencontainers.image.source"="https://github.com/upfitai/ai-service-nodejs"
LABEL "org.opencontainers.image.description"="CHATGPT"

WORKDIR /app
COPY . ./
RUN pip install --no-cache-dir -r requirements.txt

ENV XDG_CONFIG_HOME /data

WORKDIR ${XDG_CONFIG_HOME}
VOLUME ${XDG_CONFIG_HOME}

ENTRYPOINT ["python", "/app/src/chatgpt.py"]
