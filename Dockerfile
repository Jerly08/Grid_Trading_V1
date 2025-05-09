FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Default environment variables untuk grid bot ADA
ENV BINANCE_TESTNET=False
ENV SYMBOL=ADAUSDT
ENV UPPER_PRICE=0.795
ENV LOWER_PRICE=0.765
ENV GRID_NUMBER=5
ENV QUANTITY=20

# Expose port untuk dashboard
EXPOSE 5000

# Entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

# Run command
CMD ["python", "run.py", "--production"] 