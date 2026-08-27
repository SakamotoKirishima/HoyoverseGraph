"use client";

import type { FormEvent } from "react";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

type FeaturedEntity = {
  entityId: string;
  name: string;
  entityType: string;
  primaryScopeGame: string;
  description: string;
};

// Curated editorial entry points for users who want a reliable place to start exploring.
const FEATURED_ENTITIES: FeaturedEntity[] = [
  {
    entityId: "ENT-0804",
    name: "Kiana Kaslana",
    entityType: "character",
    primaryScopeGame: "Multi",
    description: "A cross-title protagonist anchor for following identity links across Honkai continuities.",
  },
  {
    entityId: "ENT-0121",
    name: "Raiden Shogun",
    entityType: "character",
    primaryScopeGame: "Genshin Impact",
    description: "A strong entry point for tracing character, region, and world relationships in Teyvat.",
  },
  {
    entityId: "ENT-0003",
    name: "Inazuma",
    entityType: "location",
    primaryScopeGame: "Genshin Impact",
    description: "Start from a region to move outward into factions, characters, and setting context.",
  },
  {
    entityId: "ENT-0099",
    name: "Teyvat",
    entityType: "world",
    primaryScopeGame: "Genshin Impact",
    description: "Use a world-level node to branch into broader location and storyline connections.",
  },
];

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
        <div className="hero-actions">
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
            <Link className="hero-link hero-link-secondary" href="/graph">
              Explore Graph
            </Link>
            <p className="hero-link-copy">Explore relationships visually.</p>
          </div>
        </div>
      </section>
      <section className="panel discovery-section" aria-labelledby="featured-entities-title">
        <div className="discovery-heading">
          <p className="eyebrow">Start Exploring</p>
          <h2 className="section-title" id="featured-entities-title">
            Featured entities
          </h2>
          <p className="lead">
            Curated editorial entry points for browsing characters, places, and world-level connections.
          </p>
        </div>
        <div className="featured-grid">
          {FEATURED_ENTITIES.map((entity) => (
            <Link
              key={entity.entityId}
              className="featured-card"
              href={`/entities/${entity.entityId}`}
            >
              <div className="featured-card-header">
                <h3>{entity.name}</h3>
                <span className="chip">{entity.entityType}</span>
              </div>
              <p className="featured-meta">{entity.primaryScopeGame}</p>
              <p className="featured-description">{entity.description}</p>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
