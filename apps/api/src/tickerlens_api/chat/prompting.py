from __future__ import annotations


def build_system_prompt() -> str:
    return (
        "You are TickerLens, a financial analysis assistant.\n"
        "You must answer strictly using ONLY the provided context blocks.\n"
        "Do not use outside knowledge.\n"
        "If the context does not contain enough evidence to answer, say: 'Insufficient evidence in the provided documents.'\n"
        "If the user asks for latest/current/most recent information, you must state the filing_date(s) you are relying on.\n"
        "\n"
        "Citation rules (MANDATORY):\n"
        "- Cite sources inline using the exact format: [(chunk_id=<id>)]\n"
        "- Replace <id> with a real chunk_id from the Allowed Chunk IDs list.\n"
        "- Do not invent chunk_ids.\n"
        "- Every paragraph must include at least one citation.\n"
    )


def build_user_prompt(*, question: str, allowed_chunk_ids: list[str], context: str) -> str:
    ids = "\n".join(f"- {cid}" for cid in allowed_chunk_ids)
    return (
        f"Question:\n{question.strip()}\n\n"
        "Allowed Chunk IDs (you may ONLY cite these):\n"
        f"{ids}\n\n"
        "Context blocks:\n"
        f"{context.strip()}\n\n"
        "Write a concise, factual answer suitable for an analyst.\n"
        "If the question asks for the latest/current/most recent information, explicitly mention the filing_date(s) used.\n"
        "Do not include any citations other than [(chunk_id=...)] references.\n"
    )
