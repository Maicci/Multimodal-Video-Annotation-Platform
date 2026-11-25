import { useEffect, useRef, useState } from "react";
import ReviewHistory, { type ReviewEvent } from "../features/videos/ReviewHistory";
import "../assets/css/ReviewPage.css";

const API_URL = import.meta.env.VITE_API_URL || "";
const authHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("access_token")}` });
type Item = { id: string; video_id: string; author_name: string; filename: string; status: string; workflow_version: number };
type Detail = Item & {
  summary: string; submitted_at: string; can_review: boolean; review_history: ReviewEvent[];
  segments: { id: string; title: string; description: string; audio_description: string; start_time: number; end_time: number; start_frame: number; end_frame: number }[];
};

function SubmittedWork({ id, onBack }: { id: string; onBack: () => void }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [mediaToken, setMediaToken] = useState("");
  const [mediaError, setMediaError] = useState("");
  const player = useRef<HTMLVideoElement>(null);
  const restore = useRef({ time: 0, playing: false });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/api/reviews/${id}`, { headers: authHeaders(), signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load submitted work (${response.status}).`);
        return response.json();
      }).then((data) => { if (!controller.signal.aborted) { setDetail(data); setError(""); } })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [id, reload]);

  const videoId = detail?.video_id;
  useEffect(() => {
    if (!videoId) return;
    const controller = new AbortController();
    async function refresh() {
      try {
        const response = await fetch(`${API_URL}/api/videos/${videoId}/media-token`, { method: "POST", headers: authHeaders(), signal: controller.signal });
        if (!response.ok) throw new Error("Could not load the video preview.");
        const data = await response.json();
        if (controller.signal.aborted) return;
        if (player.current && player.current.readyState >= 1) restore.current = { time: player.current.currentTime, playing: !player.current.paused };
        setMediaToken(data.token);
        setMediaError("");
      } catch (cause) { if (!controller.signal.aborted) setMediaError(cause instanceof Error ? cause.message : "Could not load preview."); }
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 240000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [videoId]);

  async function decide(action: "approve" | "return") {
    if (!detail || busy) return;
    if (action === "return" && !comment.trim()) { setError("Add a comment explaining what needs changing."); return; }
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/reviews/${id}/${action}`, {
        method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ expected_version: detail.workflow_version, comment }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not save review.");
      setDetail({ ...detail, ...data, can_review: false });
      setComment("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save review."); }
    finally { setBusy(false); }
  }

  return <section className="submitted-work">
    <button type="button" disabled={busy} onClick={onBack}>Back to review queue</button>
    {error && <div role="alert"><p>{error}</p><button type="button" disabled={busy} onClick={() => setReload((value) => value + 1)}>Refresh review</button></div>}
    {!detail && !error && <p role="status">Loading submitted work…</p>}
    {detail && <>
      <h1>Review annotation</h1>
      <p>{detail.filename} · {detail.author_name}</p>
      <p role="status">Review status: {detail.status}</p>
      <p>Submitted {new Date(detail.submitted_at).toLocaleString()}. This saved revision is read-only.</p>
      <video controls preload="metadata" ref={player} aria-label="Review video preview"
        src={mediaToken ? `${API_URL}/api/videos/${detail.video_id}/stream?media_token=${encodeURIComponent(mediaToken)}` : undefined}
        onError={() => setMediaError("The video preview could not be played.")}
        onLoadedMetadata={() => { if (player.current) { player.current.currentTime = restore.current.time; if (restore.current.playing) void player.current.play().catch(() => {}); } }} />
      {mediaError && <p role="alert">{mediaError}</p>}
      <section aria-label="Submitted segments"><h2>Submitted segments</h2>
        {detail.segments.map((segment) => <article className="review-segment" key={segment.id}>
          <h3>{segment.title}</h3>
          <button type="button" disabled={!mediaToken} onClick={() => {
            restore.current = { time: segment.start_time, playing: true };
            if (player.current && player.current.readyState >= 1) { player.current.currentTime = segment.start_time; void player.current.play().catch(() => setMediaError("Use the video Play control to start playback.")); }
          }}>Play from {segment.start_time.toFixed(2)} s</button>
          <p>{segment.start_time.toFixed(3)}–{segment.end_time.toFixed(3)} s · Frames {segment.start_frame}–{segment.end_frame} (end exclusive)</p>
          <h4>Video description</h4><p>{segment.description}</p>
          <h4>Audio description</h4><p>{segment.audio_description}</p>
        </article>)}
      </section>
      <section aria-label="Submitted summary"><h2>Whole-video summary</h2><p>{detail.summary}</p></section>
      {detail.can_review && <section aria-label="Review decision">
        <h2>Review decision</h2>
        <label>Review comment<textarea maxLength={10000} value={comment} disabled={busy} onChange={(event) => setComment(event.target.value)} /></label>
        <p>A comment is required when returning work for changes.</p>
        <div className="review-actions">
          <button type="button" disabled={busy} onClick={() => void decide("approve")}>Approve annotation</button>
          <button type="button" disabled={busy} onClick={() => void decide("return")}>Return for changes</button>
        </div>
      </section>}
      <ReviewHistory events={detail.review_history} />
    </>}
  </section>;
}

export default function ReviewPage({ onSignOut, onBack }: { onSignOut: () => void; onBack?: () => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (selected) return;
    const controller = new AbortController();
    setLoading(true);
    fetch(`${API_URL}/api/reviews`, { headers: authHeaders(), signal: controller.signal })
      .then(async (response) => { if (!response.ok) throw new Error(`Could not load reviews (${response.status}).`); return response.json(); })
      .then((data) => { if (!controller.signal.aborted) { setItems(data); setError(""); } })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [selected, reload]);
  return <main className="review-page">
    <nav aria-label="Reviewer navigation">{onBack && <button type="button" onClick={onBack}>Back to administration</button>}<button type="button" onClick={onSignOut}>Sign out</button></nav>
    {selected ? <SubmittedWork key={selected} id={selected} onBack={() => setSelected(null)} /> : <>
      <h1>Annotation reviews</h1>
      <p>Inspect submitted work, approve it, or return it with feedback.</p>
      <button type="button" onClick={() => setReload((value) => value + 1)}>Refresh queue</button>
      {loading && <p role="status">Loading review queue…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && items.length === 0 && <p>No submitted annotations yet.</p>}
      {!loading && !error && <ul className="review-queue">{items.map((item) => <li key={item.id}>
        <strong>{item.filename}</strong><span>{item.author_name} · {item.status}</span>
        <button type="button" onClick={() => setSelected(item.id)}>{item.status === "submitted" ? "Review submission" : "View review"}</button>
      </li>)}</ul>}
    </>}
  </main>;
}
