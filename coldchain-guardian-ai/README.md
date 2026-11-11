# ColdChain Guardian AI

AI-powered cold-chain logistics monitoring system. Detects temperature excursions, door-breach incidents, and maintenance failures using hybrid RAG, temporal analysis, and an LLM investigation agent.

## Prerequisites

- Python 3.11+
- PostgreSQL 16+ with `pgvector` extension
- Node.js 20+

## Day 1 – Generate synthetic data

```bash
python data/seed.py
```

Output files land in `data/synthetic/`.
