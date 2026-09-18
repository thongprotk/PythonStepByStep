# docs/

Grounding material for `/mida-assistant`, populated by `POST /docs/scrape`
(`app/tools/doc_scraper.py`) and read back by `app/tools/doc_retriever.py`.

Loop: `POST /docs/scrape {"urls": [...]}` fetches each page, extracts the
main content, converts it to Markdown with a small front-matter header
(`title`, `source`, `scraped_at`), and writes one `.md` file per page here.
`/mida-assistant` then does naive keyword retrieval over these files to
auto-fill `retrieved_chunks` when a caller doesn't supply its own — so a chat
agent gets grounded answers without running its own RAG step.

Scraped files are generated output, not hand-written docs — don't edit them
directly; re-run the scrape instead.
