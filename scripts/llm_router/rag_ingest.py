#!/usr/bin/env python3
"""rag_ingest — build the RAG index for llm_router from a directory of markdown.

Chunks every .md under RAG_DOCS, embeds each chunk via Ollama (nomic-embed-text),
and writes two files that llm_router loads at startup:
  - rag_index.json      : [{"text","source"}, ...]
  - rag_embeddings.npy  : float32 [N, D], L2-normalized (cosine = dot product)

nomic-embed-text is asymmetric: documents are prefixed "search_document: " and
queries (in llm_router) "search_query: ".
"""
import os
import glob
import json

import numpy as np
import httpx

RAG_DOCS = os.environ.get("RAG_DOCS", "/opt/llm_router/rag_docs")
RAG_DIR = os.environ.get("RAG_DIR", "/opt/llm_router")
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")
CHUNK = int(os.environ.get("RAG_CHUNK", "1200"))
OVERLAP = int(os.environ.get("RAG_OVERLAP", "200"))


def chunk_text(text: str) -> list[str]:
    """Paragraph-aware chunking; guarantees no chunk exceeds CHUNK chars
    (long paragraphs — big tables/code blocks — are hard-split)."""
    paras = []
    for p in text.split("\n\n"):
        p = p.strip()
        if not p:
            continue
        while len(p) > CHUNK:  # hard-split oversized paragraph
            paras.append(p[:CHUNK])
            p = p[CHUNK - OVERLAP:]
        if p:
            paras.append(p)
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= CHUNK:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    out = []
    with httpx.Client(timeout=120) as c:
        for t in texts:
            r = c.post(f"{OLLAMA}/api/embeddings",
                       json={"model": EMBED_MODEL, "prompt": ("search_document: " + t)[:6000]})
            if r.status_code != 200:
                print(f"  WARN embed failed ({r.status_code}) for chunk: {t[:80]!r}")
                r.raise_for_status()
            out.append(r.json()["embedding"])
    return out


def main():
    files = sorted(glob.glob(os.path.join(RAG_DOCS, "**", "*.md"), recursive=True))
    records = []
    for f in files:
        rel = os.path.relpath(f, RAG_DOCS)
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for ch in chunk_text(fh.read()):
                records.append({"text": ch, "source": rel})
    print(f"{len(files)} files -> {len(records)} chunks; embedding via {EMBED_MODEL} ...")

    embs = []
    for i in range(0, len(records), 32):
        batch = [r["text"] for r in records[i:i + 32]]
        embs.extend(embed(batch))
        print(f"  {min(i + 32, len(records))}/{len(records)}")

    mat = np.asarray(embs, dtype=np.float32)
    mat /= (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)  # L2 normalize
    np.save(os.path.join(RAG_DIR, "rag_embeddings.npy"), mat)
    with open(os.path.join(RAG_DIR, "rag_index.json"), "w", encoding="utf-8") as fh:
        json.dump(records, fh)
    print(f"wrote index: {mat.shape[0]} vectors x {mat.shape[1]} dims -> {RAG_DIR}")


if __name__ == "__main__":
    main()
