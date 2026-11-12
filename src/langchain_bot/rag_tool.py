from pathlib import Path
from dotenv import load_dotenv
import langchain
from langchain_core.tools import BaseTool, tool
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
_vector_store = None
__all__ = ["search_policies", "initialize_vector_store"]
def load_policy_documents():
    root = Path(__file__).resolve().parents[2]
    policy_dir = root / "policies"
    documents = []
    for file_path in policy_dir.glob("*.txt"):
        loader = TextLoader(str(file_path))
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = file_path.name
        documents.extend(docs)
    return documents

def split_documents(documents, chunk_size=800, overlap=150):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return text_splitter.split_documents(documents)

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        embeddings = OpenAIEmbeddings()
        chromadb_path = Path(__file__).resolve().parents[2] / "chroma_db"
        #if chromadb path exists and is non empty, load it, else create a new one
        if chromadb_path.exists() and any(chromadb_path.iterdir()):
            print("Loading existing vector store from ChromaDB...")
            _vector_store = Chroma(persist_directory=str(chromadb_path), embedding_function=embeddings)
        else:
            print("Creating new vector store from policy documents...")
            documents = load_policy_documents()
            split_docs = split_documents(documents)
            _vector_store = Chroma.from_documents(split_docs, embeddings, persist_directory=str(chromadb_path))
    return _vector_store

@tool
def search_policies(query: str):
    "for policy/FAQ only, not user orders"
    vector_store = get_vector_store()
    results = vector_store.similarity_search(query, k=3)
    #format chunks into a single string with source labels
    formatted_res= "\n\n".join([f"Source: {doc.metadata.get('source', 'unknown')}\nContent: {doc.page_content}" for doc in results])
    return formatted_res

def initialize_vector_store():
    get_vector_store()


