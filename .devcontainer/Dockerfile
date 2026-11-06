FROM mcr.microsoft.com/devcontainers/python:3.12
COPY requirements.txt /tmp/farmared-requirements.txt
RUN pip install --no-cache-dir -r /tmp/farmared-requirements.txt
WORKDIR /workspaces/farmared
