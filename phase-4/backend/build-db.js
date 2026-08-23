// Rebuilds brightpeak.db from db/schema.sql + db/seed.sql.
// Run this again any time you change schema.sql or seed.sql, or to
// reset the database back to seed state.
//
// Reuses the same init-db.js logic db.js uses automatically on every
// server start, so schema/seed/symlink handling only exists in one
// place (see init-db.js's module docstring for why that matters).
const fs = require("fs");
const path = require("path");
const { ensureDatabase, DB_PATH } = require("./init-db");

if (fs.existsSync(DB_PATH)) {
    fs.unlinkSync(DB_PATH);
    console.log("Removed old brightpeak.db");
}

ensureDatabase();
console.log("Done -> " + path.relative(process.cwd(), DB_PATH));