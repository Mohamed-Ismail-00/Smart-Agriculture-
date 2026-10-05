/**
 * pages/about/AboutPage.jsx — Project overview & platform story
 */

import { useNavigate } from "react-router-dom";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import "../Pages.css";
import "./About.css";

const HIGHLIGHTS = [
  { value: "27", label: "Governorates" },
  { value: "10m", label: "Satellite resolution" },
  { value: "AI", label: "AgriMind insights" },
  { value: "24/7", label: "Land monitoring" },
];

const CAPABILITIES = [
  {
    title: "Satellite Intelligence",
    body: "Register field boundaries and track NDVI vegetation health from Sentinel-2 imagery via Microsoft Planetary Computer.",
    color: "var(--green-600)",
    bg: "var(--green-50)",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
      </svg>
    ),
  },
  {
    title: "Climate & Soil Context",
    body: "Layer Open-Meteo weather signals and SoilGrids soil properties to understand crop stress beyond vegetation indices alone.",
    color: "var(--amber-500)",
    bg: "var(--warning-light)",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2" />
        <circle cx="12" cy="12" r="4" />
      </svg>
    ),
  },
  {
    title: "AgriMind AI Agronomist",
    body: "Conversational AI analyzes your land data and surfaces actionable recommendations — irrigation, crop health, and yield outlook.",
    color: "#7c3aed",
    bg: "#f3e8ff",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3a7 7 0 00-4 12.7V19a2 2 0 002 2h4a2 2 0 002-2v-3.3A7 7 0 0012 3z" />
        <path d="M9 22h6" />
      </svg>
    ),
  },
  {
    title: "Compare & Export",
    body: "Benchmark multiple plots side-by-side and export structured Excel reports for sharing with agronomists or stakeholders.",
    color: "var(--info)",
    bg: "var(--info-light)",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 3H5a2 2 0 00-2 2v14a2 2 0 002 2h5" />
        <path d="M14 3h5a2 2 0 012 2v14a2 2 0 01-2 2h-5" />
        <path d="M12 3v18" />
      </svg>
    ),
  },
];

const AUDIENCE = [
  {
    emoji: "🌾",
    title: "Farmers & Cooperatives",
    body: "Monitor plots remotely, spot vegetation stress early, and get plain-language guidance without GIS expertise.",
  },
  {
    emoji: "📊",
    title: "Agronomists & Analysts",
    body: "Access NDVI time series, environmental layers, and exportable datasets for field-level decision support.",
  },
  {
    emoji: "🏛️",
    title: "Researchers & Policy",
    body: "Aggregate land intelligence across regions to study productivity, water use, and sustainable farming trends.",
  },
];

const WORKFLOW = [
  { title: "Register a land", body: "Draw or upload your field boundary on the interactive map." },
  { title: "Pipeline runs", body: "Satellite, climate, and soil layers are fetched and processed automatically." },
  { title: "Review intelligence", body: "Explore NDVI charts, crop health, water metrics, and satellite previews." },
  { title: "Act with AI", body: "Ask AgriMind for recommendations or export a report for your team." },
];

const TECH_GROUPS = [
  {
    label: "Experience",
    title: "Web Application",
    pills: ["React 19", "Vite", "Recharts", "Leaflet"],
  },
  {
    label: "Core API",
    title: "Backend Services",
    pills: ["FastAPI", "SQLAlchemy", "PostgreSQL", "PostGIS", "APScheduler"],
  },
  {
    label: "Data & AI",
    title: "Intelligence Layer",
    pills: ["Sentinel-2 STAC", "Open-Meteo", "SoilGrids", "Groq LLM", "OpenCV"],
  },
  {
    label: "Ops",
    title: "Infrastructure",
    pills: ["Docker Compose", "NGINX", "Uvicorn", "Excel Export"],
  },
  {
    label: "Geospatial",
    title: "Processing",
    pills: ["NDVI (B08/B04)", "GeoJSON", "Raster tiles", "Timeseries"],
  },
  {
    label: "Security",
    title: "Platform",
    pills: ["JWT Auth", "Role-based access", "API keys", "Soft-delete"],
  },
];

export default function AboutPage() {
  const navigate = useNavigate();
  const { isDrawer } = useBreakpoint();
  const isMobileLayout = isDrawer;

  return (
    <div className={`anim-fade-in about-page${isMobileLayout ? " about-page--mobile" : ""}`}>
      <section className="about-hero anim-stagger" style={{ "--stagger-index": 0 }}>
        <span className="about-hero__blob about-hero__blob--1" aria-hidden="true" />
        <span className="about-hero__blob about-hero__blob--2" aria-hidden="true" />
        <span className="about-hero__badge">Smart Agriculture Data Platform</span>
        <h1 className="about-hero__title">
          {isMobileLayout ? "Precision ag for Egypt" : "Precision agriculture intelligence for Egypt"}
        </h1>
        <p className="about-hero__subtitle">
          A unified platform that turns satellite imagery, climate data, soil science, and AI into
          actionable insights for every registered plot — from the Delta to Upper Egypt.
        </p>
        <div className="about-hero__actions">
          <button type="button" className="btn btn--primary" onClick={() => navigate("/lands/new")}>
            Register a Land
          </button>
          <button type="button" className="btn btn--secondary" onClick={() => navigate("/methodology")}>
            How It Works
          </button>
        </div>
      </section>

      <section className="about-highlights anim-stagger" style={{ "--stagger-index": 1 }} aria-label="Platform highlights">
        {HIGHLIGHTS.map((item) => (
          <div className="about-highlight" key={item.label}>
            <div className="about-highlight__value">{item.value}</div>
            <div className="about-highlight__label">{item.label}</div>
          </div>
        ))}
      </section>

      <section className="about-section anim-stagger" style={{ "--stagger-index": 2 }}>
        <div className="about-mission">
          <div className="about-mission__eyebrow">Our mission</div>
          <p className="about-mission__text">
            Egyptian agriculture faces rising water scarcity, climate volatility, and the need to feed
            a growing population. We built this platform to democratize precision farming — giving every
            farmer, analyst, and decision-maker access to the same satellite-driven intelligence once
            reserved for large enterprises. By combining open geospatial data with modern AI, we help
            teams optimize irrigation, detect crop stress sooner, compare field performance, and make
            evidence-based choices across all 27 governorates.
          </p>
        </div>
      </section>

      <section className="about-section anim-stagger" style={{ "--stagger-index": 3 }}>
        <div className="about-section__head">
          <div>
            <h2 className="about-section__title">What the platform does</h2>
            <p className="about-section__desc">
              End-to-end land intelligence — from boundary registration to AI-guided recommendations.
            </p>
          </div>
        </div>
        <div className="about-cap-grid">
          {CAPABILITIES.map((cap, i) => (
            <div className="about-cap-card anim-stagger" style={{ "--stagger-index": i + 4 }} key={cap.title}>
              <div className="about-cap-card__icon" style={{ background: cap.bg, color: cap.color }}>
                {cap.icon}
              </div>
              <div className="about-cap-card__title">{cap.title}</div>
              <p className="about-cap-card__body">{cap.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="about-section anim-stagger" style={{ "--stagger-index": 4 }}>
        <div className="about-section__head">
          <div>
            <h2 className="about-section__title">Built for</h2>
            <p className="about-section__desc">Designed for the people who grow, analyze, and govern Egyptian agriculture.</p>
          </div>
        </div>
        <div className="about-audience-grid">
          {AUDIENCE.map((item) => (
            <div className="about-audience-card" key={item.title}>
              <div className="about-audience-card__emoji" aria-hidden="true">{item.emoji}</div>
              <div>
                <div className="about-audience-card__title">{item.title}</div>
                <p className="about-audience-card__body">{item.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="about-section anim-stagger" style={{ "--stagger-index": 5 }}>
        <div className="about-section__head">
          <div>
            <h2 className="about-section__title">From plot to insight</h2>
            <p className="about-section__desc">A simple workflow that runs heavy geospatial processing behind the scenes.</p>
          </div>
        </div>
        <div className="about-timeline">
          {WORKFLOW.map((step, i) => (
            <div className="about-step" key={step.title}>
              <div className="about-step__num">{i + 1}</div>
              <div className="about-step__title">{step.title}</div>
              <p className="about-step__body">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="about-section anim-stagger" style={{ "--stagger-index": 6 }}>
        <div className="about-section__head">
          <div>
            <h2 className="about-section__title">Technology stack</h2>
            <p className="about-section__desc">
              Containerized microservices with a React client, FastAPI backend, and PostgreSQL + PostGIS datastore.
            </p>
          </div>
        </div>
        <div className="about-tech-grid">
          {TECH_GROUPS.map((group, i) => (
            <div className="about-tech-group anim-stagger" style={{ "--stagger-index": i + 7 }} key={group.title}>
              <div className="about-tech-group__label">{group.label}</div>
              <div className="about-tech-group__title">{group.title}</div>
              <div className="about-tech-pills">
                {group.pills.map((pill) => (
                  <span className="about-tech-pill" key={pill}>{pill}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="about-cta anim-stagger" style={{ "--stagger-index": 8 }}>
        <div>
          <div className="about-cta__title">Ready to explore?</div>
          <p className="about-cta__body">
            Dive deeper into our data methodology or start monitoring your first field today.
          </p>
        </div>
        <div className="about-cta__actions">
          <button type="button" className="btn btn--primary" onClick={() => navigate("/lands")}>
            View My Lands
          </button>
          <button type="button" className="btn btn--secondary" onClick={() => navigate("/methodology")}>
            Data & Methodology
          </button>
        </div>
      </section>
    </div>
  );
}