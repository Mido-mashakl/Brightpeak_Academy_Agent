const Database = require("better-sqlite3");
const fs = require("fs");
const { ensureDatabase, DB_PATH } = require("./init-db");

// The project's schema.sql / seed.sql are written for SQLite
// (PRAGMA foreign_keys, AUTOINCREMENT, DATETIME('now')...),
// so the server talks to a local SQLite file, not a separate
// MySQL server. init-db.js builds it automatically (schema + seed +
// the portable symlink to phase-3/db/) if it's missing, so a fresh
// checkout or Docker build needs zero manual steps.

const dbPath = path.join(__dirname, "..", "brightpeak.db");
const schemaPath = path.join(__dirname, "..", "db", "schema.sql");
const seedPath = path.join(__dirname, "..", "db", "seed.sql");

ensureDatabase();

const db = new Database(DB_PATH);
const isNew = !fs.existsSync(dbPath);

db.pragma("foreign_keys = ON");
if (isNew) {
    console.log("brightpeak.db not found — building from schema.sql + seed.sql");
    db.exec(fs.readFileSync(schemaPath, "utf8"));
    db.exec(fs.readFileSync(seedPath, "utf8"));
    console.log("Database built.");
}

module.exports = db;