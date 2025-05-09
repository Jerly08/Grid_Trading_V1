FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Default environment variables
ENV BINANCE_TESTNET=True

# Expose port for dashboard
EXPOSE 5000

# Run command
CMD ["python", "run.py", "--production"] 