// init-db.js
// Shared DB bootstrap logic, reused by:
//   - db.js        -> silent, idempotent check on every server start
//   - build-db.js   -> explicit manual rebuild/reset
//
// Single source of truth: phase-4/db/schema.sql + phase-4/db/seed.sql.
// phase-3/db/schema.sql and seed.sql are symlinks to these same files
// (see phase-3/mcp_server/database.py, which was fixed to read the
// phase-4 copies directly rather than a second, independently-drifting
// set of schema/seed files).
const fs = require("fs");
const path = require("path");
const Database = require("better-sqlite3");

const DB_PATH = path.join(__dirname, "..", "brightpeak.db");
const SCHEMA_PATH = path.join(__dirname, "..", "db", "schema.sql");
const SEED_PATH = path.join(__dirname, "..", "db", "seed.sql");
const PHASE3_DB_PATH = path.join(__dirname, "..", "..", "phase-3", "db", "brightpeak.db");

function ensureDatabaseFile() {
    if (fs.existsSync(DB_PATH) && fs.statSync(DB_PATH).size > 0) return;
    console.log("brightpeak.db missing or empty — building it automatically...");
    if (fs.existsSync(DB_PATH)) fs.unlinkSync(DB_PATH); // remove a stale 0-byte file
    const db = new Database(DB_PATH);
    db.pragma("foreign_keys = ON");
    db.exec(fs.readFileSync(SCHEMA_PATH, "utf8"));
    db.exec(fs.readFileSync(SEED_PATH, "utf8"));
    db.close();
    console.log("brightpeak.db created and seeded automatically.");
}

function ensurePortableSymlink() {
    if (!fs.existsSync(path.dirname(PHASE3_DB_PATH))) return; // phase-3 not present as a sibling
    const relativeTarget = path.relative(path.dirname(PHASE3_DB_PATH), DB_PATH);
    try {
        const current = fs.readlinkSync(PHASE3_DB_PATH);
        if (current === relativeTarget) return; // already correct, no-op
    } catch (_) { /* doesn't exist or isn't a symlink yet — fall through */ }
    try { fs.unlinkSync(PHASE3_DB_PATH); } catch (_) { /* fine if missing */ }
    fs.symlinkSync(relativeTarget, PHASE3_DB_PATH);
    console.log(`phase-3/db/brightpeak.db -> ${relativeTarget} (relative, portable)`);
}

function ensureDatabase() {
    ensureDatabaseFile();
    ensurePortableSymlink();
}

module.exports = { ensureDatabase, DB_PATH };