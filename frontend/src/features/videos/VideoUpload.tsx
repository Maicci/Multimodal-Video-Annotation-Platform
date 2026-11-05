import { useState } from "react";

function VideoUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  const allowedTypes = [
    "video/mp4",
    "video/quicktime",
  ];

  const maxFileSize = 500 * 1024 * 1024;

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];

    setFile(null);
    setError("");
    setSuccessMessage("");

    if (!selectedFile) return;

    if (!allowedTypes.includes(selectedFile.type)) {
      setError("Only MP4 and MOV files are supported.");
      return;
    }

    if (selectedFile.size > maxFileSize) {
      setError("The selected file is too large. Maximum size is 500 MB.");
      return;
    }

    setFile(selectedFile);
  }

  async function handleUpload() {
    if (!file) return;

    setIsUploading(true);
    setError("");
    setSuccessMessage("");

    const token = localStorage.getItem("access_token");

    if (!token) {
      setError("You must be logged in to upload videos.");
      setIsUploading(false);
      return;
    }

    const formData = new FormData();

    formData.append("upload", file);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/videos/upload",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Video upload failed.");
      }

      console.log("Uploaded video:", data);

      setSuccessMessage(
        `Video "${data.filename}" uploaded successfully. Status: ${data.status}`
      );

      setFile(null);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Video upload failed.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section>
      <h2>Upload video</h2>

      <input
        type="file"
        accept=".mp4,.mov"
        onChange={handleFileChange}
      />

      {file && (
        <div>
          <p>Selected file: {file.name}</p>
          <p>
            Size: {(file.size / 1024 / 1024).toFixed(2)} MB
          </p>
        </div>
      )}

      {error && <p>{error}</p>}

      {successMessage && <p>{successMessage}</p>}

      <button
        type="button"
        disabled={!file || isUploading}
        onClick={handleUpload}
      >
        {isUploading ? "Uploading..." : "Upload"}
      </button>
    </section>
  );
}

export default VideoUpload;