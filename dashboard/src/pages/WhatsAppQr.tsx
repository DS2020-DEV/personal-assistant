import { useEffect, useState } from "react";
import { api } from "../api";

type Pairing = {
  ok?: boolean;
  linked?: boolean;
  connected?: boolean;
  channelConnected?: boolean;
  active?: boolean;
  qrDataUrl?: string | null;
  message?: string;
  error?: string | null;
};

export default function WhatsAppQr({ autoStart = false }: { autoStart?: boolean }) {
  const [state, setState] = useState<Pairing | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    const next = await api.get("/api/whatsapp/qr");
    setState(next);
    return next as Pairing;
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const current = await refresh();
        if (cancelled) return;
        if (autoStart && !current.linked && !current.qrDataUrl && !current.active) {
          setBusy(true);
          const started = await api.post("/api/whatsapp/qr", { force: false });
          if (!cancelled) setState(started);
        }
      } catch (err) {
        if (!cancelled) setError(String(err).replace(/^Error:\s*/, ""));
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    const id = setInterval(() => {
      refresh().catch(() => {});
    }, 8000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [autoStart]);

  const showQr = async (force: boolean) => {
    setBusy(true);
    setError("");
    try {
      if (!force && (state?.linked || state?.channelConnected)) {
        setState({
          ...state,
          message: "WhatsApp is already linked and connected. Use Relink only if you need a new QR.",
          error: null,
        });
        return;
      }
      const next = await api.post("/api/whatsapp/qr", { force });
      setState(next);
      if (next?.error) setError(next.error);
    } catch (err) {
      setError(String(err).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const linked = Boolean(state?.linked || state?.channelConnected);
  const qr = state?.qrDataUrl;

  return (
    <div className="stack">
      <p className="muted">
        Open WhatsApp on your phone → Linked devices → Link a device, then scan the QR below. It shows here on this page, not in a terminal.
      </p>
      <p>
        Status:{" "}
        <strong>
          {linked ? "Linked" : qr ? "Waiting for scan" : "Not linked"}
        </strong>
        {state?.channelConnected ? " · connected" : ""}
      </p>
      {qr ? (
        <div className="qr-frame">
          <img src={qr} alt="WhatsApp pairing QR code" />
        </div>
      ) : (
        <p className="muted">{state?.message || "Press the button to show a pairing QR."}</p>
      )}
      <div className="row">
        <button type="button" className="btn primary" onClick={() => showQr(false)} disabled={busy || linked}>
          {busy ? "Preparing QR…" : linked ? "Already linked" : "Show pairing QR"}
        </button>
        {linked && (
          <button type="button" className="btn" onClick={() => showQr(true)} disabled={busy}>
            Relink with a new QR
          </button>
        )}
      </div>
      {(error || state?.error) && <p className="error">{error || state?.error}</p>}
    </div>
  );
}
