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
        <h1>Explore the connections across HoYoverse worlds.</h1>
        <p>
          A source-backed knowledge platform for researching characters, concepts,
          factions, locations, artifacts, events, and recurring connections across
          HoYoverse titles. Claims are linked to their sources.
        </p>
        <p>
          Search for something specific or explore relationships through the graph.
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
