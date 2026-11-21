import { useState } from "react";
import AdminPage from "./pages/AdminPage";
import LoginPage from "./pages/LoginPage";
import VideoViewer from "./features/videos/VideoViewer";

function App() {
  const [videoId, setVideoId] = useState<string | null>(null);
  const [token, setToken] = useState(() => localStorage.getItem("access_token"));

  if (!token) return <LoginPage onLogin={setToken} />;

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
