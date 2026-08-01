FROM python:3.12-slim

WORKDIR /app

# Install dependencies di layer terpisah (cache lebih efisien)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh project
COPY . .

# Expose port yang dipakai uvicorn
EXPOSE 8000

# Jalankan uvicorn sebagai entrypoint
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
