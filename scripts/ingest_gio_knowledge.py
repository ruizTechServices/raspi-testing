#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from unified_server.gio.embeddings import EmbeddingService
from unified_server.gio.knowledge import GioKnowledgeChunkInput, GioKnowledgeService, chunk_text, iter_text_files
from unified_server.gio.repository import GioSupabaseRepository
from unified_server.settings import get_settings
from openai import OpenAI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest local files into Gio knowledge RAG storage.")
    parser.add_argument("paths", nargs="+", help="Files or directories to ingest")
    parser.add_argument("--tag", action="append", default=[], dest="tags", help="Tag to attach to every ingested document")
    parser.add_argument("--url-prefix", default="", help="Optional URL prefix for turning file paths into public source URLs")
    parser.add_argument("--chunk-size", type=int, default=1800, help="Approximate characters per chunk")
    parser.add_argument("--overlap", type=int, default=250, help="Characters of overlap between adjacent chunks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        print("OPENAI_API_KEY is required for ingestion.", file=sys.stderr)
        return 1

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    embedder = EmbeddingService(lambda: client)
    repository = GioSupabaseRepository()
    repository.ensure_schema()
    knowledge = GioKnowledgeService(repository)

    files = iter_text_files(args.paths)
    if not files:
        print("No supported text files found.", file=sys.stderr)
        return 1

    total_chunks = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        pieces = chunk_text(text, chunk_size=args.chunk_size, overlap=args.overlap)
        chunk_inputs: list[GioKnowledgeChunkInput] = []
        for index, piece in enumerate(pieces):
            embedding = embedder.embed(piece)
            chunk_inputs.append(
                GioKnowledgeChunkInput(
                    content=piece,
                    chunk_index=index,
                    token_count=len(piece.split()),
                    embedding=embedding,
                )
            )
        relative_path = path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path
        source_key = str(relative_path)
        url = None
        if args.url_prefix:
            url = args.url_prefix.rstrip("/") + "/" + str(relative_path).replace("\\", "/")
        knowledge.upsert_document_with_chunks(
            source_key=source_key,
            title=path.name,
            chunks=chunk_inputs,
            url=url,
            tags=args.tags,
            metadata={"path": str(path)},
        )
        total_chunks += len(chunk_inputs)
        print(f"Ingested {source_key} ({len(chunk_inputs)} chunks)")

    print(f"Done. {len(files)} files, {total_chunks} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
