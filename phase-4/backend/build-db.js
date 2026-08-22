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
console.log("Done -> ../brightpeak.db");