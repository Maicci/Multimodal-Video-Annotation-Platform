import { useRef, useState } from "react";
import "../../assets/css/VideoUpload.css";

const API_URL = import.meta.env.VITE_API_URL || "";
const MAX_FILE_SIZE = 500 * 1024 * 1024;

type Props = { onUploaded: () => void };

function sendUpload(file: File, token: string, onProgress: (percent: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("upload", file);

    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };
    request.onerror = () => reject(new Error("Could not reach the server."));
    request.onload = () => {
      let data: { error?: string; filename?: string };
      try {
        data = JSON.parse(request.responseText);
      } catch {
        reject(new Error("The server returned an invalid response."));
        return;
      }
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(data.error || "Video upload failed."));
        return;
      }
      if (!data.filename) {
        reject(new Error("The server did not confirm the uploaded video."));
        return;
      }
      resolve(data.filename);
    };

    request.open("POST", `${API_URL}/api/videos/upload`);
    request.setRequestHeader("Authorization", `Bearer ${token}`);
    request.send(formData);
  });
}

function VideoUpload({ onUploaded }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    setFile(null);
    setError("");
    setSuccessMessage("");
    setUploadPercent(null);

    if (!selectedFile) return;
    if (!/\.(mp4|mov)$/i.test(selectedFile.name)) {
      setError("Only MP4 and MOV files are supported.");
      return;
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError("The selected file is too large. Maximum size is 500 MB.");
      return;
    }
    setFile(selectedFile);
  }

  async function handleUpload() {
    if (!file) return;

    setIsUploading(true);
    setUploadPercent(0);
    setError("");
    setSuccessMessage("");

    const token = localStorage.getItem("access_token");
    if (!token) {
      setError("You must be logged in to upload videos.");
      setIsUploading(false);
      setUploadPercent(null);
      return;
    }

    try {
      const filename = await sendUpload(file, token, setUploadPercent);
      setSuccessMessage(`Video "${filename}" uploaded successfully.`);
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      onUploaded();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Video upload failed.");
    } finally {
      setIsUploading(false);
      setUploadPercent(null);
    }
  }

  return (
    <section>
      <h2>Upload video</h2>
      <input
        ref={fileInput}
        type="file"
        accept=".mp4,.mov"
        onChange={handleFileChange}
        disabled={isUploading}
      />

      {file && (
        <div>
          <p>Selected file: {file.name}</p>
          <p>Size: {(file.size / 1024 / 1024).toFixed(2)} MB</p>
        </div>
      )}

      {error && <p role="alert">{error}</p>}
      {successMessage && <p role="status">{successMessage}</p>}
      {isUploading && (
        <div className="upload-progress">
          <progress aria-label="Video upload progress" max={100} value={uploadPercent ?? undefined} />
          <p role="status">
            {uploadPercent === null
              ? "Uploading video…"
              : uploadPercent === 100
                ? "Upload sent. Waiting for server…"
                : `Uploading video: ${uploadPercent}%`}
          </p>
        </div>
      )}
      <button type="button" disabled={!file || isUploading} onClick={handleUpload}>
        {isUploading ? "Uploading..." : "Upload"}
      </button>
    </section>
  );
}

export default VideoUpload;
