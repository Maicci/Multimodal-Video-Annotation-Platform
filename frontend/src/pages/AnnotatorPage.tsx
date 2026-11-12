// Main page for annotators.
// Displays the video annotation workspace.

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
         {/* TODO: Replace hardcoded video ID with the annotator's assigned video. */}
        <VideoViewer videoId="4b6beb8a-ab30-4780-9a07-4b44c7b65291" />
      </main>
    </div>
  );
}

export default AnnotatorPage;