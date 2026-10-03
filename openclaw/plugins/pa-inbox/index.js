import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

const INBOX_URL = "http://127.0.0.1:8787/api/inbox";
const mediaByKey = new Map();

const OVERFLOW =
  /context compaction|auto-compaction could not recover|use \/compact|context limit exceeded/i;

function mediaKind(fact) {
  const kind = String(fact?.kind || "").toLowerCase();
  const type = String(fact?.contentType || "").toLowerCase();
  if (kind.includes("audio") || kind === "voice" || kind === "ptt" || type.startsWith("audio/")) {
    return "audio";
  }
  if (kind.includes("image") || type.startsWith("image/")) return "image";
  return kind || (type.split("/")[0] || null);
}

function pickMedia(event) {
  const items = [...(event.media || []), ...(event.originalMedia || [])];
  if (!items.length) return null;
  return (
    items.find((item) => mediaKind(item) === "audio") ||
    items.find((item) => item?.path) ||
    items[0]
  );
}

function rememberMedia(event) {
  const media = pickMedia(event);
  if (!media?.path) return;
  for (const key of [event.messageId, event.sessionKey, event.senderId]) {
    if (key) mediaByKey.set(String(key), media);
  }
}

function lookupMedia(event, ctx) {
  for (const key of [event.messageId, ctx.messageId, event.sessionKey, ctx.sessionKey, event.senderId, ctx.senderId]) {
    if (key && mediaByKey.has(String(key))) return mediaByKey.get(String(key));
  }
  return null;
}

function stripMediaPlaceholders(text) {
  return String(text || "")
    .replace(/<media:[^>]+>/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function postInbox({ text, media, sender }) {
  const body = {
    text: text || "",
    source: "whatsapp",
    sender: sender || null,
    deliver_reply: false,
  };
  if (media?.path) {
    body.media_path = media.path;
    body.media_kind = mediaKind(media) || "audio";
  }
  const response = await fetch(INBOX_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(120000),
  });
  if (!response.ok) {
    throw new Error(`inbox ${response.status}`);
  }
  return response.json();
}

export default definePluginEntry({
  id: "pa-inbox",
  name: "Personal Assistant Inbox",
  description: "Send WhatsApp messages to the local FastAPI inbox instead of overflowing the 8k Qwen session.",
  register(api) {
    api.on("message_received", (event) => {
      rememberMedia(event);
    });

    api.on("before_dispatch", async (event, ctx) => {
      const raw = event.body || event.content || "";
      if (/^\s*\//.test(raw) && !OVERFLOW.test(raw)) return;
      const channel = String(event.channel || ctx.channelId || "").toLowerCase();
      if (channel && channel !== "whatsapp") return;

      rememberMedia(event);
      const media = lookupMedia(event, ctx);
      const text = stripMediaPlaceholders(raw);
      try {
        const result = await postInbox({
          text,
          media,
          sender: event.senderId || ctx.senderId,
        });
        const reply =
          (result && result.reply) ||
          (media ? "Message received. Working on that recording now." : "Message received.");
        return { handled: true, text: String(reply).slice(0, 3500) };
      } catch {
        return {
          handled: true,
          text: "Got it. The local assistant is busy — try again in a moment, or press Start on http://127.0.0.1:8787",
        };
      }
    });

    api.on("message_sending", (event) => {
      if (OVERFLOW.test(event.content || "")) {
        return {
          content:
            "Message received. I'm processing that locally (notes/transcription) instead of stuffing it into the chat model.",
        };
      }
    });
  },
});
