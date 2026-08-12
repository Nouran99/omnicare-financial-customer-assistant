export default function HomePage() {
  return (
    <main className="page-shell">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">OmniCare prototype</p>
        <h1 id="page-title">Financial customer assistance, grounded in policy evidence.</h1>
        <p className="lede">
          A focused insurance-support experience for coverage questions, mock claim-status
          lookups, and validated claim submissions.
        </p>
      </section>

      <section className="capability-grid" aria-label="Supported capabilities">
        <article className="capability-card">
          <span className="card-index">01</span>
          <h2>Policy coverage</h2>
          <p>Ask about the supplied policy and receive answers tied to local evidence.</p>
        </article>
        <article className="capability-card">
          <span className="card-index">02</span>
          <h2>Claim status</h2>
          <p>Look up a known mock claim without exposing unrelated records.</p>
        </article>
        <article className="capability-card">
          <span className="card-index">03</span>
          <h2>Claim submission</h2>
          <p>Submit validated mock-claim details through the governed assistant flow.</p>
        </article>
      </section>

      <p className="disclaimer">
        This is a technical-assessment prototype using mock insurance data. It is not a source
        of real coverage, authorization, or claims decisions.
      </p>
    </main>
  );
}
