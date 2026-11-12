// Main administrator page.
// Combines the video upload interface and the list of uploaded videos.

import VideoUpload from "../features/videos/VideoUpload";
import VideoList from "../features/videos/VideoList";

function AdminPage() {
  return (
    <main>
      <h1>Admin Page</h1>

      <VideoUpload />
      <VideoList />
    </main>
  );
}

export default AdminPage;