import { useEffect, useRef, useState } from "react";
import "../../assets/css/VideoViewer.css";
import FrameTimeline from "./FrameTimelines";

type Props = { videoId: string };

type SegmentInput = {
  title: string;
  start_time: number;
  end_time: number;
  description: string;
  audio_description: string;
};

type Segment = SegmentInput & { id: string; video_id: string; author_id: string };

const API_URL = import.meta.env.VITE_API_URL || "";

function VideoViewer({ videoId }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<SegmentInput>({
    title: "", start_time: 0, end_time: 0, description: "", audio_description: "",
  });
  const [summary, setSummary] = useState("");
  const [summaryStatus, setSummaryStatus] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summarySaving, setSummarySaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const token = localStorage.getItem("access_token");
    if (!token) return;
    fetch(`${API_URL}/api/videos/${videoId}/segments`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load segments (${response.status}).`);
        return response.json() as Promise<Segment[]>;
      })
      .then((items) => {
        setSegments(items);
        if (items.length > 0) {
          setSelectedId(items[0].id);
          setDraft(items[0]);
        }
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Could not load segments.");
        }
      });
    return () => controller.abort();
  }, [videoId]);

  useEffect(() => {
    const controller = new AbortController();
    const token = localStorage.getItem("access_token");
    if (!token) {
      setSummaryLoading(false);
      setSummaryStatus("Sign in to load the summary.");
      return;
    }
    setSummaryLoading(true);
    setSummary("");
    setSummaryStatus("");
    fetch(`${API_URL}/api/videos/${videoId}/summary`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load summary (${response.status}).`);
        return response.json() as Promise<{ summary: string }>;
      })
      .then((data) => setSummary(data.summary))
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setSummaryStatus(cause instanceof Error ? cause.message : "Could not load summary.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setSummaryLoading(false);
      });
    return () => controller.abort();
  }, [videoId]);

  async function handleTimeUpdate() {
    if (!videoRef.current) return;
    const time = videoRef.current.currentTime;
    setCurrentTime(time);
    try {
      const response = await fetch(`${API_URL}/api/videos/${videoId}/frame?time=${time}`);
      if (response.ok) {
        const data: { frame: number } = await response.json();
        setCurrentFrame(data.frame);
      }
    } catch {
      // Playback remains usable if frame timing is unavailable.
    }
  }

  function handleTimelineChange(time: number) {
    if (!videoRef.current) return;
    videoRef.current.currentTime = time;
    setCurrentTime(time);
  }

  function togglePlayback() {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      void videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  }

  function newSegment() {
    const start = Math.min(currentTime, Math.max(0, duration - 0.1));
    setSelectedId(null);
    setDraft({
      title: "",
      start_time: Number(start.toFixed(2)),
      end_time: Number(Math.min(duration, start + 5).toFixed(2)),
      description: "",
      audio_description: "",
    });
    setError("");
    setMessage("");
  }

  function selectSegment(segment: Segment) {
    setSelectedId(segment.id);
    setDraft(segment);
    setError("");
    setMessage("");
    handleTimelineChange(segment.start_time);
  }

  async function saveSegment() {
    const payload = { ...draft, title: draft.title.trim() };
    if (!payload.title || payload.start_time < 0 ||
        payload.end_time <= payload.start_time || payload.end_time > duration) {
      setError("Enter a title and a valid time range within the video.");
      return;
    }
    const token = localStorage.getItem("access_token");
    if (!token) {
      setError("Sign in again to save this segment.");
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        `${API_URL}/api/videos/${videoId}/segments${selectedId ? `/${selectedId}` : ""}`,
        {
          method: selectedId ? "PUT" : "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );
      if (!response.ok) {
        const body = await response.json();
        throw new Error(typeof body.detail === "string" ? body.detail : `Save failed (${response.status}).`);
      }
      const saved: Segment = await response.json();
      setSegments((previous) => [...previous.filter((item) => item.id !== saved.id), saved]
        .sort((a, b) => a.start_time - b.start_time));
      setSelectedId(saved.id);
      setDraft(saved);
      setMessage("Segment saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save segment.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteSelectedSegment() {
    if (!selectedId || !window.confirm(`Delete segment "${draft.title}"?`)) return;
    const token = localStorage.getItem("access_token");
    if (!token) {
      setError("Sign in again to delete this segment.");
      return;
    }
    setDeleting(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(
        `${API_URL}/api/videos/${videoId}/segments/${selectedId}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } },
      );
      if (!response.ok) throw new Error(`Could not delete segment (${response.status}).`);
      const remaining = segments.filter((item) => item.id !== selectedId);
      setSegments(remaining);
      if (remaining.length > 0) {
        selectSegment(remaining[0]);
      } else {
        newSegment();
      }
      setMessage("Segment deleted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete segment.");
    } finally {
      setDeleting(false);
    }
  }

  async function saveSummary() {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setSummaryStatus("Sign in again to save the summary.");
      return;
    }
    setSummarySaving(true);
    setSummaryStatus("");
    try {
      const response = await fetch(`${API_URL}/api/videos/${videoId}/summary`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ summary }),
      });
      if (!response.ok) throw new Error(`Could not save summary (${response.status}).`);
      setSummaryStatus("Summary saved.");
    } catch (cause) {
      setSummaryStatus(cause instanceof Error ? cause.message : "Could not save summary.");
    } finally {
      setSummarySaving(false);
    }
  }

  return (
    <section className="annotation-workspace">
      <div className="top-row">
        <div className="video-panel">
          <video
            ref={videoRef}
            className="video-player"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={() => setDuration(videoRef.current?.duration || 0)}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
          >
            <source src={`${API_URL}/api/videos/${videoId}/stream`} type="video/mp4" />
          </video>
          <div className="video-controls">
            <button type="button" onClick={togglePlayback}>{isPlaying ? "Pause" : "Play"}</button>
            <span>{currentTime.toFixed(2)} s</span>
            <span>Frame {currentFrame}</span>
          </div>
        </div>
        <aside className="segments-panel">
          <div className="segments-header">
            <h2>Segments</h2>
            <button type="button" onClick={newSegment} disabled={duration <= 0}>+ New segment</button>
          </div>
          {segments.length === 0 && <p>No saved segments yet.</p>}
          {segments.map((segment) => (
            <button
              key={segment.id}
              type="button"
              className={`segment-item ${selectedId === segment.id ? "active" : ""}`}
              onClick={() => selectSegment(segment)}
            >
              <strong>{segment.start_time.toFixed(2)} – {segment.end_time.toFixed(2)} s</strong>
              <span>{segment.title}</span>
            </button>
          ))}
        </aside>
      </div>

      <FrameTimeline
        videoId={videoId}
        currentTime={currentTime}
        duration={duration}
        onTimeChange={handleTimelineChange}
        selection={draft.end_time > draft.start_time
          ? { start: draft.start_time, end: draft.end_time }
          : null}
        onSelectionChange={(start_time, end_time) => {
          setDraft((current) => ({ ...current, start_time, end_time }));
          setMessage("");
        }}
      />
      <p className="timeline-hint">Drag the blue start bar or orange end bar to set the segment range.</p>

      <section className="annotation-details">
        <h2>{selectedId ? "Edit segment" : "New segment"}</h2>
        <div className="annotation-fields">
          <label>Title
            <input
              value={draft.title}
              maxLength={120}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
              placeholder="What happens in this segment?"
            />
          </label>
          <div className="time-row">
            <label>Start (seconds)
              <input type="number" min="0" max={duration} step="0.01" value={draft.start_time}
                onChange={(event) => setDraft({ ...draft, start_time: Number(event.target.value) })} />
            </label>
            <label>End (seconds)
              <input type="number" min="0" max={duration} step="0.01" value={draft.end_time}
                onChange={(event) => setDraft({ ...draft, end_time: Number(event.target.value) })} />
            </label>
          </div>
          <label>Video description
            <textarea value={draft.description} maxLength={10000}
              onChange={(event) => setDraft({ ...draft, description: event.target.value })}
              placeholder="Describe what is visible in the segment." />
          </label>
          <label>Audio description
            <textarea value={draft.audio_description} maxLength={10000}
              onChange={(event) => setDraft({ ...draft, audio_description: event.target.value })}
              placeholder="Describe speech, sounds, and other audio in the segment." />
          </label>
        </div>
        {error && <p role="alert">{error}</p>}
        {message && <p role="status">{message}</p>}
        <div className="segment-actions">
          <button type="button" onClick={saveSegment} disabled={saving || deleting || duration <= 0}>
            {saving ? "Saving…" : "Save segment"}
          </button>
          {selectedId && (
            <button type="button" onClick={deleteSelectedSegment} disabled={saving || deleting}>
              {deleting ? "Deleting…" : "Delete segment"}
            </button>
          )}
        </div>
      </section>
      <section className="annotation-details">
        <h2>Whole-video summary</h2>
        <label>Video summary
          <textarea value={summary} maxLength={20000} disabled={summaryLoading || summarySaving}
            onChange={(event) => {
              setSummary(event.target.value);
              setSummaryStatus("Unsaved changes");
            }}
            placeholder="Summarize the video as a whole." />
        </label>
        {summaryStatus && <p role="status">{summaryStatus}</p>}
        <button type="button" onClick={saveSummary} disabled={summaryLoading || summarySaving}>
          {summaryLoading ? "Loading…" : summarySaving ? "Saving…" : "Save summary"}
        </button>
      </section>
    </section>
  );
}

export default VideoViewer;
