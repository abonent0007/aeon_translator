"""
AEON Binary Format v1.0 — компактный файл семантической модели.

Формат .aeon:
┌──────────────────────────────────────────────┐
│ HEADER (64 байта)                             │
│  magic:     "AEON" (4 bytes)                 │
│  version:   uint16 (2)                        │
│  emb_dim:   uint16 (2)   — размерность       │
│  prim_dim:  uint16 (2)   — кол-во примитивов │
│  atom_count:uint32 (4)    — число атомов      │
│  edge_count:uint32 (4)    — число рёбер       │
│  flags:     uint16 (2)                         │
│  reserved:  44 bytes                          │
├──────────────────────────────────────────────┤
│ PRIMITIVE NAMES (prim_dim * 32 bytes)         │
├──────────────────────────────────────────────┤
│ ATOM ENTRIES (atom_count)                     │
│  hash:      16 bytes                          │
│  embedding: emb_dim * float16 (2 bytes each)  │
│  prim_vec:  prim_dim * float16                 │
│  intent:    32 bytes (padded)                  │
│  domain:    32 bytes                           │
│  complexity:float16 (2)                        │
│  urgency:   float16 (2)                        │
│  confidence:float16 (2)                        │
│  lang:      16 bytes                           │
│  entities_count: uint8                         │
│  entities:  variable (JSON chunk)              │
│  evidence_count: uint8                         │
│  evidence:  variable (JSON chunk)              │
├──────────────────────────────────────────────┤
│ EDGE ENTRIES (edge_count)                     │
│  source_hash: 16 bytes                        │
│  target_hash: 16 bytes                        │
│  rel_type:    32 bytes                        │
│  strength:    float16 (2)                      │
│  evidence_len: uint8                           │
│  evidence:    variable                         │
├──────────────────────────────────────────────┤
│ FOOTER                                        │
│  checksum:  SHA256 всего выше                 │
│  magic_end: "EONA" (подтверждение)            │
└──────────────────────────────────────────────┘
"""

import struct
import hashlib
import json
import os
import io
from typing import List, BinaryIO
from .semantic_atom import SemanticAtom, Relation, Entity

MAGIC = b"AEON"
MAGIC_END = b"EONA"
VERSION = 1
HEADER_SIZE = 64
PRIMITIVE_NAME_SIZE = 32


class AeonFormat:
    """Сериализатор/десериализатор .aeon файлов."""

    @staticmethod
    def serialize(atom: SemanticAtom, path: str):
        """Сохраняет атом в .aeon файл."""
        atoms = [atom]
        AeonFormat.serialize_batch(atoms, path)

    @staticmethod
    def serialize_batch(atoms: List[SemanticAtom], path: str):
        """Сохраняет граф атомов в .aeon файл."""
        primitives = [
            "existence", "action", "relation", "property",
            "quantity", "quality", "time", "space",
            "cause", "effect", "purpose", "means",
            "part", "whole", "similarity", "difference"
        ]
        prim_dim = len(primitives)
        emb_dim = len(atoms[0].embedding) if atoms and atoms[0].embedding else 0

        edges = []
        for atom in atoms:
            for rel in atom.relations:
                edges.append((atom.meaning_hash, rel))

        buf = io.BytesIO()

        # ── HEADER ──
        buf.write(MAGIC)
        buf.write(struct.pack("<H", VERSION))
        buf.write(struct.pack("<H", emb_dim))
        buf.write(struct.pack("<H", prim_dim))
        buf.write(struct.pack("<I", len(atoms)))
        buf.write(struct.pack("<I", len(edges)))
        buf.write(struct.pack("<H", 0))  # flags
        buf.write(b"\x00" * 44)          # reserved

        # ── PRIMITIVE NAMES ──
        for p in primitives:
            name_bytes = p.encode("utf-8")[:PRIMITIVE_NAME_SIZE - 1]
            buf.write(name_bytes + b"\x00" * (PRIMITIVE_NAME_SIZE - len(name_bytes)))

        # ── ATOM ENTRIES ──
        for atom in atoms:
            # hash (16 bytes)
            hash_bytes = bytes.fromhex(atom.meaning_hash) if len(atom.meaning_hash) == 32 else atom.meaning_hash.encode()[:16]
            buf.write(hash_bytes.ljust(16, b"\x00"))

            # embedding (emb_dim * float16)
            if emb_dim > 0 and atom.embedding:
                for v in atom.embedding[:emb_dim]:
                    buf.write(struct.pack("<e", float(v)))
            else:
                buf.write(b"\x00" * (emb_dim * 2))

            # primitive vector (prim_dim * float16)
            for v in atom.primitive_coordinates[:prim_dim]:
                buf.write(struct.pack("<e", float(v)))
            if len(atom.primitive_coordinates) < prim_dim:
                buf.write(b"\x00" * ((prim_dim - len(atom.primitive_coordinates)) * 2))

            # intent, domain, language (32 bytes each, padded)
            for field in [atom.intent, atom.domain, atom.language_origin]:
                fb = field.encode("utf-8")[:31]
                buf.write(fb + b"\x00" * (32 - len(fb)))

            # complexity, urgency, confidence (float16)
            for v in [atom.complexity, atom.urgency, atom.extraction_confidence]:
                buf.write(struct.pack("<e", float(v)))

            # entities (JSON)
            entities_json = json.dumps([{"n": e.name, "t": e.type, "r": e.role, "c": e.confidence}
                                        for e in atom.entities], ensure_ascii=False).encode("utf-8")
            buf.write(struct.pack("<B", len(atom.entities)))
            buf.write(struct.pack("<H", len(entities_json)))
            buf.write(entities_json)

            # evidence (JSON)
            evidence_json = json.dumps(atom.evidence, ensure_ascii=False).encode("utf-8")
            buf.write(struct.pack("<B", len(atom.evidence)))
            buf.write(struct.pack("<H", len(evidence_json)))
            buf.write(evidence_json)

            # explanation chain (JSON)
            expl_json = json.dumps(atom.explanation_chain, ensure_ascii=False).encode("utf-8")
            buf.write(struct.pack("<H", len(expl_json)))
            buf.write(expl_json)

            # confidence breakdown (JSON)
            cb_json = json.dumps(atom.confidence_breakdown, ensure_ascii=False).encode("utf-8")
            buf.write(struct.pack("<H", len(cb_json)))
            buf.write(cb_json)

            # hallucination metrics
            for v in [atom.consistency_score, atom.hallucination_risk]:
                buf.write(struct.pack("<e", float(v)))
            buf.write(struct.pack("<B", 1 if atom.fact_grounded else 0))

        # ── EDGE ENTRIES ──
        for src_hash, rel in edges:
            src_b = bytes.fromhex(src_hash) if len(src_hash) == 32 else src_hash.encode()[:16]
            tgt_b = bytes.fromhex(rel.target_hash) if len(rel.target_hash) == 32 else rel.target_hash.encode()[:16]
            buf.write(src_b.ljust(16, b"\x00"))
            buf.write(tgt_b.ljust(16, b"\x00"))
            rt = rel.relation_type.encode("utf-8")[:31]
            buf.write(rt + b"\x00" * (32 - len(rt)))
            buf.write(struct.pack("<e", float(rel.strength)))
            ev = (rel.evidence or "").encode("utf-8")[:255]
            buf.write(struct.pack("<B", len(ev)))
            buf.write(ev)

        # ── FOOTER ──
        content = buf.getvalue()
        checksum = hashlib.sha256(content).digest()[:32]
        buf.write(checksum)
        buf.write(MAGIC_END)

        with open(path, "wb") as f:
            f.write(buf.getvalue())

        size_kb = len(buf.getvalue()) / 1024
        print(f"   💾 .aeon сохранён: {path} ({size_kb:.1f} КБ, {len(atoms)} атомов, {len(edges)} рёбер)")

    @staticmethod
    def deserialize(path: str) -> List[SemanticAtom]:
        """Загружает .aeon файл в список атомов."""
        with open(path, "rb") as f:
            data = f.read()

        buf = io.BytesIO(data)

        # ── HEADER ──
        magic = buf.read(4)
        if magic != MAGIC:
            raise ValueError(f"Not a .aeon file: {magic}")

        version = struct.unpack("<H", buf.read(2))[0]
        emb_dim = struct.unpack("<H", buf.read(2))[0]
        prim_dim = struct.unpack("<H", buf.read(2))[0]
        atom_count = struct.unpack("<I", buf.read(4))[0]
        edge_count = struct.unpack("<I", buf.read(4))[0]
        buf.read(2)   # flags
        buf.read(44)  # reserved

        # ── PRIMITIVE NAMES ──
        primitives = []
        for _ in range(prim_dim):
            name = buf.read(PRIMITIVE_NAME_SIZE).rstrip(b"\x00").decode("utf-8")
            primitives.append(name)

        # ── ATOM ENTRIES ──
        atoms = []
        for _ in range(atom_count):
            hash_bytes = buf.read(16).rstrip(b"\x00")
            meaning_hash = hash_bytes.hex() if len(hash_bytes) == 16 else hash_bytes.decode()

            embedding = []
            if emb_dim > 0:
                for _ in range(emb_dim):
                    embedding.append(struct.unpack("<e", buf.read(2))[0])

            prim_vec = []
            for _ in range(prim_dim):
                prim_vec.append(struct.unpack("<e", buf.read(2))[0])

            intent = buf.read(32).rstrip(b"\x00").decode("utf-8")
            domain = buf.read(32).rstrip(b"\x00").decode("utf-8")
            language = buf.read(32).rstrip(b"\x00").decode("utf-8")

            complexity = struct.unpack("<e", buf.read(2))[0]
            urgency = struct.unpack("<e", buf.read(2))[0]
            confidence = struct.unpack("<e", buf.read(2))[0]

            ent_count = struct.unpack("<B", buf.read(1))[0]
            ent_len = struct.unpack("<H", buf.read(2))[0]
            entities_raw = json.loads(buf.read(ent_len).decode("utf-8"))
            entities = [Entity(name=e["n"], type=e["t"], role=e.get("r", ""), confidence=e["c"])
                        for e in entities_raw]

            ev_count = struct.unpack("<B", buf.read(1))[0]
            ev_len = struct.unpack("<H", buf.read(2))[0]
            evidence = json.loads(buf.read(ev_len).decode("utf-8"))

            expl_len = struct.unpack("<H", buf.read(2))[0]
            explanation = json.loads(buf.read(expl_len).decode("utf-8"))

            cb_len = struct.unpack("<H", buf.read(2))[0]
            confidence_breakdown = json.loads(buf.read(cb_len).decode("utf-8"))

            consistency = struct.unpack("<e", buf.read(2))[0]
            hallucination_risk = struct.unpack("<e", buf.read(2))[0]
            fact_grounded = struct.unpack("<B", buf.read(1))[0] == 1

            atom = SemanticAtom(
                meaning_hash=meaning_hash,
                embedding=embedding,
                primitive_coordinates=prim_vec,
                intent=intent,
                domain=domain,
                entities=entities,
                complexity=complexity,
                urgency=urgency,
                extraction_confidence=confidence,
                explanation_chain=explanation,
                evidence=evidence,
                confidence_breakdown=confidence_breakdown,
                language_origin=language,
                consistency_score=consistency,
                hallucination_risk=hallucination_risk,
                fact_grounded=fact_grounded
            )
            atoms.append(atom)

        # ── EDGE ENTRIES ──
        edge_map = {}
        for _ in range(edge_count):
            src = buf.read(16).rstrip(b"\x00")
            tgt = buf.read(16).rstrip(b"\x00")
            src_hash = src.hex() if len(src) == 16 else src.decode()
            tgt_hash = tgt.hex() if len(tgt) == 16 else tgt.decode()
            rel_type = buf.read(32).rstrip(b"\x00").decode("utf-8")
            strength = struct.unpack("<e", buf.read(2))[0]
            ev_len = struct.unpack("<B", buf.read(1))[0]
            evidence_text = buf.read(ev_len).decode("utf-8") if ev_len > 0 else ""
            rel = Relation(target_hash=tgt_hash, relation_type=rel_type, strength=strength, evidence=evidence_text)
            edge_map.setdefault(src_hash, []).append(rel)

        # Привязываем рёбра к атомам
        for atom in atoms:
            if atom.meaning_hash in edge_map:
                atom.relations = edge_map[atom.meaning_hash]
                atom.related_atoms = [r.target_hash for r in atom.relations]

        return atoms

    @staticmethod
    def compare_files(path_a: str, path_b: str) -> dict:
        """Сравнивает два .aeon файла."""
        atoms_a = AeonFormat.deserialize(path_a)
        atoms_b = AeonFormat.deserialize(path_b)

        if not atoms_a or not atoms_b:
            return {"error": "empty files"}

        a = atoms_a[0]
        b = atoms_b[0]
        dist = a.distance_to(b)

        return {
            "atoms_count": (len(atoms_a), len(atoms_b)),
            "semantic_distance": round(dist, 4),
            "intent_match": a.intent == b.intent,
            "domain_match": a.domain == b.domain,
            "common_entities": list(
                set(e.name for e in a.entities) & set(e.name for e in b.entities)
            ),
            "file_a_size": os.path.getsize(path_a),
            "file_b_size": os.path.getsize(path_b),
            "verdict": "same_meaning" if dist < 0.15 else "similar" if dist < 0.4 else "different"
        }
