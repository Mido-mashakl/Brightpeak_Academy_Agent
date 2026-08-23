const Database = require("better-sqlite3");
const { ensureDatabase, DB_PATH } = require("./init-db");

// The project's schema.sql / seed.sql are written for SQLite
// (PRAGMA foreign_keys, AUTOINCREMENT, DATETIME('now')...),
// so the server talks to a local SQLite file, not a separate
// MySQL server. init-db.js builds it automatically (schema + seed +
// the portable symlink to phase-3/db/) if it's missing, so a fresh
// checkout or Docker build needs zero manual steps.
ensureDatabase();

const db = new Database(DB_PATH);
db.pragma("foreign_keys = ON");

module.exports = db;