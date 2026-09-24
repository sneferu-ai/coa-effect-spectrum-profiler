/* Synchronous, local-only enhancement marker. Kept external so the response
   can enforce a script-src 'self' Content Security Policy without inline JS. */
document.documentElement.classList.remove("no-js");
document.documentElement.classList.add("js");
