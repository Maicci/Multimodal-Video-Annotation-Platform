// Main administrator page.

import { useCallback, useEffect, useState } from "react";
import VideoUpload from "../features/videos/VideoUpload";
import VideoList, { type VideoItem } from "../features/videos/VideoList";
import PendingUsers from "../features/users/PendingUsers";
import "../assets/css/AdminPage.css";

const API_URL = import.meta.env.VITE_API_URL || "";

type AssignableUser = {
  id: string;
  full_name: string;
  email: string;
  role: string | null;
  status: string;
};

function AdminPage({
  onView,
  onSignOut,
}: {
  onView: (id: string) => void;
  onSignOut: () => void;
}) {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [listError, setListError] = useState("");

  const [showPendingUsers, setShowPendingUsers] = useState(false);

  const [assignVideoId, setAssignVideoId] = useState<string | null>(null);
  const [assignQuery, setAssignQuery] = useState("");
  const [assignAnnotatorId, setAssignAnnotatorId] = useState<string | null>(null);
  const [assignUsers, setAssignUsers] = useState<AssignableUser[] | null>(null);
  const [assignUsersError, setAssignUsersError] = useState("");
  const [assignError, setAssignError] = useState("");
  const [assignMessage, setAssignMessage] = useState("");
  const [assignLoading, setAssignLoading] = useState(false);

  const loadVideos = useCallback(async () => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      setListError("You must be logged in to see the video list.");
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/videos`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 401) {
        onSignOut();
        return;
      }

      if (!res.ok) {
        throw new Error(`Video list request failed (${res.status})`);
      }

      const data: unknown = await res.json();

      if (!Array.isArray(data)) {
        throw new Error("Video list response was not an array");
      }

      setVideos(data as VideoItem[]);
      setListError("");
    } catch (err) {
      console.error("Video list request failed:", err);

      setListError(
        err instanceof Error
          ? err.message
          : "Could not load the video list."
      );
    }
  }, [onSignOut]);

  useEffect(() => {
    loadVideos();

    const interval = window.setInterval(loadVideos, 3000);

    return () => window.clearInterval(interval);
  }, [loadVideos]);

  useEffect(() => {
    if (!assignVideoId) return;
    const token = localStorage.getItem("access_token");
    const controller = new AbortController();
    setAssignUsers(null);
    setAssignUsersError("");
    if (!token) {
      setAssignUsersError("Sign in again to load annotators.");
      return;
    }
    fetch(`${API_URL}/api/users`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load annotators (${response.status}).`);
        return response.json() as Promise<AssignableUser[]>;
      })
      .then((users) => setAssignUsers(users.filter(
        (user) => user.role === "annotator" && user.status === "active"
      )))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setAssignUsersError(error instanceof Error ? error.message : "Could not load annotators.");
        }
      });
    return () => controller.abort();
  }, [assignVideoId]);

  const matchingAnnotators = assignUsers?.filter((user) => {
    const query = assignQuery.trim().toLowerCase();
    return user.full_name.toLowerCase().includes(query) || user.email.toLowerCase().includes(query);
  }).slice(0, 8) ?? [];
  const selectedAnnotator = assignUsers?.find((user) => user.id === assignAnnotatorId);

  const deleteVideo = useCallback(
    async (video: VideoItem) => {
      const confirmed = window.confirm(
        `Delete "${video.filename}"? The video and its data are removed permanently.`
      );

      if (!confirmed) {
        return;
      }

      const token = localStorage.getItem("access_token");

      if (!token) {
        setListError("You must be logged in to delete videos.");
        return;
      }

      try {
        const res = await fetch(`${API_URL}/api/videos/${video.id}`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          console.error(
            "Delete failed:",
            res.status,
            await res.text()
          );

          setListError(
            `Could not delete the video (status ${res.status}).`
          );

          return;
        }

        await loadVideos();
      } catch (err) {
        console.error("Delete request failed:", err);
        setListError("Could not reach the server.");
      }
    },
    [loadVideos]
  );

  const closeAssignModal = () => {
    setAssignVideoId(null);
    setAssignQuery("");
    setAssignAnnotatorId(null);
    setAssignError("");
    setAssignMessage("");
    setAssignLoading(false);
  };

  const assignVideo = async () => {
    if (!assignVideoId || !assignAnnotatorId) {
      return;
    }

    const token = localStorage.getItem("access_token");

    if (!token) {
      setAssignError("You must be logged in to assign videos.");
      return;
    }

    setAssignError("");
    setAssignMessage("");
    setAssignLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/assignments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          video_id: assignVideoId,
          annotator_id: assignAnnotatorId,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);

        setAssignError(
          data?.detail ?? `Could not assign video (${res.status}).`
        );

        return;
      }

      setAssignMessage("Video assigned successfully.");
      setAssignQuery("");
      setAssignAnnotatorId(null);
    } catch (err) {
      console.error("Assignment request failed:", err);
      setAssignError("Could not reach the server.");
    } finally {
      setAssignLoading(false);
    }
  };

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div className="admin-logo">Video Annotation</div>

        <nav className="admin-nav">
          <button
            type="button"
            className="active"
          >
            Videos
          </button>

          <button
            type="button"
            onClick={() => setShowPendingUsers(true)}
          >
            Pending users
          </button>
        </nav>

        <div className="admin-profile">
          <button
            type="button"
            className="sign-out-button"
            onClick={onSignOut}
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="admin-content">
        <section className="admin-section">
          <div className="section-header">
            <div>
              <h1>Videos</h1>
              <p>Upload and manage videos for annotation.</p>
            </div>
          </div>

          <VideoUpload onUploaded={loadVideos} />
        </section>

        <section className="admin-section">
          <div className="section-header">
            <div>
              <h2>Uploaded videos</h2>
              <p>View, assign or remove uploaded videos.</p>
            </div>
          </div>

          {listError && (
            <p className="admin-error">
              {listError}
            </p>
          )}

          <VideoList
            videos={videos}
            onDelete={deleteVideo}
            onView={onView}
            onAssign={setAssignVideoId}
          />
        </section>
      </main>

      {showPendingUsers && (
        <div
          className="modal-backdrop"
          onMouseDown={() => setShowPendingUsers(false)}
        >
          <div
            className="pending-users-modal"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2>Pending users</h2>
                <p>
                  Review registration requests and assign user roles.
                </p>
              </div>

              <button
                type="button"
                className="modal-close-button"
                onClick={() => setShowPendingUsers(false)}
                aria-label="Close pending users"
              >
                ×
              </button>
            </div>

            <PendingUsers />
          </div>
        </div>
      )}

      {assignVideoId && (
        <div
          className="modal-backdrop"
          onMouseDown={closeAssignModal}
        >
          <div
            className="pending-users-modal"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2>Assign video</h2>
                <p>
                  Search for an annotator by name or email.
                </p>
              </div>

              <button
                type="button"
                className="modal-close-button"
                onClick={closeAssignModal}
                aria-label="Close assign video"
              >
                ×
              </button>
            </div>

            <div className="pending-users-content">
              <label htmlFor="annotator-email">
                Annotator
              </label>

              <input
                id="annotator-email"
                type="search"
                value={assignQuery}
                onChange={(event) => {
                  setAssignQuery(event.target.value);
                  setAssignAnnotatorId(null);
                  setAssignMessage("");
                }}
                placeholder="Name or email"
                autoComplete="off"
              />

              {assignUsersError && <p role="alert" className="admin-error">{assignUsersError}</p>}
              {!assignUsers && !assignUsersError && <p>Loading annotators…</p>}
              {assignUsers && assignUsers.length === 0 && <p>No active annotators are available.</p>}
              {assignUsers && !selectedAnnotator && assignUsers.length > 0 && (
                matchingAnnotators.length > 0 ? (
                  <ul className="annotator-suggestions" aria-label="Matching annotators">
                    {matchingAnnotators.map((user) => (
                      <li key={user.id}>
                        <button type="button" onClick={() => {
                          setAssignAnnotatorId(user.id);
                          setAssignQuery(user.email);
                          setAssignError("");
                        }}>
                          <strong>{user.full_name}</strong>
                          <span>{user.email}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : <p>No matching annotators.</p>
              )}
              {selectedAnnotator && <p className="selected-annotator">Selected: {selectedAnnotator.full_name} ({selectedAnnotator.email})</p>}

              {assignError && (
                <p className="admin-error">
                  {assignError}
                </p>
              )}

              {assignMessage && (
                <p>
                  {assignMessage}
                </p>
              )}

              <button
                type="button"
                onClick={assignVideo}
                disabled={
                  assignLoading || !assignAnnotatorId
                }
              >
                {assignLoading
                  ? "Assigning..."
                  : "Assign"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminPage;
