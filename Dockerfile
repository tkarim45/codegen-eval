FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
ENTRYPOINT ["codegen-eval"]
CMD ["run", "--mock"]
