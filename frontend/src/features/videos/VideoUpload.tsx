import { useState } from "react";

function VideoUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string>("");

  const allowedTypes: string[] = [
    "video/mp4",
    "video/quicktime"
  ];

  const maxFileSize = 500 * 1024 * 1024;

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];

    setFile(null);
    setError("");

    if (!selectedFile) {
      return;
    }

    if (!allowedTypes.includes(selectedFile.type)) {
      setError("Only MP4 and MOV files are supported.");
      return;
    }

    if (selectedFile.size > maxFileSize) {
      setError("The selected file is too large.");
      return;
    }

    setFile(selectedFile);
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

      <button
        type="button"
        disabled={!file}
      >
        Upload
      </button>
    </section>
  );
}

export default VideoUpload;