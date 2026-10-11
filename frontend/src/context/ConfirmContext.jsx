/**
 * context/ConfirmContext.jsx
 * Mobile-friendly confirm dialogs — replaces window.confirm().
 */

import { createContext, useCallback, useContext, useState } from "react";

const ConfirmContext = createContext(null);

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null);

  const confirm = useCallback(({ title = "Confirm", message, confirmLabel = "Confirm", cancelLabel = "Cancel", variant = "danger" }) => {
    return new Promise((resolve) => {
      setState({ title, message, confirmLabel, cancelLabel, variant, resolve });
    });
  }, []);

  const handleClose = (result) => {
    state?.resolve(result);
    setState(null);
  };

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {state && (
        <div
          className="confirm-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
          onClick={() => handleClose(false)}
        >
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h2 id="confirm-title" className="confirm-dialog__title">{state.title}</h2>
            <p className="confirm-dialog__message">{state.message}</p>
            <div className="confirm-dialog__actions">
              <button className="btn btn--secondary" onClick={() => handleClose(false)}>
                {state.cancelLabel}
              </button>
              <button
                className={`btn ${state.variant === "danger" ? "btn--danger" : "btn--primary"}`}
                onClick={() => handleClose(true)}
              >
                {state.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within ConfirmProvider");
  return ctx.confirm;
}