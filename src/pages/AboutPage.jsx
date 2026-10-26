import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import ThemeToggle from "../Components/ThemeToggle";
import "./AboutPage.css";

const technologies = [
  {
    mark: "UI",
    title: "Frontend",
    description: "React, JavaScript, and CSS build the interactive interface and responsive layouts.",
  },
  {
    mark: "API",
    title: "Backend",
    description: "Python, Django, and Django REST Framework power the application and its APIs.",
  },
  {
    mark: "DB",
    title: "Data storage",
    description: "SQLite is used locally, with Supabase-hosted PostgreSQL for production.",
  },
  {
    mark: "AI",
    title: "AI integrations",
    description: "The backend connects to AI model services through provider APIs, including OpenRouter and Google Gemini.",
  },
  {
    mark: "CD",
    title: "Media & hosting",
    description: "Cloudinary stores uploaded media in production, and Render hosts the backend service.",
  },
];

export default function AboutPage({ theme = "light", onToggleTheme }) {
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

  return (
    <main className={`about-page ${theme}-theme`}>
      <nav className="about-nav" aria-label="About page navigation">
        <Link className="about-brand" to="/" aria-label="conversa Ai home">
          <span className="about-brand-mark" aria-hidden="true">✳</span>
          <span>conversa Ai</span>
        </Link>
        <div className="about-nav-actions">
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <Link className="about-login-link" to="/login"><span>Log in</span></Link>
          <Link className="about-cta" to="/signup">Get started <span aria-hidden="true">↗</span></Link>
        </div>
      </nav>

      <section className="about-hero" aria-labelledby="about-heading">
        <span className="about-kicker"><span aria-hidden="true" /> A LITTLE ABOUT THIS SPACE</span>
        <h1 id="about-heading">Curiosity deserves<br />a <span>good conversation.</span></h1>
        <p>
          conversa Ai is a prototype for exploring ideas with AI—a place to ask,
          create, untangle, and keep moving.
        </p>
        <p className="about-prototype-note" role="note">
          This is a prototype. Use dummy details only to try logging in or signing up. Do not enter real or sensitive information. The site owner is not responsible if information you submit is exposed or leaked.
        </p>

      </section>

      <section className="about-technology" aria-labelledby="about-technology-heading">
        <div className="about-section-heading">
          <span>THE STACK</span>
          <h2 id="about-technology-heading">What this website is built with.</h2>
        </div>
        <div className="about-technology-grid">
          {technologies.map((technology) => (
            <article className="about-technology-card" key={technology.title}>
              <span className="about-technology-mark" aria-hidden="true">{technology.mark}</span>
              <div>
                <h3>{technology.title}</h3>
                <p>{technology.description}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <footer className="about-footer">
        <p>Thoughtful tools for curious minds.</p>
        <div className="about-footer-links">
          <span>Contact us at</span>
          <a href="mailto:eclipsexautomationsolution@gmail.com">eclipsexautomationsolution@gmail.com</a>
          <Link to="/">Back to home</Link>
        </div>
      </footer>
    </main>
  );
}
