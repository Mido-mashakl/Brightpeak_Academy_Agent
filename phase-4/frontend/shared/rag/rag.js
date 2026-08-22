// =========================================================
// Brightpeak Academy — RAG Documents module (privileged, shared)
// Same rationale as shared/tools/tools.js: a capability, not a
// role page.
//   GET    /api/rag/documents
//   POST   /api/rag/documents
//   DELETE /api/rag/documents/{document_id}
// =========================================================

window.BrightPeakRagService = (function () {
  function listDocuments() {
    return window.BrightPeakAPI.get("/api/rag/documents");
  }

  function uploadDocument(doc) {
    return window.BrightPeakAPI.post("/api/rag/documents", doc);
  }

  // DELETE isn't wrapped by shared/api.js yet — add it there if this
  // module moves past the placeholder stage.

  return { listDocuments, uploadDocument };
})();

document.addEventListener("DOMContentLoaded", () => {
  const user = window.BrightPeakAuth.getUser();
  if (!user || !window.BrightPeakPermissions.can(user.role, "rag")) {
    window.location.href = window.BrightPeakAuth.LOGIN_URL;
  }
});
