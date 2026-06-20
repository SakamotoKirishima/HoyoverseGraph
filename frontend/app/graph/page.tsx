import { Suspense } from "react";

import { GraphViewer } from "../../components/GraphViewer";

export default function GraphPage() {
  return (
    <main>
      <section className="hero">
        <p className="muted">Graph Page</p>
        <h1>Explore entity neighborhoods as a living graph.</h1>
        <p>
          Load a seed entity, expand one or two hops, and refine the visible edges
          with predicate, confidence, and evidence filters.
        </p>
      </section>
      <Suspense fallback={<p className="muted">Preparing graph controls...</p>}>
        <GraphViewer />
      </Suspense>
    </main>
  );
}
