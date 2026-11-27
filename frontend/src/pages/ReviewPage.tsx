import { useEffect, useRef, useState } from "react";
import ReviewHistory, { type ReviewEvent } from "../features/videos/ReviewHistory";
import "../assets/css/ReviewPage.css";

const API_URL = import.meta.env.VITE_API_URL || "";
const authHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("access_token")}` });
type Item = { id: string; video_id: string; author_name: string; filename: string; status: string; workflow_version: number };
type Detail = Item & {
  summary: string; submitted_at: string; submission_version: number; can_review: boolean; review_history: ReviewEvent[];
  segments: { id: string; title: string; description: string; audio_description: string; start_time: number; end_time: number; start_frame: number; end_frame: number }[];
};

function useSubmission(id: string) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

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
  return { detail, setDetail, error, setError, refresh: () => setReload((value) => value + 1) };
}

function Snapshot({ detail, onPlay }: { detail: Detail; onPlay?: (time: number) => void }) {
  return <article className="review-snapshot" aria-label={`Submission by ${detail.author_name}`}>
    <h2>{detail.author_name}</h2>
    <p>Submitted {new Date(detail.submitted_at).toLocaleString()} · Revision {detail.submission_version}</p>
    <section aria-label="Submitted segments"><h3>Submitted segments</h3>
      {detail.segments.map((segment) => <article className="review-segment" key={segment.id}>
        <h4>{segment.title}</h4>
        {onPlay && <button type="button" onClick={() => onPlay(segment.start_time)}>Play from {segment.start_time.toFixed(2)} s</button>}
        <p>{segment.start_time.toFixed(3)}–{segment.end_time.toFixed(3)} s · Frames {segment.start_frame}–{segment.end_frame} (end exclusive)</p>
        <h4>Video description</h4><p>{segment.description}</p>
        <h4>Audio description</h4><p>{segment.audio_description}</p>
      </article>)}
    </section>
    <section aria-label="Submitted summary"><h3>Whole-video summary</h3><p>{detail.summary}</p></section>
  </article>;
}

function ComparisonSnapshot({ id, onPlay }: { id: string; onPlay?: (time: number) => void }) {
  const { detail, error, refresh } = useSubmission(id);
  if (error) return <div role="alert">{error} <button onClick={refresh}>Retry comparison</button></div>;
  if (!detail) return <p role="status">Loading comparison…</p>;
  return <Snapshot detail={detail} onPlay={onPlay} />;
}

function SubmittedWork({ id, peers, onBack }: { id: string; peers: Item[]; onBack: () => void }) {
  const { detail, setDetail, error, setError, refresh } = useSubmission(id);
  const [comparison, setComparison] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [mediaToken, setMediaToken] = useState("");
  const [mediaError, setMediaError] = useState("");
  const player = useRef<HTMLVideoElement>(null);
  const restore = useRef({ time: 0, playing: false });

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

  function playFrom(time: number) {
    restore.current = { time, playing: true };
    if (player.current && player.current.readyState >= 1) {
      player.current.currentTime = time;
      void player.current.play().catch(() => setMediaError("Use the video Play control to start playback."));
    }
  }

  return <section className="submitted-work">
    <button type="button" disabled={busy} onClick={onBack}>Back to review queue</button>
    {error && <div role="alert"><p>{error}</p><button type="button" disabled={busy} onClick={refresh}>Refresh review</button></div>}
    {!detail && !error && <p role="status">Loading submitted work…</p>}
    {detail && <>
      <h1>Review annotation</h1>
      <p>{detail.filename} · {detail.author_name}</p>
      <p role="status">Review status: {detail.status}</p>
      <video controls preload="metadata" ref={player} aria-label="Review video preview"
        src={mediaToken ? `${API_URL}/api/videos/${detail.video_id}/stream?media_token=${encodeURIComponent(mediaToken)}` : undefined}
        onError={() => setMediaError("The video preview could not be played.")}
        onLoadedMetadata={() => { if (player.current) { player.current.currentTime = restore.current.time; if (restore.current.playing) void player.current.play().catch(() => {}); } }} />
      {mediaError && <p role="alert">{mediaError}</p>}
      {peers.length > 0 && <label>Compare with another submission <select value={comparison} onChange={(event) => setComparison(event.target.value)}>
        <option value="">Choose an annotator</option>
        {peers.map((peer) => <option key={peer.id} value={peer.id}>{peer.author_name} · {peer.status}</option>)}
      </select></label>}
      <div className={comparison ? "snapshot-comparison" : undefined}>
        <Snapshot detail={detail} onPlay={mediaToken ? playFrom : undefined} />
        {comparison && <ComparisonSnapshot key={comparison} id={comparison} onPlay={mediaToken ? playFrom : undefined} />}
      </div>
      {detail.can_review && <section aria-label="Review decision">
        <h2>Review decision for {detail.author_name}</h2>
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
  const selectedVideo = items.find((item) => item.id === selected)?.video_id;
  const queueSections = [
    { title: "Awaiting review", rows: items.filter((item) => item.status === "submitted") },
    { title: "Review history", rows: items.filter((item) => item.status !== "submitted") },
  ];

async function exportAnnotation(
  assignmentId: string,
  format: "json" | "csv",
) {
  try {
    const response = await fetch(
      `${API_URL}/api/reviews/${assignmentId}/export/${format}`,
      {
        headers: authHeaders(),
      },
    );

    if (!response.ok) {
      throw new Error(`Could not export annotation (${response.status}).`);
    }

    const blob = await response.blob();

    const contentDisposition = response.headers.get("Content-Disposition");

    const filenameMatch = contentDisposition?.match(/filename="(.+)"/);

    const filename =
      filenameMatch?.[1] ?? `annotation-${assignmentId}.${format}`;

    const url = window.URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    link.remove();

    window.URL.revokeObjectURL(url);
  } catch (cause) {
    setError(
      cause instanceof Error
        ? cause.message
        : "Could not export annotation.",
    );
  }
}

  return <main className="review-page">
    <nav aria-label="Reviewer navigation">{onBack && <button type="button" onClick={onBack}>Back to administration</button>}<button type="button" onClick={onSignOut}>Sign out</button></nav>
    {selected ? <SubmittedWork key={selected} id={selected}
      peers={items.filter((item) => item.id !== selected && item.video_id === selectedVideo)}
      onBack={() => setSelected(null)} /> : <>
      <h1>Annotation reviews</h1>
      <p>Inspect submitted work, approve it, or return it with feedback.</p>
      <button type="button" onClick={() => setReload((value) => value + 1)}>Refresh queue</button>
      {loading && <p role="status">Loading review queue…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && items.length === 0 && <p>No submitted annotations yet.</p>}
      {!loading && !error && items.length > 0 && queueSections.map(({ title, rows }) => (
        <section key={title}><h2>{title} ({rows.length})</h2><ul className="review-queue">
          {rows.map((item) => <li key={item.id}>
  <strong>{item.filename}</strong>

  <span>
    {item.author_name} · {item.status}
  </span>

  <div className="review-queue-actions">
    <button
      type="button"
      onClick={() => setSelected(item.id)}
    >
      {item.status === "submitted"
        ? "Review submission"
        : "View review"}
    </button>

    <button
      type="button"
      onClick={() => void exportAnnotation(item.id, "json")}
    >
      Export JSON
    </button>

    <button
      type="button"
      onClick={() => void exportAnnotation(item.id, "csv")}
    >
      Export CSV
    </button>
  </div>
</li>)}
        </ul></section>
      ))}
    </>}
  </main>;
}
