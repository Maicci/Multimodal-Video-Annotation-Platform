import { useEffect, useRef, useState } from "react";
import "../../assets/css/VideoViewer.css";
import FrameTimeline from "./FrameTimelines";

type Props = { videoId: string; onDirtyChange: (dirty: boolean) => void };

type SegmentInput = {
  start_frame?: number;
  end_frame?: number;
  version?: number;
  title: string;
  start_time: number;
  end_time: number;
  description: string;
  audio_description: string;
};

type Segment = SegmentInput & { id: string; video_id: string; author_id: string };

const API_URL = import.meta.env.VITE_API_URL || "";

function VideoViewer({ videoId, onDirtyChange }: Props) {
  const frameRequest = useRef(0);
  const resumePlayback = useRef(false);
  const playbackPosition = useRef(0);
  const [waveform, setWaveform] = useState<{ duration: number; status: string; peaks: number[] } | null>(null);
  const [waveformError, setWaveformError] = useState("");
  const [boundaries, setBoundaries] = useState<number[]>([]);
  const [mediaToken, setMediaToken] = useState("");
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
  const [sessionStatus, setSessionStatus] = useState("unassigned");
  const [completionMessage, setCompletionMessage] = useState("");
  const [dirty, setDirty] = useState(false);
  const [savedSummary, setSavedSummary] = useState("");
  const [summaryVersion, setSummaryVersion] = useState(0);
  const [summary, setSummary] = useState("");
  const [summaryStatus, setSummaryStatus] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summarySaving, setSummarySaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [segmentsLoading, setSegmentsLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const hasChanges = dirty || summary !== savedSummary;
    onDirtyChange(hasChanges);
    const warn = (event: BeforeUnloadEvent) => {
      if (hasChanges) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, summary, savedSummary, onDirtyChange]);

  function nearestFrame(time: number) {
    return boundaries.reduce((best, value, index) => Math.abs(value - time) < Math.abs(boundaries[best] - time) ? index : best, 0);
  }

  function updateDraft(patch: Partial<SegmentInput>) {
    if (boundaries.length) {
      if (patch.start_time !== undefined) { patch.start_frame = nearestFrame(patch.start_time); patch.start_time = boundaries[patch.start_frame]; }
      if (patch.end_time !== undefined) { patch.end_frame = nearestFrame(patch.end_time); patch.end_time = boundaries[patch.end_frame]; }
    }
    setDraft((current) => ({ ...current, ...patch }));
    setDirty(true);
    setMessage("Unsaved changes");
  }

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
      }).finally(() => { if (!controller.signal.aborted) setSegmentsLoading(false); });
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
        return response.json() as Promise<{ summary: string; version: number }>;
      })
      .then((data) => { setSummary(data.summary); setSavedSummary(data.summary); setSummaryVersion(data.version); })
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

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/api/videos/${videoId}/timeline`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }, signal: controller.signal,
    }).then(async (response) => { if (response.ok) setBoundaries((await response.json()).boundaries); }).catch(() => {});
    fetch(`${API_URL}/api/videos/${videoId}/waveform`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }, signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) throw new Error("Waveform could not be loaded.");
      setWaveform(await response.json());
    }).catch((cause) => { if (!controller.signal.aborted) setWaveformError(cause.message); });
    async function refreshPlaybackToken() {
      try {
        const response = await fetch(`${API_URL}/api/videos/${videoId}/media-token`, {
          method: "POST",
          headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("You cannot access this video. Sign in again or check your assignment.");
        const data = await response.json();
        resumePlayback.current = Boolean(videoRef.current && !videoRef.current.paused);
        setMediaToken(data.token);
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Cannot load video.");
      }
    }
    void refreshPlaybackToken();
    const timer = window.setInterval(() => void refreshPlaybackToken(), 240000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [videoId]);

  async function handleTimeUpdate() {
    if (!videoRef.current || videoRef.current.readyState < 1) return;
    const time = videoRef.current.currentTime;
    setCurrentTime(time);
    playbackPosition.current = time;
    const requestId = ++frameRequest.current;
    try {
      const response = await fetch(`${API_URL}/api/videos/${videoId}/frame?time=${time}`, { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } });
      if (response.ok) {
        const data: { frame: number } = await response.json();
        if (requestId === frameRequest.current) setCurrentFrame(data.frame);
      }
    } catch {
      // Playback remains usable if frame timing is unavailable.
    }
  }

  function handleTimelineChange(time: number) {
    if (!videoRef.current) return;
    videoRef.current.currentTime = time;
    setCurrentTime(time);
    playbackPosition.current = time;
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

  function newSegment(discardConfirmed = false) {
    if (dirty && !discardConfirmed && !window.confirm("Discard unsaved segment changes?")) return;
    setDirty(false);
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

  function selectSegment(segment: Segment, discardConfirmed = false) {
    if (dirty && !discardConfirmed && !window.confirm("Discard unsaved segment changes?")) return;
    setDirty(false);
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
      setDirty(false);
      if (sessionStatus !== "unassigned") setSessionStatus("in_progress");
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
        `${API_URL}/api/videos/${videoId}/segments/${selectedId}?version=${draft.version || 1}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } },
      );
      if (!response.ok) throw new Error(response.status === 409 ? "This segment changed in another session. Reload before deleting." : `Could not delete segment (${response.status}).`);
      setDirty(false);
      if (sessionStatus !== "unassigned") setSessionStatus("in_progress");
      const remaining = segments.filter((item) => item.id !== selectedId);
      setSegments(remaining);
      if (remaining.length > 0) {
        selectSegment(remaining[0], true);
      } else {
        newSegment(true);
      }
      setMessage("Segment deleted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete segment.");
    } finally {
      setDeleting(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/api/videos/${videoId}/annotation-session`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }, signal: controller.signal,
    }).then(async (response) => { if (response.ok) setSessionStatus((await response.json()).status); }).catch(() => {});
    return () => controller.abort();
  }, [videoId]);

  async function completeAnnotation() {
    try {
      const response = await fetch(`${API_URL}/api/videos/${videoId}/annotation-session/complete`, {
        method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not complete annotation.");
      setSessionStatus("completed");
      setCompletionMessage("Annotation completed.");
    } catch (cause) { setCompletionMessage(cause instanceof Error ? cause.message : "Could not complete annotation."); }
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
        body: JSON.stringify({ summary, version: summaryVersion }),
      });
      if (!response.ok) throw new Error(response.status === 409
        ? "This summary changed in another session. Copy your text before reloading."
        : `Could not save summary (${response.status}).`);
      const saved = await response.json();
      setSummaryVersion(saved.version);
      setSavedSummary(saved.summary);
      if (sessionStatus !== "unassigned") setSessionStatus("in_progress");
      setSummaryStatus("Summary saved.");
    } catch (cause) {
      setSummaryStatus(cause instanceof Error ? cause.message : "Could not save summary.");
    } finally {
      setSummarySaving(false);
    }
  }

  // One gain for the whole clip keeps relative loudness intact. Limit the gain
  // so near-silent noise does not become a full-height waveform.
  const waveformMaximum = waveform?.peaks.reduce((maximum, peak) => Math.max(maximum, peak), 0) || 0;
  const waveformGain = waveformMaximum > 0 ? Math.min(50, 1 / waveformMaximum) : 1;

  return (
    <section className="annotation-workspace">
      <div className="top-row">
        <div className="video-panel">
          <video
            ref={videoRef}
            className="video-player"
            onTimeUpdate={handleTimeUpdate}
            src={mediaToken ? `${API_URL}/api/videos/${videoId}/stream?media_token=${encodeURIComponent(mediaToken)}` : undefined}
            onLoadedMetadata={() => {
              setDuration(videoRef.current?.duration || 0);
              if (videoRef.current) {
                videoRef.current.currentTime = playbackPosition.current;
                if (resumePlayback.current) void videoRef.current.play();
              }
            }}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
          >

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
            <button type="button" onClick={() => newSegment()} disabled={segmentsLoading || duration <= 0 || saving || deleting}>+ New segment</button>
          </div>
          {segments.length === 0 && <p>No saved segments yet.</p>}
          {segments.map((segment) => (
            <button
              key={segment.id}
              type="button"
              className={`segment-item ${selectedId === segment.id ? "active" : ""}`}
              disabled={saving || deleting}
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
        mediaToken={mediaToken}
        currentTime={currentTime}
        duration={duration}
        onTimeChange={handleTimelineChange}
        selection={draft.end_time > draft.start_time
          ? { start: draft.start_time, end: draft.end_time }
          : null}
        onSelectionChange={(start_time, end_time) => {
          if (!saving && !deleting) updateDraft({ start_time, end_time });
        }}
      />
      <section aria-label="Audio waveform">
        <h2>Audio waveform</h2>
        {waveformError && <p role="alert">{waveformError}</p>}
        {!waveform && !waveformError && <p>Loading waveform…</p>}
        {waveform?.status === "no_audio" && <p>This video has no audio track.</p>}
        {waveform && waveform.peaks.length > 0 && <>
          <svg viewBox="0 0 1000 100" preserveAspectRatio="none" width="100%" height="120" role="img" aria-label="Waveform with segment selection and playback position"
            style={{ touchAction: "none", cursor: "ew-resize" }}
            onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); const box = event.currentTarget.getBoundingClientRect(); handleTimelineChange(Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)) * waveform.duration); }}
            onPointerMove={(event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) { const box = event.currentTarget.getBoundingClientRect(); handleTimelineChange(Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)) * waveform.duration); } }}
            onPointerUp={(event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}>
            <rect width="1000" height="100" fill="#222733" />
            <rect x={draft.start_time / waveform.duration * 1000} width={Math.max(0, (draft.end_time - draft.start_time) / waveform.duration * 1000)} height="100" fill="#345b91" />
            <line x1="0" x2="1000" y1="50" y2="50" stroke="#617386" vectorEffect="non-scaling-stroke" />
            <path d={waveform.peaks.map((peak, i) => {
              const amplitude = Math.min(1, peak * waveformGain) * 44;
              return `M${(i + 0.5) / waveform.peaks.length * 1000},${50 - amplitude}v${amplitude * 2}`;
            }).join(" ")} stroke="#a8d8ff" vectorEffect="non-scaling-stroke" />
            <line x1={currentTime / waveform.duration * 1000} x2={currentTime / waveform.duration * 1000} y1="0" y2="100" stroke="white" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          </svg>
          <small>Waveform height is scaled for visibility. Audio volume is unchanged.</small>
          <label>Seek audio waveform<input type="range" min="0" max={waveform.duration} step="0.01" value={currentTime} onChange={(event) => handleTimelineChange(Number(event.target.value))} /></label>
        </>}
      </section>
      <p className="timeline-hint">Drag the blue start bar or orange end bar to set the segment range.</p>

      <section className="annotation-details">
        <h2>{selectedId ? "Edit segment" : "New segment"}</h2>
        <fieldset className="annotation-fields" disabled={segmentsLoading || saving || deleting}>
          <label>Title
            <input
              value={draft.title}
              maxLength={120}
              onChange={(event) => updateDraft({ title: event.target.value })}
              placeholder="What happens in this segment?"
            />
          </label>
          <div className="time-row">
            <label>Start (seconds)
              <input type="number" min="0" max={duration} step="0.01" value={draft.start_time}
                onChange={(event) => updateDraft({ start_time: Number(event.target.value) })} />
            </label>
            <label>End (seconds)
              <input type="number" min="0" max={duration} step="0.01" value={draft.end_time}
                onChange={(event) => updateDraft({ end_time: Number(event.target.value) })} />
            </label>
          </div>
          {boundaries.length > 0 && <div className="time-row">
            <label>Start frame (inclusive)
              <input type="number" min="0" max={boundaries.length - 2} value={nearestFrame(draft.start_time)}
                onChange={(event) => { const frame = Number(event.target.value); if (Number.isInteger(frame) && frame >= 0 && frame < boundaries.length - 1) updateDraft({ start_time: boundaries[frame] }); }} />
            </label>
            <label>End frame (exclusive)
              <input type="number" min="1" max={boundaries.length - 1} value={nearestFrame(draft.end_time)}
                onChange={(event) => { const frame = Number(event.target.value); if (Number.isInteger(frame) && frame > 0 && frame < boundaries.length) updateDraft({ end_time: boundaries[frame] }); }} />
            </label>
          </div>}
          <label>Video description
            <textarea value={draft.description} maxLength={10000}
              onChange={(event) => updateDraft({ description: event.target.value })}
              placeholder="Describe what is visible in the segment." />
          </label>
          <label>Audio description
            <textarea value={draft.audio_description} maxLength={10000}
              onChange={(event) => updateDraft({ audio_description: event.target.value })}
              placeholder="Describe speech, sounds, and other audio in the segment." />
          </label>
        </fieldset>
        {error && <p role="alert">{error}</p>}
        {message && <p role="status">{message}</p>}
        <div className="segment-actions">
          <button type="button" onClick={saveSegment} disabled={segmentsLoading || saving || deleting || duration <= 0}>
            {saving ? "Saving…" : "Save segment"}
          </button>
          {selectedId && (
            <button type="button" onClick={deleteSelectedSegment} disabled={segmentsLoading || saving || deleting}>
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
      {sessionStatus !== "unassigned" && <section>
        <p>Annotation: {sessionStatus.replaceAll("_", " ")}</p>
        <button type="button" disabled={dirty || summary !== savedSummary || saving || summarySaving || sessionStatus === "completed"} onClick={completeAnnotation}>Mark complete</button>
        {completionMessage && <p role="status">{completionMessage}</p>}
      </section>}
    </section>
  );
}

export default VideoViewer;
