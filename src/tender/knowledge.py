"""Shared retrieval gateway. Similarity finds evidence; it never selects a numeric rate."""

import hashlib
import math
import re
from collections import Counter
from datetime import date

import httpx
import numpy as np
from sqlalchemy import select

from tender.config import Settings
from tender.db import ChunkRow, DocumentRow, PackRow, RateRow, Repository
from tender.schemas import DomainPack, Identity, RateRecord, SourceDocument
from tender.storage import ObjectStore


def key(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:40]


def tokens(value: str) -> list[str]:
    return re.findall(r"[\w.-]+", value.casefold())


def in_period(start: date, end: date | None, when: date) -> bool:
    return start <= when and (end is None or when <= end)


class Embedder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.name = settings.embedding_url

    def embed(self, texts: list[str]) -> list[list[float] | None]:
        if not self.name:
            return [None] * len(texts)
        response = httpx.post(
            self.name,
            json={"texts": texts},
            timeout=60,
            headers={"Authorization": f"Bearer {self.settings.embedding_key}"},
        )
        response.raise_for_status()
        vectors = response.json()["vectors"]
        if len(vectors) != len(texts):
            raise ValueError("Embedding provider returned the wrong number of vectors")
        sizes = {len(v) for v in vectors}
        if (
            len(sizes) != 1
            or not next(iter(sizes))
            or not all(math.isfinite(float(n)) for v in vectors for n in v)
        ):
            raise ValueError("Embedding provider returned invalid vectors")
        return vectors


class KnowledgeGateway:
    def __init__(self, repo: Repository, objects: ObjectStore, settings: Settings):
        self.repo, self.objects, self.settings = repo, objects, settings
        self.embedder = Embedder(settings)

    def index_document(self, document: SourceDocument, tenant: str, namespace: str = "inbox") -> str:
        if not document.content_hash:
            document.content_hash = hashlib.sha256(document.text.encode()).hexdigest()
        doc_id = key(tenant, namespace, document.id, document.content_hash)
        with self.repo.session.begin() as session:
            existing = session.get(DocumentRow, doc_id)
            if existing:
                existing.active = True
                return doc_id
        # Overlapping paragraph windows preserve nearby table headers and qualification text.
        content = document.text
        chunks = [content[i : i + 2400] for i in range(0, len(content), 2100)]
        vectors = []
        for offset in range(0, len(chunks), 32):
            vectors.extend(self.embedder.embed(chunks[offset : offset + 32]))
        if not document.snapshot_ref:
            document.snapshot_ref = self.objects.put(content.encode())
        if not document.content_hash:
            document.content_hash = hashlib.sha256(content.encode()).hexdigest()
        with self.repo.session.begin() as session:
            session.add(
                DocumentRow(
                    id=doc_id,
                    tenant=tenant,
                    authority=document.authority,
                    trust=document.trust,
                    payload=document.model_dump(mode="json"),
                )
            )
            session.flush()
            for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                session.add(
                    ChunkRow(
                        id=f"{doc_id}-{i}",
                        document_id=doc_id,
                        position=i,
                        content=chunk,
                        embedding=vector,
                        embedding_model=self.embedder.name,
                    )
                )
        return doc_id

    def import_pack(self, pack: DomainPack, identity: Identity, *, internal_demo: bool = False) -> str:
        pack = pack.model_copy(deep=True)
        pack_id = key(identity.tenant, pack.id, pack.version)
        with self.repo.session() as session:
            existing = session.get(PackRow, pack_id)
            if existing:
                # Import is idempotent, but an existing version cannot be silently changed.
                old = DomainPack.model_validate(existing.payload)

                def comparable(p):
                    data = p.model_dump(mode="json")
                    data.pop("trust", None)
                    for d in data["documents"]:
                        for field in ("trust", "snapshot_ref", "content_hash", "retrieved_at"):
                            d.pop(field, None)
                    return data

                if comparable(old) != comparable(pack):
                    raise ValueError(
                        "This package version already exists with different content; increment version"
                    )
                return pack_id
        is_demo = internal_demo or pack.trust == "demo" or any(d.trust == "demo" for d in pack.documents)
        if is_demo and self.settings.mode == "production":
            raise ValueError("Synthetic demonstration packages cannot be imported into production")
        pack.trust = "demo" if is_demo else "candidate"
        for doc in pack.documents:
            doc.trust = pack.trust
            # Recompute snapshots from the submitted source content; clients cannot forge object refs.
            doc.snapshot_ref = self.objects.put(doc.text.encode())
            doc.content_hash = hashlib.sha256(doc.text.encode()).hexdigest()
            self.index_document(doc, identity.tenant, pack_id)
        with self.repo.session.begin() as session:
            session.add(
                PackRow(
                    id=pack_id,
                    tenant=identity.tenant,
                    authority=pack.authority,
                    trust=pack.trust,
                    payload=pack.model_dump(mode="json"),
                )
            )
            session.flush()
            for rate in pack.rates:
                session.add(
                    RateRow(
                        id=key(pack_id, rate.id),
                        pack_id=pack_id,
                        component_key=rate.component_key,
                        item_code=rate.item_code,
                        unit=rate.unit,
                        value=rate.value,
                        payload=rate.model_dump(mode="json"),
                    )
                )
        self.repo.audit(identity, "pack_imported", pack_id, {"version": pack.version, "trust": pack.trust})
        return pack_id

    def approve_pack(self, pack_id: str, identity: Identity, reason: str):
        with self.repo.session.begin() as session:
            row = session.get(PackRow, pack_id)
            if not row or row.tenant != identity.tenant:
                raise LookupError("Package not found")
            if row.trust == "demo":
                raise ValueError("Synthetic demo data cannot be promoted to official data")
            pack = DomainPack.model_validate(row.payload)
            if pack.authority == "unknown":
                raise ValueError("Package authority must be resolved before approval")
            pack.trust = "approved"
            for doc in pack.documents:
                if doc.authority not in (pack.authority, "unknown"):
                    # Cross-authority adoption must be represented as a package rule, not rejected.
                    if not pack.rules:
                        raise ValueError("Cross-authority sources require an explicit adoption rule")
                doc.trust = "approved"
                doc_id = key(identity.tenant, pack_id, doc.id, doc.content_hash)
                source_row = session.get(DocumentRow, doc_id)
                if source_row:
                    source_row.trust = "approved"
                    source_row.payload = doc.model_dump(mode="json")
            row.trust, row.payload = "approved", pack.model_dump(mode="json")
        self.repo.audit(identity, "pack_approved", pack_id, {"reason": reason})

    def packs(self, tenant: str, include_candidates: bool = True) -> list[tuple[str, DomainPack]]:
        with self.repo.session() as session:
            stmt = select(PackRow).where(PackRow.tenant == tenant)
            if not include_candidates:
                stmt = stmt.where(PackRow.trust.in_(["approved", "demo"]))
            return [(row.id, DomainPack.model_validate(row.payload)) for row in session.scalars(stmt)]

    def rate_candidates(self, pack_id: str, component_key: str, tenant: str) -> list[RateRecord]:
        with self.repo.session() as session:
            rows = session.scalars(
                select(RateRow)
                .join(PackRow)
                .where(
                    RateRow.pack_id == pack_id,
                    RateRow.component_key == component_key,
                    PackRow.tenant == tenant,
                )
            )
            return [RateRecord.model_validate(row.payload) for row in rows]

    def search(
        self,
        query: str,
        tenant: str,
        authority: str | None = None,
        as_of: date | None = None,
        approved_only: bool = False,
        limit: int = 8,
        state: str | None = None,
        discipline: str | None = None,
    ) -> dict:
        with self.repo.session() as session:
            stmt = (
                select(ChunkRow, DocumentRow)
                .join(DocumentRow)
                .where(DocumentRow.tenant == tenant, DocumentRow.active.is_(True))
            )
            if authority:
                stmt = stmt.where(DocumentRow.authority.in_([authority, "unknown"]))
            if approved_only:
                stmt = stmt.where(DocumentRow.trust == "approved")
            rows = session.execute(stmt).all()
        # Filter applicability BEFORE ranking so inaccessible or expired evidence cannot crowd out matches.
        rows = [
            (c, d)
            for c, d in rows
            if not as_of
            or in_period(
                date.fromisoformat(d.payload["effective_from"]),
                date.fromisoformat(d.payload["effective_to"]) if d.payload.get("effective_to") else None,
                as_of,
            )
        ]
        if state:
            rows = [
                (c, d) for c, d in rows if d.payload.get("state", "").casefold() in ("", state.casefold())
            ]
        if discipline:
            rows = [
                (c, d)
                for c, d in rows
                if d.payload.get("discipline", "all").casefold() in ("all", discipline.casefold())
            ]
        if not rows:
            return {"mode": "keyword", "results": []}
        terms = set(tokens(query))
        corpus = [Counter(tokens(c.content)) for c, _ in rows]
        average = sum(sum(c.values()) for c in corpus) / len(corpus) or 1
        lexical = []
        for i, counts in enumerate(corpus):
            score = 0.0
            for term in terms:
                frequency = counts[term]
                n = sum(term in c for c in corpus)
                idf = math.log(1 + (len(corpus) - n + 0.5) / (n + 0.5))
                score += (
                    idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * sum(counts.values()) / average))
                )
            if score:
                lexical.append((i, score))
        lexical.sort(key=lambda x: x[1], reverse=True)
        ranked = {i: 1 / (60 + rank) for rank, (i, _) in enumerate(lexical, 1)}
        mode, warning = "keyword", None
        if self.embedder.name:
            try:
                vector = np.array(self.embedder.embed([query])[0])
                semantic = []
                for i, (chunk, _) in enumerate(rows):
                    if chunk.embedding is None or chunk.embedding_model != self.embedder.name:
                        continue
                    other = np.array(chunk.embedding)
                    if other.shape != vector.shape:
                        continue
                    denom = np.linalg.norm(vector) * np.linalg.norm(other)
                    score = float(np.dot(vector, other) / denom) if denom else 0
                    if score > 0:
                        semantic.append((i, score))
                for rank, (i, _) in enumerate(sorted(semantic, key=lambda x: -x[1]), 1):
                    ranked[i] = ranked.get(i, 0) + 1 / (60 + rank)
                mode = "hybrid" if semantic else "keyword"
            except (httpx.HTTPError, ValueError, KeyError):
                warning = "Semantic retrieval unavailable; keyword results are shown."
        results = []
        for i, score in sorted(ranked.items(), key=lambda x: -x[1])[:limit]:
            chunk, doc = rows[i]
            results.append(
                {
                    "document_id": doc.id,
                    "title": doc.payload["title"],
                    "version": doc.payload["version"],
                    "trust": doc.trust,
                    "authority": doc.authority,
                    "content": chunk.content,
                    "locator": f"{doc.payload.get('locator', '')}; chunk {chunk.position + 1}",
                    "snapshot_ref": doc.payload["snapshot_ref"],
                    "score": score,
                }
            )
        return {"mode": mode, "warning": warning, "results": results}
