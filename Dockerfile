FROM python:3.12-slim
RUN useradd -m app
WORKDIR /app
COPY pyproject.toml ./
COPY usdconv ./usdconv
RUN pip install --no-cache-dir .
USER app
ENV USDC_DATA_DIR=/data
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "usdconv.app:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000"]
