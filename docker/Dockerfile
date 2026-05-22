FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY README.md .
COPY src/ src/

RUN pip install --no-cache-dir .

EXPOSE 8420

CMD ["synapse", "serve"]