/* COA Effect-Spectrum Profiler — progressive enhancement only (SPEC §10).
   No dependencies, no build step. The full journey works without this file:
   it enhances the dropzone, shows an honest loading overlay, wires anonymous
   feedback, enables the client-side JSON download, and scrolls source spans
   into view. The no-js → js class swap happens inline in <head>, not here. */
(function () {
  "use strict";

  var reducedMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    /* Reveal JS-only features (D5, D13). */
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-feedback], [data-download-json]"),
      function (el) { el.hidden = false; }
    );

    /* ------------------------------------------------ upload page ----- */
    var form = document.getElementById("upload-form");
    if (form) {
      var input = document.getElementById("file");
      var dropzone = document.getElementById("dropzone");
      var status = document.getElementById("file-status");
      var submit = document.getElementById("upload-submit");
      var helper = document.getElementById("upload-helper");
      var overlay = document.getElementById("loading-overlay");
      var maxBytes = parseInt(form.getAttribute("data-max-upload-bytes"), 10) || 0;
      var oversize = false;

      function fmtSize(bytes) {
        if (bytes >= 1048576) { return (bytes / 1048576).toFixed(1) + " MB"; }
        return Math.max(1, Math.round(bytes / 1024)) + " KB";
      }

      function refreshSubmit() {
        var hasFile = input && input.files && input.files.length > 0;
        if (submit) { submit.disabled = !hasFile || oversize; }
        if (helper) {
          helper.classList.toggle("is-visible", !hasFile || oversize);
          helper.textContent = oversize
            ? "That file is too large — the limit is " + Math.round(maxBytes / 1048576) + " MB."
            : "Select a file to continue";
        }
      }

      function describe(file) {
        oversize = maxBytes > 0 && file.size > maxBytes;
        if (status) {
          status.textContent = oversize
            ? "Selected: " + file.name + " (" + fmtSize(file.size) + ") — over the size limit."
            : "Selected: " + file.name + ", " + fmtSize(file.size);
        }
        refreshSubmit();
      }

      if (submit) { submit.disabled = true; }

      if (input) {
        input.addEventListener("change", function () {
          if (input.files && input.files[0]) { describe(input.files[0]); }
        });
      }

      if (dropzone && input) {
        ["dragenter", "dragover"].forEach(function (evt) {
          dropzone.addEventListener(evt, function (e) {
            e.preventDefault();
            dropzone.classList.add("dragover");
          });
        });
        ["dragleave", "drop"].forEach(function (evt) {
          dropzone.addEventListener(evt, function () {
            dropzone.classList.remove("dragover");
          });
        });
        dropzone.addEventListener("drop", function (e) {
          e.preventDefault();
          var files = e.dataTransfer && e.dataTransfer.files;
          if (files && files.length) {
            try {
              var dt = new DataTransfer();
              dt.items.add(files[0]);
              input.files = dt.files;
            } catch (err) { /* older engines: user picks via the dialog */ }
            if (input.files && input.files[0]) { describe(input.files[0]); }
          }
        });
      }

      form.addEventListener("submit", function (e) {
        if (oversize) {
          e.preventDefault();
          return;
        }
        if (!overlay) { return; }
        overlay.hidden = false;
        var title = document.getElementById("overlay-title");
        if (title) { title.focus(); }
        /* Focus trap: the overlay is modal while visible (SPEC §10.3). */
        overlay.addEventListener("keydown", function (ev) {
          if (ev.key === "Tab") { ev.preventDefault(); }
        });
      });
    }

    /* ------------------------------------------------ feedback -------- */
    var feedback = document.querySelector("[data-feedback]");
    if (feedback) {
      var statusLine = feedback.querySelector(".feedback-status");
      var buttons = feedback.querySelectorAll("[data-feedback-value]");
      var setDisabled = function (v) {
        Array.prototype.forEach.call(buttons, function (b) { b.disabled = v; });
      };
      Array.prototype.forEach.call(buttons, function (btn) {
        btn.addEventListener("click", function () {
          var body = {
            helpful: btn.getAttribute("data-feedback-value") === "true",
            placement: parseInt(feedback.getAttribute("data-placement"), 10),
            completeness: feedback.getAttribute("data-completeness"),
            lab_format: feedback.getAttribute("data-lab-format")
          };
          setDisabled(true);
          btn.setAttribute("aria-pressed", "true");
          if (statusLine) { statusLine.textContent = "Submitting…"; }
          var xhr = new XMLHttpRequest();
          xhr.open("POST", "/feedback", true);
          xhr.setRequestHeader("Content-Type", "application/json");
          xhr.onload = function () {
            if (xhr.status === 204) {
              if (statusLine) {
                statusLine.textContent = "Thank you. Your feedback helps improve the tool.";
              }
            } else {
              if (statusLine) { statusLine.textContent = "Feedback could not be recorded."; }
              btn.setAttribute("aria-pressed", "false");
              if (xhr.status !== 429) { setDisabled(false); }
            }
          };
          xhr.onerror = function () {
            if (statusLine) { statusLine.textContent = "Feedback could not be recorded."; }
            btn.setAttribute("aria-pressed", "false");
            setDisabled(false);
          };
          xhr.send(JSON.stringify(body));
        });
      });
    }

    /* ------------------------------------------------ JSON download --- */
    var jsonBtn = document.querySelector("[data-download-json]");
    if (jsonBtn) {
      jsonBtn.addEventListener("click", function () {
        var block = document.getElementById("result-data");
        if (!block) { return; }
        var score = jsonBtn.getAttribute("data-score") || "result";
        var blob = new Blob([block.textContent], { type: "application/json" });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "coa-profile-" + score + ".json";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      });
    }

    /* ------------------------------------------------ source spans ---- */
    Array.prototype.forEach.call(document.querySelectorAll("details.source-span"), function (d) {
      d.addEventListener("toggle", function () {
        if (!d.open) { return; }
        var rect = d.getBoundingClientRect();
        var offscreen = rect.top < 0 || rect.bottom > window.innerHeight;
        if (offscreen) {
          d.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "nearest" });
        }
      });
    });

    /* ------------------------------------------------ aria-expanded --- */
    /* SPEC §13: aria-expanded on COA explainer and source-span <details>.
       Browsers expose this implicitly for <details>, but the attribute is
       required by the spec for older AT. We keep it in sync on toggle. */
    Array.prototype.forEach.call(document.querySelectorAll("details"), function (d) {
      d.setAttribute("aria-expanded", d.open ? "true" : "false");
      d.addEventListener("toggle", function () {
        d.setAttribute("aria-expanded", d.open ? "true" : "false");
      });
    });
  });
})();
