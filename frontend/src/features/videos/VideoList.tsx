export type VideoItem = {
  id: string;
  filename: string;
  size_bytes: number;
  status: string;
  uploaded_at: string;
  duration: number | null;
};

type Props = {
  videos: VideoItem[];
  onDelete: (video: VideoItem) => void;
  onView: (id: string) => void;
};

function VideoList({ videos, onDelete, onView }: Props) {
  return (
    <section className="video-list">
      <h2>Video list</h2>

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
                </td>
                <td>{new Date(v.uploaded_at).toLocaleString()}</td>
                <td>—</td>
                <td>
                  <button type="button" className="view-button" onClick={() => onView(v.id)} disabled={v.status !== "COMPLETED"}>
                    View
                  </button>{" "}
                  <button
                    type="button"
                    className="view-button delete-button"
                    onClick={() => onDelete(v)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default VideoList;
