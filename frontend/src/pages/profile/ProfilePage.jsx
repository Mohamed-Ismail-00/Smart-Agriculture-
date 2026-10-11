/**
 * pages/profile/ProfilePage.jsx — Account, activity & AI API keys
 */

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import { useConfirm } from "../../context/ConfirmContext";
import {
  listLands,
  getAiApiKeys,
  addAiApiKey,
  deleteAiApiKey,
  toggleAiApiKey,
} from "../../services/api";
import "../Pages.css";
import "./Profile.css";

function ProfileStats({ loadingLands, landsCount, totalArea, activeKeys, className = "" }) {
  return (
    <div className={`profile-stats ${className}`.trim()}>
      <div className="profile-stat">
        <div className="profile-stat__value">{loadingLands ? "…" : landsCount}</div>
        <div className="profile-stat__label">Lands</div>
      </div>
      <div className="profile-stat">
        <div className="profile-stat__value">{loadingLands ? "…" : totalArea.toFixed(1)}</div>
        <div className="profile-stat__label">Total ha</div>
      </div>
      <div className="profile-stat">
        <div className="profile-stat__value">{activeKeys}</div>
        <div className="profile-stat__label">AI Keys</div>
      </div>
    </div>
  );
}

function ApiKeyCard({ keyItem, onToggle, onDelete }) {
  const cardClass = keyItem.quota_exceeded
    ? "profile-key-card--quota"
    : keyItem.is_active
      ? "profile-key-card--active"
      : "profile-key-card--inactive";

  return (
    <div className={`profile-key-card ${cardClass}`}>
      <div className="profile-key-card__top">
        <div className="profile-key-card__info">
          <div className="profile-key-card__label">{keyItem.label || `Key #${keyItem.key_id}`}</div>
          <div className="profile-key-card__preview">••••••{keyItem.key_preview}</div>
        </div>
      </div>
      <div className="profile-key-card__badges">
        {keyItem.quota_exceeded ? (
          <span className="badge badge--critical">Quota Exceeded</span>
        ) : keyItem.is_active ? (
          <span className="badge badge--healthy">Active</span>
        ) : (
          <span className="badge badge--neutral">Disabled</span>
        )}
        <span className="badge badge--info" style={{ textTransform: "capitalize" }}>
          {keyItem.provider}
        </span>
      </div>
      <div className="profile-key-card__actions">
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => onToggle(keyItem.key_id, keyItem.is_active)}
        >
          {keyItem.is_active ? "Disable" : "Enable"}
        </button>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          style={{ color: "var(--error)" }}
          onClick={() => onDelete(keyItem.key_id)}
        >
          Remove
        </button>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const { user } = useAuth();
  const confirm = useConfirm();
  const { isDrawer } = useBreakpoint();
  const isMobileLayout = isDrawer;

  const [lands, setLands] = useState([]);
  const [loadingLands, setLoadingLands] = useState(true);
  const [apiKeys, setApiKeys] = useState([]);
  const [newKey, setNewKey] = useState("");
  const [newKeyLabel, setNewKeyLabel] = useState("");
  const [addingKey, setAddingKey] = useState(false);
  const [keyError, setKeyError] = useState(null);
  const [keySuccess, setKeySuccess] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await listLands();
        if (active) setLands(res.lands || []);
      } catch {
        if (active) setLands([]);
      } finally {
        if (active) setLoadingLands(false);
      }
    })();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    loadKeys();
  }, []);

  const loadKeys = async () => {
    try {
      const res = await getAiApiKeys();
      setApiKeys(res.keys || []);
    } catch {
      // ignore
    }
  };

  const handleAddKey = async () => {
    if (!newKey.trim()) return;
    setAddingKey(true);
    setKeyError(null);
    setKeySuccess(null);
    try {
      await addAiApiKey(newKey.trim(), newKeyLabel.trim() || null);
      setKeySuccess("API key added successfully!");
      setNewKey("");
      setNewKeyLabel("");
      setShowAddForm(false);
      await loadKeys();
    } catch (err) {
      setKeyError(err.message || "Failed to add key.");
    } finally {
      setAddingKey(false);
    }
  };

  const handleDeleteKey = async (keyId) => {
    const confirmed = await confirm({
      title: "Remove API Key",
      message: "Remove this API key? AI features may stop working if no other keys are active.",
      confirmLabel: "Remove",
      cancelLabel: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;
    try {
      await deleteAiApiKey(keyId);
      await loadKeys();
    } catch (err) {
      setKeyError(err.message || "Failed to delete key.");
    }
  };

  const handleToggleKey = async (keyId, currentActive) => {
    try {
      await toggleAiApiKey(keyId, !currentActive);
      await loadKeys();
    } catch (err) {
      setKeyError(err.message || "Failed to toggle key.");
    }
  };

  const initials = user?.email ? user.email.charAt(0).toUpperCase() : "?";
  const displayName = user?.email?.split("@")[0] || "User";
  const activeKeyCount = apiKeys.filter((k) => k.is_active).length;

  const totalArea = useMemo(
    () => lands.reduce((sum, land) => sum + Number(land.area_hectares || 0), 0),
    [lands]
  );

  const recentActivity = useMemo(
    () =>
      lands
        .slice()
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 4)
        .map((land) => ({
          action: `Registered ${land.name}`,
          time: new Date(land.created_at).toLocaleDateString(),
          type: land.status === "error" ? "warning" : "success",
        })),
    [lands]
  );

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString()
    : "Not available";

  const accountFields = [
    { label: "Email", value: user?.email || "—" },
    { label: "Role", value: (user?.role || "viewer"), capitalize: true },
    { label: "Member Since", value: memberSince },
    { label: "Tracking", value: "Per land setting" },
  ];

  return (
    <div className={`anim-fade-in profile-page${isMobileLayout ? " profile-page--mobile" : ""}`}>
      <div className="page-header">
        <h1 className="page-header__title">My Profile</h1>
        <p className="page-header__subtitle">
          Review your account and the land records connected to it.
        </p>
      </div>

      {/* Mobile compact hero */}
      {isMobileLayout && (
        <div className="profile-hero anim-stagger" style={{ "--stagger-index": 0 }}>
          <div className="profile-avatar">{initials}</div>
          <div className="profile-hero__body">
            <div className="profile-name">{displayName}</div>
            <div className="profile-email">{user?.email || "—"}</div>
            <span className="badge badge--healthy profile-role-badge">
              {user?.role || "viewer"}
            </span>
          </div>
        </div>
      )}

      {isMobileLayout && (
        <div className="anim-stagger" style={{ "--stagger-index": 0.5 }}>
          <ProfileStats
            loadingLands={loadingLands}
            landsCount={lands.length}
            totalArea={totalArea}
            activeKeys={activeKeyCount}
            className="profile-stats--mobile"
          />
        </div>
      )}

      <div className="profile-section">
        {/* Desktop sidebar */}
        <div className="profile-sidebar profile-sidebar--desktop-only anim-stagger" style={{ "--stagger-index": 0 }}>
          <div className="profile-avatar">{initials}</div>
          <div className="profile-name">{displayName}</div>
          <div className="profile-email">{user?.email || "—"}</div>
          <span className="badge badge--healthy profile-role-badge">
            {user?.role || "viewer"}
          </span>
          <ProfileStats
            loadingLands={loadingLands}
            landsCount={lands.length}
            totalArea={totalArea}
            activeKeys={activeKeyCount}
          />
        </div>

        <div className="profile-main">
          {/* Account */}
          <section className="anim-stagger" style={{ "--stagger-index": 1 }}>
            <div className="profile-block__header">
              <h2 className="profile-block__title">Account Information</h2>
            </div>
            <div className="profile-info-card">
              {accountFields.map((field) => (
                <div key={field.label} className="profile-info-row">
                  <span className="profile-info-row__label">{field.label}</span>
                  <span
                    className="profile-info-row__value"
                    style={field.capitalize ? { textTransform: "capitalize" } : undefined}
                  >
                    {field.value}
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* Activity */}
          <section className="anim-stagger" style={{ "--stagger-index": 2 }}>
            <div className="profile-block__header">
              <h2 className="profile-block__title">Recent Activity</h2>
            </div>
            <div className="profile-activity-list">
              {recentActivity.length === 0 && (
                <div className="profile-activity-item">
                  <span className="text-body-sm" style={{ color: "var(--text-secondary)" }}>
                    {loadingLands ? "Loading activity…" : "No land activity yet."}
                  </span>
                </div>
              )}
              {recentActivity.map((item) => (
                <div key={`${item.action}-${item.time}`} className="profile-activity-item">
                  <span className={`profile-activity-item__dot profile-activity-item__dot--${item.type}`} />
                  <div className="profile-activity-item__body">
                    <span className="profile-activity-item__text">{item.action}</span>
                    <span className="profile-activity-item__time">{item.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* AI API Keys */}
          <section className="anim-stagger" style={{ "--stagger-index": 3 }}>
            <div className="profile-block__header profile-block__header--keys">
              <div className="profile-block__title-row">
                <h2 className="profile-block__title">AI API Keys</h2>
                <span className="profile-groq-badge">✨ Groq</span>
              </div>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={() => setShowAddForm(!showAddForm)}
              >
                {showAddForm ? "Cancel" : "+ Add Key"}
              </button>
            </div>

            {keyError && <div className="profile-alert profile-alert--error">{keyError}</div>}
            {keySuccess && <div className="profile-alert profile-alert--success">{keySuccess}</div>}

            {showAddForm && (
              <div className="profile-key-form">
                <div className="form-group">
                  <label className="form-label">Key Label (optional)</label>
                  <input
                    className="form-control"
                    placeholder='e.g. "Primary Key"'
                    value={newKeyLabel}
                    onChange={(e) => setNewKeyLabel(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">
                    Groq API Key <span style={{ color: "var(--error)" }}>*</span>
                  </label>
                  <input
                    className="form-control"
                    placeholder="gsk_..."
                    type="password"
                    value={newKey}
                    onChange={(e) => setNewKey(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleAddKey()}
                    autoComplete="off"
                  />
                  <span className="text-caption" style={{ marginTop: 4, display: "block" }}>
                    Get your key at{" "}
                    <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer" style={{ color: "#f97316" }}>
                      console.groq.com
                    </a>
                    . Keys are stored securely.
                  </span>
                </div>
                <div className="profile-key-form__actions">
                  <button type="button" className="btn btn--ghost btn--sm" onClick={() => setShowAddForm(false)}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn--primary btn--sm"
                    onClick={handleAddKey}
                    disabled={addingKey || !newKey.trim()}
                  >
                    {addingKey ? "Saving…" : "Save Key"}
                  </button>
                </div>
              </div>
            )}

            <div className="profile-keys-list">
              {apiKeys.length === 0 && !showAddForm && (
                <div className="profile-keys-empty">
                  <div className="profile-keys-empty__icon">🔑</div>
                  <div className="text-body-sm" style={{ fontWeight: 600 }}>No API keys yet</div>
                  <div className="text-caption" style={{ marginTop: 4 }}>
                    Add a Groq API key to enable AI crop analysis and chat.
                  </div>
                </div>
              )}
              {apiKeys.map((key) => (
                <ApiKeyCard
                  key={key.key_id}
                  keyItem={key}
                  onToggle={handleToggleKey}
                  onDelete={handleDeleteKey}
                />
              ))}
            </div>

            {apiKeys.length > 0 && (
              <div className="profile-keys-hint">
                <div className="profile-keys-hint__title">✨ How key rotation works</div>
                <div className="profile-keys-hint__body">
                  Keys are tried in order. If one hits its quota, the system skips it and tries the next.
                  Quota-exceeded keys re-enable automatically after 1 hour.
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}