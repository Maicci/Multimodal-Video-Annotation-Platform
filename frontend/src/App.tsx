import { useEffect, useState } from "react";
import AdminPage from "./pages/AdminPage";
import LoginPage from "./pages/LoginPage";
import VideoViewer from "./features/videos/VideoViewer";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function App() {
  const [videoId, setVideoId] = useState<string | null>(null);
  const [token, setToken] = useState(() => localStorage.getItem("access_token"));
  const [checkingToken, setCheckingToken] = useState(Boolean(token));

  useEffect(() => {
    if (!token) {
      setCheckingToken(false);
      return;
    }
    const controller = new AbortController();
    setCheckingToken(true);
    fetch(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error("Session expired");
        setCheckingToken(false);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        localStorage.removeItem("access_token");
        setToken(null);
        setCheckingToken(false);
      });
    return () => controller.abort();
  }, [token]);

  if (checkingToken) return <main><p>Checking sign-in…</p></main>;

  if (!token) return <LoginPage onLogin={(newToken) => {
    setCheckingToken(true);
    setToken(newToken);
  }} />;

  if (videoId) {
    return (
      <main>
        <button type="button" onClick={() => setVideoId(null)}>Back to videos</button>
        <VideoViewer videoId={videoId} />
      </main>
    );
  }

  return (
    <AdminPage
      onView={setVideoId}
      onSignOut={() => {
        localStorage.removeItem("access_token");
        setToken(null);
      }}
    />
  );
}

export default App;
