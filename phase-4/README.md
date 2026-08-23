# BrightPeak Academy — Phase 4 Integration

## Run the real platform

Phase 4 uses the SQLite database at `phase-4/brightpeak.db`. `phase-4/backend/build-db.js` rebuilds it from `phase-4/db/schema.sql` + `phase-4/db/seed.sql` and links `phase-3/db/brightpeak.db` to the same physical database.

### 1. Build the database

```bash
cd phase-4/backend
npm install
npm run db:build
```

### 2. Start the Express frontend/auth server

```bash
cd phase-4/backend
npm start
```

Open `http://localhost:3000`.

### 3. Start the FastAPI / Phase-3 graph server in a second terminal

```bash
cd phase-4/backend
py -m uvicorn main:app --reload --port 8000
```

The Department Head Faculty Hiring page now binds its controls before API loading, so a temporary FastAPI outage no longer makes the **Post New Job** button dead. The page shows a real service-unavailable state instead.

## Expanded development dataset

The seed now contains:

- 50 students
- 15 instructors
- 2 advisors
- 6 department heads
- 16 courses
- 147 enrollments
- 74 assignments
- 261 grades
- 147 attendance records
- 48 course materials
- 12 faculty job postings (2 per department)
- 60 candidate records (10 per department)
- 60 candidate AI-score records
- 12 shortlist records + 24 shortlist entries
- 12 interview records
- 12 hiring decision records
- 60 upload-ready CV `.txt` files under `phase-3/documents/documents_hiring/cvs/`

All generated records are synthetic development data; they are not real people or production applicants.
