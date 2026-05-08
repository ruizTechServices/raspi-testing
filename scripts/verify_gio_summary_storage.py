from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from unified_server.gio_repository import GioSupabaseRepository
from unified_server.supabase_client import SupabaseRequestError


PROBE_TITLE = "summary storage probe"
PROBE_CONTENT = "- probe summary"
PROBE_MODEL = "gpt-4.1-mini"


def main() -> int:
    repo = GioSupabaseRepository()
    summary_table_available = repo._summary_storage_available()
    print(f"summary_table_available={summary_table_available}")

    conversation = repo.create_conversation(PROBE_TITLE)
    print(f"probe_conversation_id={conversation.id}")

    try:
        summary = repo.save_summary(
            conversation_id=conversation.id,
            content=PROBE_CONTENT,
            model=PROBE_MODEL,
            embedding=None,
        )
        print(f"saved_summary_id={summary.id}")

        summary_table_rows = []
        if summary_table_available:
            try:
                summary_table_rows = repo.client.select(
                    repo.summaries_table,
                    query={
                        "select": "id,conversation_id,content,model,created_at,updated_at",
                        "conversation_id": f"eq.{conversation.id}",
                        "limit": "5",
                    },
                )
            except SupabaseRequestError as exc:
                print(f"summary_table_query_error={exc}")
                return 1

        message_rows = repo.client.select(
            repo.messages_table,
            query={
                "select": "id,conversation_id,role,content,model,created_at",
                "conversation_id": f"eq.{conversation.id}",
                "order": "created_at.asc",
            },
        )
        summary_message_rows = [row for row in message_rows if row.get("role") == "summary"]

        if summary_table_rows:
            storage_path = "table"
        elif summary_message_rows:
            storage_path = "fallback_message"
        else:
            storage_path = "missing"

        print(f"storage_path={storage_path}")
        print(f"summary_table_rows={len(summary_table_rows)}")
        print(f"summary_message_rows={len(summary_message_rows)}")
        print(f"all_message_rows={len(message_rows)}")
        print(f"latest_summary={asdict(repo.get_latest_summary(conversation.id)) if repo.get_latest_summary(conversation.id) else None}")

        if summary_table_rows:
            print(f"summary_table_row={summary_table_rows[0]}")
        if summary_message_rows:
            print(f"summary_message_row={summary_message_rows[0]}")

        if summary_table_available and storage_path != "table":
            print("error=summary table is available but save_summary did not use it")
            return 1
        if not summary_table_available and storage_path != "fallback_message":
            print("error=summary table is unavailable but fallback message path did not work")
            return 1

        return 0
    finally:
        repo.delete_conversation(conversation.id)
        print(f"cleaned_probe_conversation_id={conversation.id}")


if __name__ == "__main__":
    sys.exit(main())
