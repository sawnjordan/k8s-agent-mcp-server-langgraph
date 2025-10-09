FROM python:3.11-slim

# Install system dependencies, unzip, and kubectl
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    supervisor \
    groff \
    less \
    jq \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI v2
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws/

# Create non-root user
RUN useradd -m -u 1000 appuser

ENV PATH="/home/appuser/.local/bin:$PATH"
USER appuser
WORKDIR /home/appuser/app

RUN mkdir -p /home/appuser/app/data \
    && chown -R appuser:appuser /home/appuser/app/data

# Copy requirements first for caching
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=appuser:appuser . .

# Supervisor config
RUN mkdir -p /home/appuser/logs
COPY --chown=appuser:appuser supervisord.conf /home/appuser/supervisord.conf

# Expose ports (8501 for Streamlit, 8000 for MCP server)
EXPOSE 8501 8000

# Create entrypoint script
# COPY entrypoint.sh /entrypoint.sh
# RUN chmod +x /entrypoint.sh

COPY --chown=appuser:appuser entrypoint.sh /home/appuser/entrypoint.sh
RUN chmod +x /home/appuser/entrypoint.sh

# Run supervisor to manage both services
ENTRYPOINT ["/home/appuser/entrypoint.sh"]
