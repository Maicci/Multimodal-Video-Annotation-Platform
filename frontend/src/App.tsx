// Renders the application
// The page can currently be changed by returning a different page component here
// TODO: Render pages based on the authenticated user's role.

import AdminPage from "./pages/AnnotatorPage";

function App() {
  return <AdminPage />;
}

export default App;