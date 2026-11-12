import VideoViewer from "../features/videos/VideoViewer";
import "../assets/css/AnnotatorPage.css";

function AnnotatorPage() {
  return (
    <div className="annotator-page">
      <header className="annotator-header">
        <div className="annotator-logo">
          Video Annotation
        </div>

      </header>

      <main className="annotator-content">
        <VideoViewer />
      </main>
    </div>
  );
}

export default AnnotatorPage;