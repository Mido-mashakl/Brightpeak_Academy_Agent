const path = require("path");
const Database = require("better-sqlite3");

// The project's schema.sql / seed.sql are written for SQLite
// (PRAGMA foreign_keys, AUTOINCREMENT, DATETIME('now')...),
// so the server talks to a local SQLite file, not a separate
// MySQL server. This one file is the whole "database setup".
const dbPath = path.join(__dirname, "..", "brightpeak.db");
const db = new Database(dbPath);

db.pragma("foreign_keys = ON");

module.exports = db;