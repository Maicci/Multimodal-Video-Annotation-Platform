import { useState } from "react";
import TranscriptViewer from "./TranscriptViewer";

export type VideoItem = {
  id: string;
  filename: string;
  size_bytes: number;
  status: string;
  uploaded_at: string;
  duration: number | null;
  processing_error?: string | null;
  transcription_status?: string | null;
  transcription_error?: string | null;
  transcription_job_id?: string | null;
};

type Props = {
  videos: VideoItem[];
  onDelete: (video: VideoItem) => void;
  onView: (id: string) => void;
  onAssign: (id: string) => void;
  canManageProcessing: boolean;
};

function VideoList({ videos, onDelete, onView, onAssign, canManageProcessing }: Props) {
  const [transcriptVideo, setTranscriptVideo] = useState<VideoItem | null>(null);
  const [jobMessage, setJobMessage] = useState("");
  const [starting, setStarting] = useState<string | null>(null);
  async function transcribe(videoId: string) {
    setStarting(videoId);
    setJobMessage("");
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || ""}/api/videos/${videoId}/transcription`, {
        method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not start transcription.");
      setJobMessage("Transcription queued. Its status will update in the video list.");
    } catch (cause) { setJobMessage(cause instanceof Error ? cause.message : "Could not start transcription."); }
    finally { setStarting(null); }
  }
  return (
    <section className="video-list">
      <h2>Video list</h2>
      {jobMessage && <p>{jobMessage}</p>}

      <div className="video-table-wrapper">
        <table className="video-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Size</th>
              <th>Status</th>
              <th>Uploaded</th>
              <th>Annotations</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {videos.length === 0 && (
              <tr>
                <td colSpan={6}>No videos uploaded yet.</td>
              </tr>
            )}

            {videos.map((v) => (
              <tr key={v.id}>
                <td>{v.filename}</td>
                <td>{(v.size_bytes / 1024 / 1024).toFixed(2)} MB</td>
                <td>
                  <span className={`video-status ${v.status.toLowerCase()}`}>
                    {v.status}
                  </span>
                  {v.processing_error && <p>{v.processing_error}</p>}
                  {v.transcription_status && <p>Transcription: {v.transcription_status}</p>}
                  {v.transcription_error && <p>{v.transcription_error}</p>}
                </td>
                <td>{new Date(v.uploaded_at).toLocaleString()}</td>
                <td>—</td>
                <td>
                  <button type="button" className="view-button" onClick={() => onView(v.id)} disabled={v.status !== "COMPLETED"}>
                    View
                  </button>{" "}

                    <button
                    type="button"
                    className="view-button"
                    onClick={() => onAssign(v.id)}
                    >
                      Assign
                      </button>{" "}
                  <button
                    type="button"
                    className="view-button delete-button"
                    onClick={() => onDelete(v)}
                  >
                    Delete
                  </button>
                  {canManageProcessing && <button type="button" onClick={() => void transcribe(v.id)} disabled={starting !== null || v.status !== "COMPLETED" || ["QUEUED", "RUNNING"].includes(v.transcription_status || "")}>
                    {starting === v.id ? "Starting…" : "Transcribe audio"}
                  </button>}
                  {canManageProcessing && v.transcription_status === "COMPLETED" && v.transcription_job_id && (
                    <button type="button" className="view-button" onClick={() => setTranscriptVideo(v)}>View transcript</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canManageProcessing && transcriptVideo?.transcription_job_id && (
        <TranscriptViewer video={transcriptVideo} jobId={transcriptVideo.transcription_job_id} onClose={() => setTranscriptVideo(null)} />
      )}
    </section>
  );
}

export default VideoList;
