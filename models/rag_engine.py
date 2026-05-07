import os
from functools import lru_cache
from typing import List, Optional
from langchain_community.document_loaders import PyPDFLoader
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document
from langchain_classic.retrievers import MultiQueryRetriever
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue, MatchAny

from utils.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    logger.info("Initializing Qdrant client...")
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT__SERVICE__API_KEY)


@lru_cache(maxsize=1)
def get_embeddings() -> OllamaEmbeddings:
    logger.info("Initializing embeddings model...")
    return OllamaEmbeddings(model=settings.EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
    logger.info("Initializing LLM...")
    return ChatOllama(model=settings.OLLAMA_MODEL)


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    logger.info("Initializing vector store...")
    return QdrantVectorStore(
        client=get_qdrant_client(),
        collection_name=settings.QDRANT_COLLECTION_NAME,
        embedding=get_embeddings(),
    )


def ensure_collection(vector_size: int = 768):
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    if settings.QDRANT_COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info(f"Created collection: {settings.QDRANT_COLLECTION_NAME}")


def get_indexed_books() -> List[str]:
    try:
        client = get_qdrant_client()
        collections = [c.name for c in client.get_collections().collections]
        if settings.QDRANT_COLLECTION_NAME not in collections:
            return []

        result = client.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )
        book_names = set()
        for point in result[0]:
            book_name = point.payload.get("metadata", {}).get("book_name", "")
            source = point.payload.get("metadata", {}).get("source", "")
            if book_name:
                book_names.add(book_name)
            elif source:
                book_names.add(os.path.basename(source))
        return sorted(list(book_names))
    except Exception as e:
        logger.error(f"Failed to fetch indexed books: {e}")
        return []


def index_pdf(file_path: str, book_name: str) -> int:
    logger.info(f"Indexing PDF: {book_name}")
    loader = PyPDFLoader(file_path)
    data = loader.load()

    for doc in data:
        doc.metadata["book_name"] = book_name

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(data)
    logger.info(f"Split into {len(chunks)} chunks")

   
    embeddings = get_embeddings()
    sample_vector = embeddings.embed_query("test")
    ensure_collection(len(sample_vector))

    vector_store = get_vector_store()
    vector_store.add_documents(chunks)
    logger.info(f"Indexed {len(chunks)} chunks for book: {book_name}")
    return len(chunks)


def delete_book(book_name: str) -> bool:
    try:
        client = get_qdrant_client()
        client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="metadata.book_name", match=MatchValue(value=book_name))]
            ),
        )
        logger.info(f"Deleted book: {book_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete book {book_name}: {e}")
        return False


def answer_question(
    question: str,
    history: List[dict],
    selected_books: Optional[List[str]] = None,
) -> str:
    logger.info(f"Answering question: {question[:80]}")

    history_text = ""
    for msg in history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

   
    vector_store = get_vector_store()
    llm = get_llm()

    search_kwargs: dict = {"k": 5}
    if selected_books:
        search_kwargs["filter"] = Filter(
            must=[FieldCondition(key="metadata.book_name", match=MatchAny(any=selected_books))]
        )

    base_retriever = vector_store.as_retriever(search_kwargs=search_kwargs)

  
    query_prompt = PromptTemplate(
        input_variables=["question"],
        template="""Generate five different versions of the given question to retrieve
relevant documents from a vector database. Provide them separated by newlines.
Original question: {question}""",
    )
    retriever = MultiQueryRetriever.from_llm(
        llm=llm, retriever=base_retriever, prompt=query_prompt
    )

    docs: List[Document] = retriever.invoke(question)
    context = "\n\n".join([d.page_content for d in docs])

    template = """Answer the question based ONLY on the following context.
If the answer is not in the context, say you don't know.

Context:
{context}

Conversation history:
{history}

Question: {question}

Answer:"""

    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | StrOutputParser()

    response = chain.invoke({"context": context, "history": history_text, "question": question})
    logger.info("Response generated successfully")
    return response