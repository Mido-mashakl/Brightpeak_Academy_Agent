// Rebuilds brightpeak.db from schema.sql + seed.sql.
// Run this again any time you change schema.sql or seed.sql.
const fs = require("fs");
const path = require("path");
const Database = require("better-sqlite3");

const dbPath = path.join(__dirname, "brightpeak.db");

if (fs.existsSync(dbPath)) {
    fs.unlinkSync(dbPath);
    console.log("Removed old brightpeak.db");
}

const db = new Database(dbPath);
db.pragma("foreign_keys = ON");

db.exec(fs.readFileSync(path.join(__dirname, "schema.sql"), "utf8"));
console.log("Schema applied.");

db.exec(fs.readFileSync(path.join(__dirname, "seed.sql"), "utf8"));
console.log("Seed data inserted.");

db.close();
console.log("Done -> brightpeak.db");