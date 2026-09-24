/* Sneferu hosted-preview handoff — client half.
 *
 * When the accepted product is opened through Sneferu's product launcher,
 * the launch wrapper authenticates the operator at the edge (access cookie +
 * injected Authorization header) and, before redirecting here, plants a
 * versioned record at localStorage["sneferu.preview.bootstrap.v1"]:
 *
 *   {schema, username, role, authorization_scheme, ...}
 *
 * This module is the client that consumes that record, so the browser tab
 * provably rides the same authenticated session the launcher established
 * instead of rendering as a logged-out visitor. It runs on every page,
 * before the page-specific enhancement script.
 *
 * Direct runs (uvicorn locally, Docker) never carry the record; the product
 * is accountless and behaves identically either way — no UI is added, no
 * network call is made, and nothing is written beyond a read-only marker
 * attribute that the hosted browser journey can assert.
 */
(function () {
  "use strict";

  function consumePreviewBootstrap() {
    var storageKey = "sneferu.preview.bootstrap.v1";
    var raw;
    try {
      raw = window.localStorage.getItem(storageKey);
    } catch (err) {
      /* Storage denied (e.g. hardened private mode). The server-side
         session still stands; there is simply nothing client-side to
         adopt. */
      return null;
    }
    if (!raw) { return null; } /* standalone run — not a hosted preview */

    var record;
    try {
      record = JSON.parse(raw);
    } catch (err) {
      return null; /* not our record; never act on bytes we cannot read */
    }
    if (!record || record.schema !== "sneferu.preview.bootstrap/v1") {
      return null;
    }
    /* A launcher record can contain edge credentials that this product does
       not need. Consume the one-time handoff and remove it from persistent
       storage before doing anything else with the validated metadata. */
    try {
      window.localStorage.removeItem(storageKey);
    } catch (err) { /* storage became unavailable after the read */ }
    if (typeof record.username !== "string" || !record.username) {
      return null;
    }
    return record;
  }

  var bootstrap = consumePreviewBootstrap();
  if (!bootstrap) { return; }

  /* The launcher's server-side wrapper authenticates every request; this
     marker is how the browser side acknowledges the handoff. The hosted
     journey proof (launch → authenticate → recover) can assert it. */
  document.documentElement.setAttribute("data-preview-session", "authenticated");
  if (
    bootstrap.authorization_scheme === "bearer" ||
    bootstrap.authorization_scheme === "basic"
  ) {
    document.documentElement.setAttribute(
      "data-preview-auth-scheme",
      bootstrap.authorization_scheme
    );
  }

  /* Authentication remains entirely at the launcher edge. This accountless
     product neither consumes nor duplicates any credential from the handoff. */
})();
