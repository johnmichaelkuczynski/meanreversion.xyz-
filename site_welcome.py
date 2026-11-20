"""Plain-language welcome and user guide for Mean Reversion."""

import streamlit as st


def render_welcome_readme() -> None:
    """Render the pre-access welcome and explain what the research tool does."""
    st.markdown(
        """
        <style>
        .mr-welcome {
            --mr-ink: #182b43;
            --mr-muted: #52677d;
            --mr-blue: #3478b9;
            --mr-line: #d8e3ee;
            --mr-paper: #ffffff;
            --mr-wash: #e8f1fa;
            --mr-caution: #fff5df;
            color: var(--mr-ink);
            max-width: 1040px;
            margin: 0 auto 2.5rem;
            animation: mr-arrive 420ms ease-out both;
        }
        .mr-welcome * { box-sizing: border-box; }
        .mr-welcome .mr-intro {
            padding: clamp(1.35rem, 4vw, 2.5rem);
            border: 1px solid var(--mr-line);
            border-radius: 18px;
            background: linear-gradient(120deg, #e8f1fa 0%, #f6f9fc 72%);
        }
        .mr-welcome .mr-kicker {
            margin: 0 0 .55rem;
            color: var(--mr-blue);
            font-size: .76rem;
            font-weight: 750;
            letter-spacing: .13em;
            text-transform: uppercase;
        }
        .mr-welcome h1 {
            margin: 0;
            color: var(--mr-ink);
            font-size: clamp(2rem, 5vw, 3.35rem);
            line-height: 1.05;
            letter-spacing: -.045em;
        }
        .mr-welcome .mr-lede {
            max-width: 720px;
            margin: 1rem 0 0;
            color: #344c65;
            font-size: clamp(1.05rem, 2vw, 1.22rem);
            line-height: 1.65;
        }
        .mr-welcome .mr-section { margin-top: 1.8rem; }
        .mr-welcome h2 {
            margin: 0 0 .75rem;
            color: var(--mr-ink);
            font-size: clamp(1.25rem, 2.5vw, 1.65rem);
            letter-spacing: -.025em;
        }
        .mr-welcome p {
            color: var(--mr-muted);
            font-size: 1rem;
            line-height: 1.7;
        }
        .mr-welcome .mr-steps {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .85rem;
            margin-top: .9rem;
        }
        .mr-welcome .mr-step {
            min-height: 138px;
            padding: 1.1rem 1.15rem;
            border: 1px solid var(--mr-line);
            border-radius: 14px;
            background: var(--mr-paper);
        }
        .mr-welcome .mr-step-label {
            display: block;
            margin-bottom: .4rem;
            color: var(--mr-blue);
            font-size: .75rem;
            font-weight: 750;
            letter-spacing: .1em;
            text-transform: uppercase;
        }
        .mr-welcome .mr-step strong {
            display: block;
            margin-bottom: .35rem;
            color: var(--mr-ink);
            font-size: 1.02rem;
        }
        .mr-welcome .mr-step p { margin: 0; font-size: .94rem; }
        .mr-welcome .mr-verdict {
            margin-top: .95rem;
            padding: 1rem 1.2rem;
            border-left: 4px solid var(--mr-blue);
            border-radius: 0 12px 12px 0;
            background: var(--mr-wash);
        }
        .mr-welcome .mr-verdict p { margin: 0; color: #344c65; }
        .mr-welcome .mr-caveat {
            padding: 1.1rem 1.2rem;
            border: 1px solid #ead8ae;
            border-radius: 14px;
            background: var(--mr-caution);
        }
        .mr-welcome .mr-caveat h2 { margin-bottom: .45rem; }
        .mr-welcome .mr-caveat p { margin: .4rem 0 0; color: #584b31; }
        .mr-welcome .mr-access {
            padding: 1.1rem 1.2rem;
            border: 1px solid var(--mr-line);
            border-radius: 14px;
            background: var(--mr-paper);
        }
        .mr-welcome .mr-access p { margin: .35rem 0 0; }
        @keyframes mr-arrive {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @media (prefers-reduced-motion: reduce) {
            .mr-welcome { animation: none; }
        }
        @media (max-width: 640px) {
            .mr-welcome .mr-steps { grid-template-columns: 1fr; }
            .mr-welcome .mr-step { min-height: auto; }
        }
        </style>
        <article class="mr-welcome">
          <header class="mr-intro">
            <p class="mr-kicker">ZHI Systems · Investor research</p>
            <h1>Mean Reversion</h1>
            <p class="mr-lede">
              A research tool for understanding a stock’s long-run price behavior:
              whether its trend has grown, and how today’s price sits relative to that trend.
            </p>
          </header>

          <section class="mr-section" aria-labelledby="mr-meaning">
            <h2 id="mr-meaning">What “mean reversion” means</h2>
            <p>
              Mean reversion is the idea that a price that has moved unusually far from
              its typical level may move back toward it over time. Here, the reference is
              a fitted, growing long-term trend—not a promise that a stock will return
              to it. Some prices move back; others stay far from trend or move farther away.
            </p>
          </section>

          <section class="mr-section" aria-labelledby="mr-reading">
            <h2 id="mr-reading">How to read the research</h2>
            <div class="mr-steps">
              <div class="mr-step">
                <span class="mr-step-label">01 · Screen</span>
                <strong>Look for a rising history</strong>
                <p>
                  The analysis looks for stocks whose historical prices tend to return
                  toward a growing long-term trend.
                </p>
              </div>
              <div class="mr-step">
                <span class="mr-step-label">02 · Trend</span>
                <strong>Check whether it rises</strong>
                <p>
                  A fitted straight mean trend summarizes the historical direction.
                  Its annualized growth rate describes how quickly that line rose over
                  the measured period; it is not a forecast of future growth.
                </p>
              </div>
              <div class="mr-step">
                <span class="mr-step-label">03 · Distance</span>
                <strong>Compare price with trend</strong>
                <p>
                  For a chosen date, see how far the observed price is above or below
                  the mean trend. This describes historical positioning, not a signal
                  that price must move in either direction.
                </p>
              </div>
              <div class="mr-step">
                <span class="mr-step-label">04 · Estimates</span>
                <strong>Read the trend range carefully</strong>
                <p>
                  Straight upper, mean, and lower trend lines project possible price
                  paths. Historically based probability estimates summarize how often
                  past observations fit the analysis; they are estimates, not validated
                  probabilities of future growth or outperformance.
                </p>
              </div>
            </div>
            <div class="mr-verdict">
              <p>
                <strong>WINNER</strong> summarizes historical screening evidence for a
                stock. It is not a prediction, recommendation, or guarantee of future results.
              </p>
            </div>
          </section>

          <section class="mr-section mr-caveat" aria-labelledby="mr-risk">
            <h2 id="mr-risk">Important: estimates are uncertain</h2>
            <p>
              The goal is to find strong growth potential that could outpace inflation.
              This tool does not establish that a stock will grow, beat inflation, or
              outperform another investment. Prices can remain away from trend, projected
              prices and probabilities are estimates, and you can lose some or all of the
              money you invest. Historical behavior does not assure future results.
            </p>
          </section>

          <section class="mr-section mr-access" aria-labelledby="mr-access-heading">
            <h2 id="mr-access-heading">Using the app</h2>
            <p>
              Google sign-in and payment are required to use the app. Configured
              administrators are exempt from payment. Sign in with Google above.
              Both app pages unlock after your payment is verified.
            </p>
          </section>
        </article>
        """,
        unsafe_allow_html=True,
    )
    return None
