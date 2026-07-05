/** Base path helpers — works behind path prefix and in embedded previews (Cursor). */
(function (global) {
  function appRoot() {
    const parts = global.location.pathname.split("/").filter(Boolean);
    if (parts.length && parts[parts.length - 1] === "login") {
      parts.pop();
    }
    return parts.length ? "/" + parts.join("/") : "";
  }

  function join(base, segment) {
    const clean = String(segment || "").replace(/^\//, "");
    return (base ? base + "/" : "/") + clean;
  }

  global.SIPCRM = {
    root: appRoot(),
    api(path) {
      return join(appRoot(), "api/" + String(path || "").replace(/^\//, ""));
    },
    static(path) {
      return join(appRoot(), "static/" + String(path || "").replace(/^\//, ""));
    },
    homeUrl() {
      const root = appRoot();
      return root ? root + "/" : "/";
    },
    loginUrl() {
      return join(appRoot(), "login");
    },
  };
})(window);
