from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel

from ckeditor_audit.tools.grep_code import GrepCodeReport, grep_code as _grep_code
from ckeditor_audit.tools.common import TokenSavings


class SearchQuery(BaseModel):
    """One query entry for multi_search."""

    query: str
    directory: str | None = None
    extensions: list[str] | None = None
    max_results: int | None = None
    case_sensitive: bool | str = "smart"
    whole_word: bool = False
    fixed_string: bool = False
    path_glob: str | None = None
    multiline: bool = False
    exclude_comments: bool = False
    exclude_strings: bool = False
    rank: bool = True
    output: str = "compact"


class SearchResult(BaseModel):
    query: str
    compact: str | None = None
    matches: list | None = None
    has_more: bool = False
    token_savings: TokenSavings | None = None
    error: str | None = None


class MultiSearchReport(BaseModel):
    results: list[SearchResult]
    token_savings: TokenSavings


def multi_search(
    queries: list[SearchQuery],
    max_parallel: int = 5,
) -> MultiSearchReport:
    """Execute multiple independent grep_code searches in parallel.

    Use this when you need several unrelated searches at once — e.g. looking for
    a class declaration, its usages, and its tests simultaneously. Each query runs
    concurrently; total wall time ≈ slowest single query instead of sum of all.

    Do NOT use for dependent queries (where one result informs the next search).

    Args:
        queries: List of search queries. Each has the same parameters as grep_code.
                 Maximum 10 queries per call.
        max_parallel: Maximum concurrent rg processes (default 5, capped at 10).

    Returns:
        results: One SearchResult per query, in the same order as input.
                 Each result includes compact/matches, has_more, and per-query token_savings.
                 On error, result.error is set and other fields are None.
        token_savings: Aggregated token savings across all queries.
    """
    capped_queries = queries[:10]
    workers = min(max(max_parallel, 1), 10, len(capped_queries))

    def _run(idx: int, q: SearchQuery) -> tuple[int, SearchResult]:
        try:
            report: GrepCodeReport = _grep_code(
                query=q.query,
                directory=q.directory,
                extensions=q.extensions,
                max_results=q.max_results,
                case_sensitive=q.case_sensitive,
                whole_word=q.whole_word,
                fixed_string=q.fixed_string,
                path_glob=q.path_glob,
                multiline=q.multiline,
                exclude_comments=q.exclude_comments,
                exclude_strings=q.exclude_strings,
                rank=q.rank,
                output=q.output,
            )
            return idx, SearchResult(
                query=q.query,
                compact=report.compact,
                matches=report.matches,
                has_more=report.has_more,
                token_savings=report.token_savings,
            )
        except Exception as exc:
            return idx, SearchResult(query=q.query, error=str(exc))

    ordered: list[SearchResult | None] = [None] * len(capped_queries)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run, i, q): i for i, q in enumerate(capped_queries)}
        for fut in as_completed(futures):
            idx, result = fut.result()
            ordered[idx] = result

    results = [r for r in ordered if r is not None]

    total_files = sum(
        r.token_savings.files_scanned for r in results if r.token_savings
    )
    total_saved = sum(
        r.token_savings.estimated_tokens_saved for r in results if r.token_savings
    )
    errors = sum(1 for r in results if r.error)

    note = (
        f"{len(capped_queries)} queries run in parallel ({workers} workers)"
        + (f", {errors} error(s)" if errors else "")
    )

    return MultiSearchReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=total_files,
            estimated_tokens_saved=total_saved,
            note=note,
        ),
    )
