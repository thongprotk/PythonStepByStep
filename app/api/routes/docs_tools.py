from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tools import doc_scraper
from app.tools.doc_retriever import load_docs

router = APIRouter(prefix="/docs", tags=["docs-tools"])


class ScrapeRequest(BaseModel):
    urls: list[str]


class ScrapedDocOut(BaseModel):
    url: str
    title: str
    path: str


class ScrapeErrorOut(BaseModel):
    url: str
    error: str


class ScrapeResponse(BaseModel):
    saved: list[ScrapedDocOut]
    errors: list[ScrapeErrorOut]


class DocSummary(BaseModel):
    title: str
    source: str
    path: str


@router.post("/scrape", response_model=ScrapeResponse)
def scrape_docs(request: ScrapeRequest) -> ScrapeResponse:
    """Fetch each URL, extract its main content, save as Markdown in docs/.

    Callable by a chat agent orchestrator as a tool to refresh the grounding
    material `/mida-assistant` retrieves from before answering a question.
    """
    if not request.urls:
        raise HTTPException(status_code=422, detail="urls must be a non-empty list")

    result = doc_scraper.scrape_urls(request.urls)
    return ScrapeResponse(
        saved=[
            ScrapedDocOut(url=d.url, title=d.title, path=str(d.path))
            for d in result["saved"]
        ],
        errors=[ScrapeErrorOut(**e) for e in result["errors"]],
    )


@router.get("/list", response_model=list[DocSummary])
def list_docs() -> list[DocSummary]:
    return [
        DocSummary(title=d.title, source=d.source, path=str(d.path))
        for d in load_docs()
    ]
