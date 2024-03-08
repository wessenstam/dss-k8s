FROM alpine:latest

RUN apk update && apk add bash python3 py3-pip curl jq \
    && pip install requests --break-system-packages

RUN mkdir /script 
COPY secrets_sync.py /script/secrets_sync.py

RUN adduser -H -D scripter
USER scripter