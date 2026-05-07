# app.py
import os
import tempfile
import streamlit as st

from utils.config import get_settings
from utils.logger import get_logger
from models.rag_engine import index_pdf, get_indexed_books, delete_book, answer_question

logger = get_logger(__name__)
settings = get_settings()

st.set_page_config(
    page_title="Chat with your PDFs",
    page_icon="📚",
    layout="wide",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_books" not in st.session_state:
    st.session_state.selected_books = []

@st.cache_data(ttl=30)  
def cached_get_indexed_books():
    return get_indexed_books()
def sidebar():
    with st.sidebar:
        st.title("Chat with your PDFs")
        st.divider()

        st.subheader("Upload PDF")
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type=["pdf"],
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            book_name = st.text_input(
                "Book name",
                value=os.path.splitext(uploaded_file.name)[0],
            )
            if st.button("Index PDF", use_container_width=True):
                with st.spinner(f"Indexing {book_name}..."):
                    try:
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=".pdf"
                        ) as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = tmp.name

                        chunks = index_pdf(tmp_path, book_name)
                        os.unlink(tmp_path)
                        st.success(f"Indexed {chunks} chunks from '{book_name}'")
                        st.rerun()
                    except Exception as e:
                        logger.error(f"Indexing failed: {e}")
                        st.error(f"Failed to index: {e}")

        st.divider()
        st.subheader("Indexed Books")

        books = cached_get_indexed_books()
        if not books:
            st.info("No books indexed yet.")
        else:
            selected = st.multiselect(
                "Query from selected books",
                options=books,
                default=books,
                help="Select which books to query. Deselect to exclude from answers.",
            )
            st.session_state.selected_books = selected

            st.divider()
            st.subheader("Delete a Book")
            book_to_delete = st.selectbox(
                "Select book to delete",
                options=["-- select --"] + books,
                label_visibility="collapsed",
            )
            if st.button("Delete", type="secondary", use_container_width=True):
                if book_to_delete != "-- select --":
                    with st.spinner(f"Deleting '{book_to_delete}'..."):
                        success = delete_book(book_to_delete)
                    if success:
                        if book_to_delete in st.session_state.selected_books:
                            st.session_state.selected_books.remove(book_to_delete)
                        st.success(f"Deleted '{book_to_delete}'")
                        st.rerun()
                    else:
                        st.error("Delete failed. Check logs.")

        st.divider()
        if st.button("Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.rerun()


def chat_area():
    st.header("Chat with your PDFs")

    if not st.session_state.selected_books:
        st.warning("No books selected. Upload and select at least one book to start chatting.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question about your documents..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if not st.session_state.selected_books:
            with st.chat_message("assistant"):
                st.warning("Please select at least one book from the sidebar.")
            st.session_state.messages.append(
                {"role": "assistant", "content": "Please select at least one book from the sidebar."}
            )
            return

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = answer_question(
                        question=prompt,
                        history=st.session_state.messages[:-1],
                        selected_books=st.session_state.selected_books,
                    )
                    st.markdown(response)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response}
                    )
                except Exception as e:
                    logger.error(f"Error during chat: {e}")
                    st.error(f"Error: {e}")


def main():
    sidebar()
    chat_area()


if __name__ == "__main__":
    main()
