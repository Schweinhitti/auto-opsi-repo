FROM uibmz/opsi-server:4.3
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv osslsigncode ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY builder/requirements.txt /app/requirements.txt
RUN python3 -m venv /app/venv && /app/venv/bin/pip install --no-cache-dir -r /app/requirements.txt
COPY builder/builder /app/builder
COPY builder/templates /app/templates
COPY builder/entrypoint.sh /app/entrypoint.sh
ENV PATH="/app/venv/bin:$PATH" PYTHONUNBUFFERED=1 HOME=/tmp TMPDIR=/data/work
ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
