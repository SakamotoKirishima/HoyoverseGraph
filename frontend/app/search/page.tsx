"use client";

import { Suspense } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { getApiBaseUrl } from "../../lib/api";

type SearchResult = {
  entity_id: string;
  canonical_name: string;
  display_label: string | null;
  entity_type: string;
  primary_scope_game: string | null;
  aliases: string[];
  short_description: string | null;
  source_count: number;
};

type SearchApiError = {
  detail?: string | string[];
};

const ENTITY_TYPE_OPTIONS = [
  "",
  "character",
  "game",
  "faction",
  "location",
  "concept",
  "item",
  "group",
] as const;

const GAME_OPTIONS = [
  "",
  "Honkai Impact 3",
  "Honkai: Star Rail",
  "Genshin Impact",
  "Gun Girls Z",
  "Multi",
] as const;

function buildSearchUrl(
  q: string,
  entityType: string,
  primaryScopeGame: string,
): string {
  const params = new URLSearchParams();
  params.set("q", q);
  if (entityType) {
    params.set("entity_type", entityType);
  }
  if (primaryScopeGame) {
    params.set("primary_scope_game", primaryScopeGame);
  }
  return `/search?${params.toString()}`;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Search failed. Please try again.";
}

function SearchPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const urlQuery = searchParams.get("q") ?? "";
  const urlEntityType = searchParams.get("entity_type") ?? "";
  const urlPrimaryScopeGame = searchParams.get("primary_scope_game") ?? "";

  const [query, setQuery] = useState(urlQuery);
  const [entityType, setEntityType] = useState(urlEntityType);
  const [primaryScopeGame, setPrimaryScopeGame] = useState(urlPrimaryScopeGame);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  const hasActiveSearch = useMemo(() => urlQuery.trim().length > 0, [urlQuery]);

  useEffect(() => {
    setQuery(urlQuery);
    setEntityType(urlEntityType);
    setPrimaryScopeGame(urlPrimaryScopeGame);
  }, [urlEntityType, urlPrimaryScopeGame, urlQuery]);

  useEffect(() => {
    const trimmedQuery = urlQuery.trim();

    if (!trimmedQuery) {
      setResults([]);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();

    async function loadResults() {
      setLoading(true);
      setError(null);
      setValidationMessage(null);

      try {
        const apiBaseUrl = getApiBaseUrl();
        const params = new URLSearchParams({ q: trimmedQuery });

        if (urlEntityType) {
          params.set("entity_type", urlEntityType);
        }
        if (urlPrimaryScopeGame) {
          params.set("primary_scope_game", urlPrimaryScopeGame);
        }

        const response = await fetch(`${apiBaseUrl}/search?${params.toString()}`, {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          let message = `Search failed with status ${response.status}.`;
          try {
            const payload = (await response.json()) as SearchApiError;
            if (Array.isArray(payload.detail)) {
              message = payload.detail.join(" ");
            } else if (typeof payload.detail === "string") {
              message = payload.detail;
            }
          } catch {
            // Keep the fallback message when the error response is not JSON.
          }
          throw new Error(message);
        }

        const payload = (await response.json()) as SearchResult[];
        setResults(payload);
      } catch (fetchError) {
        if ((fetchError as Error).name === "AbortError") {
          return;
        }
        setResults([]);
        setError(getErrorMessage(fetchError));
      } finally {
        setLoading(false);
      }
    }

    void loadResults();

    return () => controller.abort();
  }, [urlEntityType, urlPrimaryScopeGame, urlQuery]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setValidationMessage("Enter a search term before submitting.");
      return;
    }

    setValidationMessage(null);
    router.push(buildSearchUrl(trimmedQuery, entityType, primaryScopeGame));
  }

  function handleReset() {
    setQuery("");
    setEntityType("");
    setPrimaryScopeGame("");
    setValidationMessage(null);
    setError(null);
    setResults([]);
    router.push(pathname);
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Search Page</p>
        <h1 className="page-title">Find entities by name, alias, or lore text.</h1>
        <p className="lead">
          Search the HoYoverse knowledge graph backend with lightweight filters for
          entity type and primary scope game. Queries stay in the URL so they can be
          shared or revisited.
        </p>
      </section>

      <section className="panel">
        <form className="search-form" onSubmit={handleSubmit}>
          <div className="field-grid">
            <label className="field">
              <span className="label">Search query</span>
              <input
                className="control"
                type="text"
                name="q"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Try kaslana, bronya, raiden, or Ei"
              />
            </label>

            <label className="field">
              <span className="label">Entity type</span>
              <select
                className="control"
                name="entity_type"
                value={entityType}
                onChange={(event) => setEntityType(event.target.value)}
              >
                {ENTITY_TYPE_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option || "All entity types"}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span className="label">Primary scope game</span>
              <select
                className="control"
                name="primary_scope_game"
                value={primaryScopeGame}
                onChange={(event) => setPrimaryScopeGame(event.target.value)}
              >
                {GAME_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option || "All games"}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="actions">
            <button className="button" type="submit" disabled={loading}>
              {loading ? "Searching..." : "Search"}
            </button>
            <button className="subtle-link" type="button" onClick={handleReset}>
              Reset filters
            </button>
          </div>
        </form>

        {validationMessage ? <p className="message error">{validationMessage}</p> : null}
        {error ? <p className="message error">{error}</p> : null}
      </section>

      <section>
        <div className="results-meta">
          <span>
            {hasActiveSearch
              ? `${results.length} result${results.length === 1 ? "" : "s"}`
              : "Start with a query to explore the graph."}
          </span>
          {hasActiveSearch ? <span>URL-backed search state enabled</span> : null}
        </div>

        {loading ? <p className="message">Loading search results...</p> : null}

        {!loading && hasActiveSearch && !error && results.length === 0 ? (
          <p className="message">No results found. Try a broader query or clear a filter.</p>
        ) : null}

        {!loading && !hasActiveSearch && !validationMessage ? (
          <p className="message">
            Example searches: <strong>kaslana</strong>, <strong>bronya</strong>, or
            <strong> raiden</strong>.
          </p>
        ) : null}

        <div className="results">
          {results.map((result) => {
            const title = result.display_label || result.canonical_name;

            return (
              <article className="card" key={result.entity_id}>
                <h2>
                  <Link className="card-link" href={`/entities/${result.entity_id}`}>
                    {title}
                  </Link>
                </h2>
                <div className="meta-row">
                  {result.entity_id} · {result.entity_type}
                  {result.primary_scope_game ? ` · ${result.primary_scope_game}` : ""}
                </div>

                {result.aliases.length > 0 ? (
                  <div className="aliases">Aliases: {result.aliases.join(", ")}</div>
                ) : null}

                {result.short_description ? (
                  <p className="description">{result.short_description}</p>
                ) : null}

                <div className="chip-row">
                  <span className="chip">Sources: {result.source_count}</span>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<main className="shell"><section className="panel"><p className="message">Preparing search page...</p></section></main>}>
      <SearchPageContent />
    </Suspense>
  );
}
