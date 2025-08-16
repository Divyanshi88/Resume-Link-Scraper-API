from __future__ import annotations

import asyncio
import os
import re
import random
from typing import List, Optional, Literal, Tuple
from urllib.parse import urlsplit, urlunsplit

import httpx
import fitz  # PyMuPDF
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import trafilatura

try:
    from readability import Document  # Optional fallback
    from lxml.html import fromstring
    HAS_READABILITY = True
except Exception:
    HAS_READABILITY = False


# ---------------------------
# Configuration (Adjustable)
# ---------------------------
class Config:
    USER_AGENT: str = os.getenv(
        "SCRAPER_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 ResumeLinkScraper/1.0",
    )
    REQUEST_TIMEOUT_S: float = float(os.getenv("SCRAPER_TIMEOUT", "12.0"))
    CONNECT_TIMEOUT_S: float = float(os.getenv("SCRAPER_CONNECT_TIMEOUT", "5.0"))
    CONCURRENCY: int = int(os.getenv("SCRAPER_MAX_CONCURRENCY", "6"))
    PER_REQUEST_DELAY_S: float = float(os.getenv("SCRAPER_DELAY", "0.15"))
    MAX_URLS: int = int(os.getenv("SCRAPER_MAX_URLS", "40"))
    MAX_PDF_SIZE_MB: float = float(os.getenv("SCRAPER_MAX_PDF_MB", "10"))


# ---------------------------
# Data Models
# ---------------------------
class ScrapeItem(BaseModel):
    source_url: str = Field(..., description="Normalized source URL", max_length=2000)
    status: Literal["success", "error"]
    scraped_text: Optional[str] = None
    error_message: Optional[str] = None


class ScrapeResponse(BaseModel):
    scraped_data: List[ScrapeItem]


# ---------------------------
# URL Extraction Utilities
# ---------------------------
class URLExtractor:
    _URL_RE = re.compile(
        r"(?:https?://|www\.)[\w.-]+(?::\d{2,5})?(?:/[^\s<]*)?",
        re.IGNORECASE,
    )
    _TRAILING_PUNCT = ")],.;:>\"'"

    @classmethod
    def _strip_trailing_punct(cls, url: str) -> str:
        return url.rstrip(cls._TRAILING_PUNCT)

    @classmethod
    def normalize_url(cls, raw: str) -> Optional[str]:
        raw = raw.strip()
        raw = cls._strip_trailing_punct(raw)
        if raw.lower().startswith("www."):
            raw = "http://" + raw
        try:
            parts = urlsplit(raw)
        except ValueError:
            return None
        if parts.scheme not in {"http", "https"}:
            return None
        if not parts.netloc:
            return None
        parts = parts._replace(fragment="")
        return urlunsplit(parts)

    @classmethod
    def extract_pdf_urls(cls, pdf_bytes: bytes, max_urls: int) -> List[str]:
        urls: set[str] = set()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                # Extract visible URLs via regex from text
                try:
                    text = page.get_text("text") or ""
                    for m in cls._URL_RE.findall(text):
                        norm = cls.normalize_url(m)
                        if norm:
                            urls.add(norm)
                except Exception:
                    pass

                # Extract embedded link annotations
                try:
                    for link in page.get_links() or []:
                        uri = link.get("uri")
                        if uri:
                            norm = cls.normalize_url(uri)
                            if norm:
                                urls.add(norm)
                except Exception:
                    pass

        url_list = list(urls)
        random.shuffle(url_list)
        return url_list[:max_urls]


# ---------------------------
# Content Fetching and Extraction
# ---------------------------
class ContentScraper:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch_html(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            resp = await self.client.get(url)
        except httpx.TimeoutException:
            return None, f"timeout after {Config.REQUEST_TIMEOUT_S}s"
        except httpx.InvalidURL:
            return None, "invalid URL"
        except httpx.RequestError as e:
            return None, f"request error: {e.__class__.__name__}: {e}"

        ctype = resp.headers.get("content-type", "").lower()
        if resp.status_code >= 400:
            return None, f"http {resp.status_code}"
        if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
            return None, f"unsupported content-type: {ctype or 'unknown'}"

        return resp.text, None

    @staticmethod
    def extract_main_text(html: str) -> Optional[str]:
        try:
            txt = trafilatura.extract(html, include_formatting=False, favor_recall=True)
            if txt:
                return re.sub(r"\s{3,}", "\n\n", txt.strip())
        except Exception:
            pass

        if HAS_READABILITY:
            try:
                doc = Document(html)
                root = fromstring(doc.summary(html_partial=True))
                txt = root.text_content()
                if txt:
                    return re.sub(r"\s{3,}", "\n\n", txt.strip())
            except Exception:
                pass

        return None


# ---------------------------
# Async URL Scraper with concurrency limit
# ---------------------------
class ScraperService:
    def __init__(self):
        self.sem = asyncio.Semaphore(Config.CONCURRENCY)

    async def scrape_urls(self, urls: List[str]) -> List[ScrapeItem]:
        headers = {
            "User-Agent": Config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "close",
        }
        timeout = httpx.Timeout(Config.REQUEST_TIMEOUT_S, connect=Config.CONNECT_TIMEOUT_S)

        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True, max_redirects=5
        ) as client:
            scraper = ContentScraper(client)

            async def worker(url: str) -> ScrapeItem:
                await asyncio.sleep(Config.PER_REQUEST_DELAY_S)
                async with self.sem:
                    html, err = await scraper.fetch_html(url)
                    if err:
                        return ScrapeItem(source_url=url, status="error", error_message=err)
                    text = scraper.extract_main_text(html or "")
                    if not text:
                        return ScrapeItem(
                            source_url=url, status="error", error_message="no main content extracted"
                        )
                    return ScrapeItem(source_url=url, status="success", scraped_text=text)

            tasks = [worker(u) for u in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        items: List[ScrapeItem] = []
        for res, url in zip(results, urls):
            if isinstance(res, Exception):
                items.append(
                    ScrapeItem(
                        source_url=url,
                        status="error",
                        error_message=f"internal error: {res.__class__.__name__}: {res}",
                    )
                )
            else:
                items.append(res)
        return items


# ---------------------------
# FastAPI app and routes
# ---------------------------
app = FastAPI(title="Resume Link Scraper API", version="1.0.0")

scraper_service = ScraperService()

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to the Resume Link Scraper API! Visit /docs for API documentation."}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/scrape-resume-links", response_model=ScrapeResponse, response_model_exclude_none=True)
async def scrape_resume_links(resume_pdf: UploadFile = File(...)) -> JSONResponse:
    content = await resume_pdf.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > Config.MAX_PDF_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"PDF too large ({size_mb:.2f} MB). Max {Config.MAX_PDF_SIZE_MB:.0f} MB",
        )

    try:
        urls = URLExtractor.extract_pdf_urls(content, max_urls=Config.MAX_URLS)
    except fitz.FileDataError:
        raise HTTPException(status_code=400, detail="Invalid or corrupted PDF")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF parse error: {e}")

    if not urls:
        raise HTTPException(status_code=422, detail="No hyperlinks found in the PDF")

    items = await scraper_service.scrape_urls(urls)
    return JSONResponse(content=ScrapeResponse(scraped_data=items).dict())

# ---------------------------
# Local entrypoint
# ---------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
