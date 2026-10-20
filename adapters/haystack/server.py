"""Haystack MCP adapter: keyword search over documents you hand it, nothing else.

Runs as a stdio MCP server inside the container described in mcp.json. It keeps an
in-memory document store for the life of the process and ranks with BM25, so it needs
no model, no API key and no network. Documents arrive through `index_documents`; the
container sees none of the operator's files.

Pipelines are built here in code against that one store, so `run_pipeline` runs the
same retrieval and indexing that `search` and `index_documents` use.
"""
from __future__ import annotations

from typing import Any

from haystack import Document, Pipeline
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.components.writers import DocumentWriter
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.document_stores.types import DuplicatePolicy
from mcp.server.fastmcp import FastMCP

MAX_DOCUMENTS = 2_000
MAX_CHARS = 200_000

store = InMemoryDocumentStore()
mcp = FastMCP("haystack")


def _search_pipeline() -> Pipeline:
    p = Pipeline()
    p.add_component("retriever", InMemoryBM25Retriever(document_store=store))
    return p


def _index_pipeline() -> Pipeline:
    p = Pipeline()
    p.add_component("splitter", DocumentSplitter(split_by="word", split_length=200, split_overlap=20))
    p.add_component("writer", DocumentWriter(document_store=store, policy=DuplicatePolicy.SKIP))
    p.connect("splitter.documents", "writer.documents")
    return p


PIPELINES = {
    "search": ("BM25 keyword retrieval over the indexed documents.", _search_pipeline),
    "split-and-index": ("Split documents into 200-word passages and add them to the store.", _index_pipeline),
}


def _to_documents(documents: list[Any]) -> list[Document]:
    if not isinstance(documents, list) or not documents:
        raise ValueError("documents must be a non-empty list")
    if len(documents) > MAX_DOCUMENTS:
        raise ValueError(f"at most {MAX_DOCUMENTS} documents per call")
    out = []
    for d in documents:
        if isinstance(d, str):
            content, meta = d, {}
        elif isinstance(d, dict) and isinstance(d.get("content"), str):
            content, meta = d["content"], d.get("meta") or {}
        else:
            raise ValueError("each document is a string or {content, meta}")
        if len(content) > MAX_CHARS:
            raise ValueError(f"a document is longer than {MAX_CHARS} characters")
        out.append(Document(content=content, meta=meta))
    return out


def _doc_out(d: Document) -> dict[str, Any]:
    return {"content": d.content, "score": d.score, "meta": d.meta}


def _plain(value: Any) -> Any:
    if isinstance(value, Document):
        return _doc_out(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


@mcp.tool()
def index_documents(documents: list[Any], split: bool = True) -> dict[str, int]:
    """Add documents to the store. Each is a string or {content, meta}. With split, long
    documents are cut into 200-word passages first."""
    docs = _to_documents(documents)
    if split:
        written = _index_pipeline().run({"splitter": {"documents": docs}})["writer"]["documents_written"]
    else:
        written = store.write_documents(docs, policy=DuplicatePolicy.SKIP)
    return {"written": written, "total": store.count_documents()}


@mcp.tool()
def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Rank indexed passages against a query with BM25 and return the best top_k."""
    if not query.strip():
        raise ValueError("query is empty")
    top_k = max(1, min(int(top_k), 50))
    docs = _search_pipeline().run({"retriever": {"query": query, "top_k": top_k}})["retriever"]["documents"]
    return [_doc_out(d) for d in docs]


@mcp.tool()
def list_pipelines() -> list[dict[str, str]]:
    """The pipelines this adapter can run."""
    return [{"name": n, "description": desc} for n, (desc, _) in PIPELINES.items()]


@mcp.tool()
def describe_pipeline(name: str) -> dict[str, Any]:
    """A pipeline's components and connections, as Haystack serializes them."""
    if name not in PIPELINES:
        raise ValueError(f"unknown pipeline {name!r}; see list_pipelines")
    return PIPELINES[name][1]().to_dict()


@mcp.tool()
def run_pipeline(name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Run a named pipeline with Haystack's {component: {input: value}} inputs. Document
    inputs may be given as strings or {content, meta}."""
    if name not in PIPELINES:
        raise ValueError(f"unknown pipeline {name!r}; see list_pipelines")
    if name == "split-and-index":
        docs = _to_documents((inputs.get("splitter") or {}).get("documents"))
        inputs = {"splitter": {"documents": docs}}
    return _plain(PIPELINES[name][1]().run(inputs))


if __name__ == "__main__":
    mcp.run()
