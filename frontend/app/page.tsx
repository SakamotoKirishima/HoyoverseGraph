"use client";

import type { FormEvent } from "react";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      return;
    }

    router.push(`/search?q=${encodeURIComponent(trimmedQuery)}`);
  }

  return (
    <main>
      <section className="hero">
        <p className="muted">Hoyoverse Knowledge Graph</p>
        <h1>Graph and search tooling for lore-first exploration.</h1>
        <p>
          Use the graph page to expand from a seed entity, inspect relationships,
          and pressure-test the knowledge graph contract against real traversal flows.
        </p>
        <form className="search-form home-search" onSubmit={handleSearchSubmit}>
          <label className="field" htmlFor="home-search-query">
            <span className="label">Search the knowledge graph</span>
            <input
              className="control"
              id="home-search-query"
              name="q"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search characters, concepts, factions, locations..."
            />
          </label>
          <button className="primary-button" type="submit">
            Search
          </button>
        </form>
        <div className="hero-links">
          <Link className="hero-link" href="/graph">
            Open Graph Page
          </Link>
        </div>
      </section>
    </main>
  );
}
