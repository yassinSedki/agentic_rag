import json

import httpx
import streamlit as st


st.set_page_config(page_title="Agentic RAG Tester", layout="wide")
st.title("🧠 Agentic RAG – Local Tester")

# Sidebar configuration
st.sidebar.header("Backend Settings")
api_base_url = st.sidebar.text_input(
    "API base URL",
    value="http://localhost:8000",
    help="Base URL of the FastAPI backend.",
)


def _json_headers() -> dict[str, str]:
    """Headers for JSON requests (no auth)."""
    return {"Content-Type": "application/json"}


def ingest_file(file: bytes, filename: str, content_type: str | None = None) -> dict:
    """Call the /ingest endpoint with a file upload."""
    files = {
        "file": (
            filename,
            file,
            content_type or "application/octet-stream",
        )
    }

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{api_base_url}/ingest",
            headers={},
            files=files,
        )
        resp.raise_for_status()
        return resp.json()


def stream_chat(question: str):
    """Call the /chat SSE endpoint and yield incremental answer text."""
    full_answer = ""

    with httpx.Client(timeout=None) as client:
        with client.stream(
            "POST",
            f"{api_base_url}/chat",
            headers=_json_headers(),
            json={"question": question},
        ) as resp:
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue

                # SSE lines are in the form: "data: {...}\n\n"
                if line.startswith("data: "):
                    data = line[len("data: ") :]
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    # Error event
                    if "code" in event and "message" in event:
                        raise RuntimeError(
                            f"Chat error ({event.get('code')}): {event.get('message')}"
                        )

                    # Token event
                    if "chunk" in event:
                        full_answer += event["chunk"]
                        yield full_answer

                    # Done event (has latency_ms / sources / retrieval_score)
                    if "latency_ms" in event:
                        break


tab_ingest, tab_chat = st.tabs(["📥 Ingest Documents", "💬 Chat"])

with tab_ingest:
    st.subheader("Ingest Document into RAG")

    uploaded = st.file_uploader(
        "Upload a document",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=False,
        help="Supported types: PDF, TXT, Markdown, DOCX.",
    )

    if st.button("Ingest", type="primary"):
        if uploaded is None:
            st.warning("Please upload a document to ingest.")
        else:
            try:
                data = uploaded.read()
                result = ingest_file(
                    file=data,
                    filename=uploaded.name,
                    content_type=uploaded.type,
                )
                st.success(
                    f"Ingested successfully: {result.get('chunks_created', 0)} chunks "
                    f"(doc_ids: {', '.join(result.get('doc_ids', []))})"
                )
            except httpx.HTTPStatusError as exc:
                st.error(
                    f"HTTP error from backend: {exc.response.status_code} - {exc.response.text}"
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to ingest: {exc}")

with tab_chat:
    st.subheader("Ask Questions (RAG Chat)")

    question = st.text_area(
        "Your question",
        height=120,
        placeholder="Ask something about the content you ingested...",
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if st.button("Send", type="primary"):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            placeholder = st.empty()
            answer = ""

            try:
                for partial in stream_chat(question):
                    answer = partial
                    placeholder.markdown(f"**Answer (streaming):**\n\n{answer}")

                # Save to history
                st.session_state.chat_history.append((question, answer))
                placeholder.markdown(f"**Answer:**\n\n{answer}")
            except httpx.HTTPStatusError as exc:
                st.error(
                    f"HTTP error from backend: {exc.response.status_code} - {exc.response.text}"
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Chat failed: {exc}")

    if st.session_state.chat_history:
        st.markdown("---")
        st.subheader("Previous Q&A")
        for idx, (q, a) in enumerate(reversed(st.session_state.chat_history), start=1):
            with st.expander(f"Turn {idx}: {q[:60]}..."):
                st.markdown(f"**Q:** {q}")
                st.markdown(f"**A:** {a}")

