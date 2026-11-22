import { useEffect, useState } from "react";
import AdminPage from "./pages/AdminPage";
import AnnotatorHomePage from "./pages/AnnotatorHomePage";
import LoginPage from "./pages/LoginPage";
import VideoViewer from "./features/videos/VideoViewer";

const API_URL = import.meta.env.VITE_API_URL || "";

function App() {
  const [videoId, setVideoId] = useState<string | null>(null);
  const [token, setToken] = useState(() => localStorage.getItem("access_token"));
  const [role, setRole] = useState<string | null>(null);
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
        return response.json();
      })
      .then((me) => {
        setRole(me.role); 
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

  const signOut = () => {
    localStorage.removeItem("access_token");
    setToken(null);
    setRole(null);
    setVideoId(null);
  };

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

  // annotators home page
  if (role === "annotator") {
    return (
      <AnnotatorHomePage token={token} onOpenVideo={setVideoId} onSignOut={signOut} />
    );
  }
// admin page
  return <AdminPage onView={setVideoId} onSignOut={signOut} />;
}

export default App;