// Rebuilds brightpeak.db from db/schema.sql + db/seed.sql.
// Run this again any time you change schema.sql or seed.sql.
//
// IMPORTANT: schema.sql / seed.sql live in ../db/ (single source of truth),
// and the rebuilt file is written to ../brightpeak.db (repo root) because
// that's the exact path db.js reads from when the server starts. Building
// to any other location means the server keeps using the OLD data.
const fs = require("fs");
const path = require("path");
const Database = require("better-sqlite3");

const dbPath = path.join(__dirname, "..", "brightpeak.db");
const schemaPath = path.join(__dirname, "..", "db", "schema.sql");
const seedPath = path.join(__dirname, "..", "db", "seed.sql");

if (fs.existsSync(dbPath)) {
    fs.unlinkSync(dbPath);
    console.log("Removed old brightpeak.db");
}

const db = new Database(dbPath);
db.pragma("foreign_keys = ON");

db.exec(fs.readFileSync(schemaPath, "utf8"));
console.log("Schema applied.");

db.exec(fs.readFileSync(seedPath, "utf8"));
console.log("Seed data inserted.");

db.close();

// -----------------------------------------------------------------
// Single source of truth: phase-3's Python side (mcp_server/database.py,
// state_graph/*/checkpointing.py, track_recommendation/db.py) all
// hardcode their own path to phase-3/db/brightpeak.db, completely
// separate from this file. Without this step, the platform's FastAPI
// routers (which import phase-3's graphs directly, see
// backend/core/graph_loader.py) would read/write a SECOND, empty
// SQLite file with almost the same schema — Students/Instructors/etc.
// would exist on this side but not that one, and every graph call
// would fail with "no such student" even for real, seeded students.
// Symlinking phase-3/db/brightpeak.db -> this file keeps exactly one
// physical database, as the project brief requires ("do not create a
// second database").
const path3 = require("path");
const phase3DbPath = path3.join(__dirname, "..", "..", "phase-3", "db", "brightpeak.db");

try {
    try { fs.unlinkSync(phase3DbPath); } catch (_) { /* didn't exist yet, fine */ }
    fs.symlinkSync(dbPath, phase3DbPath);
    console.log(`Linked phase-3/db/brightpeak.db -> ${dbPath}`);
} catch (e) {
    console.warn(
        "Could not symlink phase-3/db/brightpeak.db (continuing without it). " +
        "The FastAPI backend will create its OWN separate brightpeak.db on first " +
        "import unless you create this symlink manually:\n" +
        `  ln -sf "${dbPath}" "${phase3DbPath}"\n` +
        `Reason: ${e.message}`
    );
}

console.log("Done -> ../brightpeak.db");