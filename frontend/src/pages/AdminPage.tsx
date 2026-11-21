// Main administrator page.
// Combines the video upload interface and the list of uploaded videos.

import { useCallback, useEffect, useState } from "react";
import VideoUpload from "../features/videos/VideoUpload";
import VideoList, { type VideoItem } from "../features/videos/VideoList";

const API_URL = import.meta.env.VITE_API_URL || "";

function AdminPage({ onView, onSignOut }: { onView: (id: string) => void; onSignOut: () => void }) {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [listError, setListError] = useState("");

  const loadVideos = useCallback(async () => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      setListError("You must be logged in to see the video list.");
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/videos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        onSignOut();
        return;
      }
      if (!res.ok) throw new Error(`Video list request failed (${res.status})`);
      const data: unknown = await res.json();
      if (!Array.isArray(data)) throw new Error("Video list response was not an array");
      setVideos(data as VideoItem[]);
      setListError("");
    } catch (err) {
      console.error("Video list request failed:", err);
      setListError(err instanceof Error ? err.message : "Could not load the video list.");
    }
  }, [onSignOut]);

  useEffect(() => {
    loadVideos();
    const interval = window.setInterval(loadVideos, 3000);
    return () => window.clearInterval(interval);
  }, [loadVideos]);

  const deleteVideo = useCallback(
    async (video: VideoItem) => {
      const confirmed = window.confirm(
        `Delete "${video.filename}"? The video and its data are removed permanently.`
      );
      if (!confirmed) return;

      const token = localStorage.getItem("access_token");
      if (!token) {
        setListError("You must be logged in to delete videos.");
        return;
      }

      try {
        const res = await fetch(`${API_URL}/api/videos/${video.id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          console.error("Delete failed:", res.status, await res.text());
          setListError(`Could not delete the video (status ${res.status}).`);
          return;
        }

        await loadVideos(); // refresh the list from the database
      } catch (err) {
        console.error("Delete request failed:", err);
        setListError("Could not reach the server.");
      }
    },
    [loadVideos]
  );

  return (
    <main>
      <h1>Admin Page</h1>
      <button type="button" onClick={onSignOut}>Sign out</button>

      <VideoUpload onUploaded={loadVideos} />

      {listError && <p>{listError}</p>}
      <VideoList videos={videos} onDelete={deleteVideo} onView={onView} />
    </main>
  );
}

export default AdminPage;
