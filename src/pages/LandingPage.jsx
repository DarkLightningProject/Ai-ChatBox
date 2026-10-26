import React, { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import ThemeToggle from "../Components/ThemeToggle";
import "./LandingPage.css";

const features = [
  {
    icon: "chat",
    title: "A chat that gets you",
    description:
      "Ask questions, explore ideas, and keep the conversation moving at your pace.",
  },
  {
    icon: "debug",
    title: "Debug from every angle",
    description:
      "Bring in specialist AI agents to reason through code, runtime, and performance issues.",
  },
  {
    icon: "file",
    title: "Give your files a voice",
    description:
      "Upload documents and images to extract text, ask questions, and get useful context.",
  },
];

function LandingIcon({ name, className = "" }) {
  if (name === "debug") {
    return <span className={`landing-icon-glyph ${className}`} aria-hidden="true">⌘</span>;
  }

  const paths = {
    chat: (
      <>
        <path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.8-3.2A7.5 7.5 0 1 1 20 11.5Z" />
        <path d="M8.5 11.5h.01M12.5 11.5h.01M16.5 11.5h.01" />
      </>
    ),
    file: (
      <>
        <path d="M7 3.75h7l4.25 4.3v12.2H7a2 2 0 0 1-2-2v-12.5a2 2 0 0 1 2-2Z" />
        <path d="M14 4v4.5h4.25M8.5 12h6M8.5 15.5h6" />
      </>
    ),
    sparkle: (
      <>
        <path d="m12 3 1.8 6.2L20 11l-6.2 1.8L12 19l-1.8-6.2L4 11l6.2-1.8L12 3Z" />
        <path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" />
      </>
    ),
    brainstorm: (
      <>
        <path d="M9 18h6M10 21h4M8.2 14.5a6 6 0 1 1 7.6 0c-.8.6-1.3 1.2-1.5 2h-4.6c-.2-.8-.7-1.4-1.5-2Z" />
        <path d="M12 2v2M4.9 4.9l1.4 1.4M2 12h2" />
      </>
    ),
    arrowUp: <path d="M12 19V5m-6 6 6-6 6 6" />,
    arrowRight: <path d="M5 12h14m-6-6 6 6-6 6" />,
    arrowDown: <path d="M12 5v14m6-6-6 6-6-6" />,
  };

  return (
    <svg
      className={`landing-icon ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths[name]}
    </svg>
  );
}

export default function LandingPage({ theme = "light", onToggleTheme }) {
  const heroVisualRef = useRef(null);
  const featuresRef = useRef(null);

  useEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    root.classList.add("landing-page-scroll");
    body.classList.add("landing-page-scroll");

    return () => {
      root.classList.remove("landing-page-scroll");
      body.classList.remove("landing-page-scroll");
    };
  }, []);

  useEffect(() => {
    const visual = heroVisualRef.current;
    if (!visual) return undefined;

    const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    let frameId = null;
    const requestFrame = window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 16));
    const cancelFrame = window.cancelAnimationFrame || window.clearTimeout;

    const updateParallax = () => {
      if (frameId !== null) cancelFrame(frameId);
      frameId = requestFrame(() => {
        frameId = null;
        const offset = prefersReducedMotion?.matches
          ? 0
          : Math.max(-52, Math.min(0, -window.scrollY * 0.09));
        visual.style.setProperty("--landing-scene-y", `${offset.toFixed(1)}px`);

        if (prefersReducedMotion?.matches) {
          visual.style.setProperty("--landing-tilt-x", "0deg");
          visual.style.setProperty("--landing-tilt-y", "0deg");
        }
      });
    };

    window.addEventListener("scroll", updateParallax, { passive: true });
    window.addEventListener("resize", updateParallax);
    prefersReducedMotion?.addEventListener?.("change", updateParallax);
    updateParallax();

    return () => {
      window.removeEventListener("scroll", updateParallax);
      window.removeEventListener("resize", updateParallax);
      prefersReducedMotion?.removeEventListener?.("change", updateParallax);
      if (frameId !== null) cancelFrame(frameId);
    };
  }, []);

  const handleVisualPointerMove = (event) => {
    const visual = heroVisualRef.current;
    if (!visual || (event.pointerType && event.pointerType !== "mouse" && event.pointerType !== "pen")) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) return;
    if (!Number.isFinite(event.clientX) || !Number.isFinite(event.clientY)) return;

    const bounds = visual.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const horizontal = Math.max(-1, Math.min(1, (event.clientX - (bounds.left + bounds.width / 2)) / (bounds.width / 2)));
    const vertical = Math.max(-1, Math.min(1, (event.clientY - (bounds.top + bounds.height / 2)) / (bounds.height / 2)));
    visual.style.setProperty("--landing-tilt-x", `${(horizontal * 5).toFixed(2)}deg`);
    visual.style.setProperty("--landing-tilt-y", `${(vertical * -4).toFixed(2)}deg`);
  };

  const resetVisualPointer = () => {
    heroVisualRef.current?.style.setProperty("--landing-tilt-x", "0deg");
    heroVisualRef.current?.style.setProperty("--landing-tilt-y", "0deg");
  };

  const scrollToFeatures = (event) => {
    event.preventDefault();
    featuresRef.current?.scrollIntoView({
      behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ? "auto" : "smooth",
      block: "start",
    });
  };

  return (
    <main className={`landing-page ${theme}-theme`}>
      <div className="landing-grain" aria-hidden="true" />
      <nav className="landing-nav" aria-label="Main navigation">
        <Link className="landing-brand" to="/" aria-label="conversa Ai home">
          <span className="landing-brand-mark" aria-hidden="true">✳</span>
          <span>conversa Ai</span>
        </Link>
        <div className="landing-nav-links">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <Link className="landing-login-link" to="/login"><span>Log in</span></Link>
          <Link className="landing-nav-cta landing-about-link" to="/about">About</Link>
          <Link className="landing-nav-cta" to="/signup">Get started <span aria-hidden="true">↗</span></Link>
        </div>
      </nav>

      <section className="landing-hero" aria-labelledby="landing-heading">
        <div className="landing-hero-copy">
          <div className="landing-eyebrow">
            <span className="landing-eyebrow-dot" />
            YOUR IDEAS, WITH ROOM TO GO FURTHER
          </div>
          <h1 id="landing-heading">
            A little more
            <br />
            <span>human</span> in your
            <br />
            corner.
          </h1>
          <p className="landing-hero-description">
            Think out loud, get unstuck, and turn “what if?” into what’s next.
            One chat for curious minds and big ideas.
          </p>
          <div className="landing-hero-actions">
            <Link className="landing-primary-cta" to="/signup">
              Start chatting <LandingIcon name="arrowRight" />
            </Link>
            <a className="landing-secondary-cta" href="#features" onClick={scrollToFeatures}>
              Take a look <LandingIcon name="arrowDown" className="landing-scroll-arrow" />
            </a>
          </div>
          <div className="landing-social-proof">
            <div className="landing-avatar-stack" aria-hidden="true">
              <span>✦</span><span>●</span><span>✳</span>
            </div>
            <p><strong>Curiosity looks good on you.</strong><br />Come ask your first question.</p>
          </div>
        </div>

        <div
          className="landing-visual"
          ref={heroVisualRef}
          aria-label="A preview of a conversa Ai conversation"
          onPointerMove={handleVisualPointerMove}
          onPointerLeave={resetVisualPointer}
        >
          <div className="landing-orbit landing-orbit-one" />
          <div className="landing-orbit landing-orbit-two" />
          <div className="landing-spark landing-spark-one"><LandingIcon name="sparkle" /></div>
          <div className="landing-spark landing-spark-two"><LandingIcon name="sparkle" /></div>

          <div className="landing-preview-card">
            <div className="landing-preview-topbar">
              <div className="landing-preview-brand">
                <span className="landing-preview-logo">✳</span>
                <span>conversa Ai</span>
              </div>
              <span className="landing-preview-menu" aria-hidden="true">•••</span>
            </div>
            <div className="landing-preview-body">
              <div className="landing-preview-greeting">
                <span className="landing-preview-sparkle"><LandingIcon name="sparkle" /></span>
                <div>
                  <span className="landing-preview-kicker">A FRESH START</span>
                  <h2>What’s on your mind?</h2>
                </div>
              </div>
              <div className="landing-preview-message landing-preview-user">
                Help me make sense of a big idea.
              </div>
              <div className="landing-preview-answer">
                <span className="landing-answer-icon"><LandingIcon name="sparkle" /></span>
                <p>Absolutely. Let’s untangle it together, one thought at a time.</p>
              </div>
              <div className="landing-preview-suggestions">
                <span><LandingIcon name="brainstorm" /> Brainstorm</span>
                <span><LandingIcon name="debug" /> Debug code</span>
                <span><LandingIcon name="file" /> Explore a file</span>
              </div>
              <div className="landing-preview-input">
                <span>Ask anything…</span>
                <span className="landing-send-button"><LandingIcon name="arrowUp" /></span>
              </div>
            </div>
          </div>

          <div className="landing-float-card landing-float-debug">
            <span className="landing-float-icon landing-float-icon-purple"><LandingIcon name="debug" /></span>
            <span><strong>Multi-Debugger</strong><small>More minds on the problem</small></span>
            <span className="landing-float-status" aria-label="Ready" />
          </div>
          <div className="landing-float-card landing-float-file">
            <span className="landing-float-icon landing-float-icon-orange"><LandingIcon name="file" /></span>
            <span><strong>File insights</strong><small>Context, in a snap</small></span>
            <span className="landing-float-check" aria-hidden="true">✓</span>
          </div>
        </div>
      </section>

      <section className="landing-features" id="features" ref={featuresRef} aria-labelledby="features-heading">
        <div className="landing-section-heading">
          <span>MADE FOR THE WAY YOU THINK</span>
          <h2 id="features-heading">More than a blank chat.</h2>
          <p>From first thought to final fix, there’s space for all of it.</p>
        </div>
        <div className="landing-feature-grid">
          {features.map((feature, index) => (
            <article className="landing-feature-card" key={feature.title} style={{ "--card-index": index }}>
              <span className={`landing-feature-icon landing-feature-icon-${index}`}>
                <LandingIcon name={feature.icon} />
              </span>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
              <span className="landing-feature-arrow"><LandingIcon name="arrowRight" /></span>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-bottom-cta">
        <div>
          <span>YOUR NEXT GOOD QUESTION IS WAITING</span>
          <h2>Let’s see where your mind goes.</h2>
        </div>
        <Link className="landing-primary-cta" to="/signup">
          Make it a conversation <LandingIcon name="arrowRight" />
        </Link>
      </section>

      <footer className="landing-footer">
        <Link className="landing-brand" to="/">
          <span className="landing-brand-mark" aria-hidden="true">✳</span>
          <span>conversa Ai</span>
        </Link>
        <span>A space for your next thought.</span>
        <div><Link to="/login">Log in</Link><Link to="/signup">Create account</Link></div>
      </footer>
    </main>
  );
}
