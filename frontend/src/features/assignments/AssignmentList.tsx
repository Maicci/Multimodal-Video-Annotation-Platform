import { useEffect, useState } from "react";
import type { Assignment, AnnotationStatus } from "../../types/assignment";
import "../../assets/css/AssignmentList.css";

const API_URL = import.meta.env.VITE_API_URL || "";

const STATUS_LABEL: Record<AnnotationStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
  submitted: "Submitted",
  returned: "Returned for changes",
  approved: "Approved",
  skipped: "Skipped",
};
const ACTION_LABEL: Record<AnnotationStatus, string> = {
  not_started: "Start",
  in_progress: "Continue",
  completed: "Review",
  submitted: "View",
  returned: "Revise",
  approved: "View",
  skipped: "Resume",
};
const GROUPS = [
  { key: "shared", title: "Shared set", note: "Everyone annotates these independently." },
  { key: "individual", title: "Your set", note: "Assigned to you only." },
] as const;

function formatDuration(s: number | null): string {
  if (s == null) return "–";
  return `${Math.floor(s / 60)}:${Math.round(s % 60).toString().padStart(2, "0")}`;
}

interface Props {
  token: string;
  onOpenVideo: (videoId: string) => void;
}

function Row({ a, onOpenVideo }: { a: Assignment; onOpenVideo: (id: string) => void }) {
  return (
    <li className="row">
      <span className="row-name">
        {a.title}
        <small>{a.original_filename}</small>
      </span>
      <span className="row-meta">{formatDuration(a.duration_seconds)}</span>
      <span className="row-meta">
        {a.segment_count} {a.segment_count === 1 ? "segment" : "segments"}
      </span>
      <span className={`status status-${a.status}`}>
        <i aria-hidden="true" />
        {STATUS_LABEL[a.status]}
      </span>
      <button type="button" className="row-action" onClick={() => onOpenVideo(a.video_id)}>
        {ACTION_LABEL[a.status]}
      </button>
    </li>
  );
}

export default function AssignmentList({ token, onOpenVideo }: Props) {
  const [data, setData] = useState<Assignment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchMyAssignments(token, ctrl.signal)
      .then(setData)
      .catch((e: Error) => e.name !== "AbortError" && setError(e.message));
    return () => ctrl.abort();
  }, [token]);

  if (error)
    return (
      <p role="alert" className="notice">
        Couldn't load your videos ({error}). Refresh the page, or contact an administrator if it persists.
      </p>
    );
  if (!data) return <p className="notice">Loading your videos…</p>;

  const done = data.filter((a) => ["completed", "submitted", "approved"].includes(a.status)).length;

  async function fetchMyAssignments(token: string, signal?: AbortSignal): Promise<Assignment[]> {
    const res = await fetch(`${API_URL}/api/me/assignments`, {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    return res.json();
  }
  
  return (
    <div className="home">
      <header className="home-head">
        <h1>Your videos</h1>
        <p>{data.length === 0 ? "Nothing is assigned to you yet." : `${done} of ${data.length} completed`}</p>
      </header>

      {data.length === 0 && <p className="notice">Ask an administrator to assign videos to your account.</p>}

      {GROUPS.map(({ key, title, note }) => {
        const items = data.filter((a) => a.protocol_group === key);
        if (items.length === 0) return null;
        return (
          <section key={key} className="group" aria-labelledby={`g-${key}`}>
            <h2 id={`g-${key}`}>{title}</h2>
            <p className="group-note">{note}</p>
            <ul className="list">
              {items.map((a) => (
                <Row key={a.video_id} a={a} onOpenVideo={onOpenVideo} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
