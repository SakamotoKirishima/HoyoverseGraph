import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <section className="hero">
        <p className="muted">Hoyoverse Knowledge Graph</p>
        <h1>Graph and search tooling for lore-first exploration.</h1>
        <p>
          Use the graph page to expand from a seed entity, inspect relationships,
          and pressure-test the knowledge graph contract against real traversal flows.
        </p>
        <div className="hero-links">
          <Link className="hero-link" href="/graph">
            Open Graph Page
          </Link>
        </div>
      </section>
    </main>
  );
}
