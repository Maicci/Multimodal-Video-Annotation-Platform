import "../../assets/css/VideoList.css";

type Video = {
  id: number;
  filename: string;
  size: string;
  status: "Processing" | "Ready";
  uploaded: string;
  annotations: string;
};

const videos: Video[] = [

  {
    id: 3,
    filename: "Example.mov",
    size: "210 MB",
    status: "Processing",
    uploaded: "2026-10-22 14:33",
    annotations: "5 / 12",
  },
];

function VideoList() {
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
            {videos.map((video) => (
              <tr key={video.id}>
                <td>{video.filename}</td>
                <td>{video.size}</td>

                <td>
                  <span
                    className={
                      video.status === "Ready"
                        ? "video-status ready"
                        : "video-status processing"
                    }
                  >
                    {video.status}
                  </span>
                </td>

                <td>{video.uploaded}</td>
                <td>{video.annotations}</td>

                <td>
                  <button type="button" className="view-button">
                    View
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