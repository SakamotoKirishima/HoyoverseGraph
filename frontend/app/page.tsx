import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">HoYoverse Knowledge Graph</p>
        <h1>Entity search, with room to grow.</h1>
        <p>
          This frontend is a lightweight shell for the backend search API. Start with
          entity lookup, then expand into richer graph exploration as the data model
          matures.
        </p>
        <div className="actions">
          <Link className="button" href="/search">
            Open Search
          </Link>
          <span className="subtle-link">Backend search is powered by the FastAPI API.</span>
        </div>
      </section>

      <section className="home-grid">
        <article className="home-card">
          <h2>Search entities</h2>
          <p>
            Query canonical names, display labels, aliases, and descriptive text from
            one page.
          </p>
        </article>
        <article className="home-card">
          <h2>Filter by ontology</h2>
          <p>
            Narrow results by entity type and primary scope game without changing the
            underlying API contract.
          </p>
        </article>
        <article className="home-card">
          <h2>Source-aware results</h2>
          <p>
            The first UI version keeps things lightweight while still surfacing how
            many sources are linked to each entity.
          </p>
        </article>
      </section>
    </main>
  );
}
