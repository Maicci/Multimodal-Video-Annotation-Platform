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