# Chat-with-Book

A Streamlit application for chatting with PDF documents using Ollama + Qdrant.

![Chat-with-Book UI](screenshot-ui.png)

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally
- [Qdrant](https://qdrant.tech) running locally (Docker recommended)

## Setup

### 1. Start Qdrant

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 2. Pull Ollama models

```bash
ollama pull llama3.2:1b
ollama pull qwen3-embedding:0.6b-fp16
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

Edit `.env` to match your setup:

```env
OLLAMA_MODEL=llama3.2:1b
EMBEDDING_MODEL=qwen3-embedding:0.6b-fp16
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=pdf_rag
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
LOG_LEVEL=INFO
```

### 5. Run the app

```bash
streamlit run app.py
```

## Project Structure

```
chat-with-book/
├── models/
│   ├── rag_engine.py     # RAG logic (indexing, retrieval, answering)
├── utils/
│   ├── config.py         # Settings via pydantic-settings
│   ├── logger.py         # Logging setup
├── app.py            # Streamlit UI
├── .env              # Environment variables
└── requirements.txt
```

## Features

- Upload and index multiple PDF files
- Select which books to query
- Delete indexed books from the vector store
- Chat with memory (last 6 messages used as context)
- MultiQueryRetriever for better recall
- Qdrant as vector store
