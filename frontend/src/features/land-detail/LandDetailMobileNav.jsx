/**
 * LandDetailMobileNav — horizontal section tabs for mobile land detail
 */

const SECTIONS = [
  {
    id: "overview",
    label: "Overview",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    id: "crops",
    label: "Crops",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22V12" />
        <path d="M12 12C12 7 7 3 3 3c0 4 2 8 6 9" />
        <path d="M12 12c0-5 5-9 9-9-1 4-3 8-7 9" />
      </svg>
    ),
  },
  {
    id: "satellite",
    label: "Satellite",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="2" />
        <path d="M16.24 7.76a6 6 0 010 8.49M7.76 16.24a6 6 0 010-8.49M19.07 4.93a10 10 0 010 14.14M4.93 19.07a10 10 0 010-14.14" />
      </svg>
    ),
  },
  {
    id: "environment",
    label: "Environment",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v6" />
        <path d="M12 22v-6" />
        <path d="M4.93 4.93l4.24 4.24" />
        <path d="M14.83 14.83l4.24 4.24" />
        <path d="M2 12h6" />
        <path d="M22 12h-6" />
        <path d="M4.93 19.07l4.24-4.24" />
        <path d="M14.83 9.17l4.24-4.24" />
      </svg>
    ),
  },
  {
    id: "water",
    label: "Water",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2.69l5.66 5.66a8 8 0 11-11.32 0z" />
      </svg>
    ),
  },
];

export { SECTIONS };

export default function LandDetailMobileNav({ activeSection, onSectionChange, availableSections }) {
  const tabs = SECTIONS.filter((s) => !availableSections || availableSections.includes(s.id));

  return (
    <nav className="land-detail-mobile-nav" aria-label="Land detail sections">
      <div className="land-detail-mobile-nav__scroll">
        {tabs.map((section) => (
          <button
            key={section.id}
            type="button"
            className={`land-detail-mobile-nav__tab${activeSection === section.id ? " land-detail-mobile-nav__tab--active" : ""}`}
            onClick={() => onSectionChange(section.id)}
            aria-current={activeSection === section.id ? "page" : undefined}
          >
            <span className="land-detail-mobile-nav__icon">{section.icon}</span>
            <span className="land-detail-mobile-nav__label">{section.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}