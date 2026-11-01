# Quickstart: Teacher Monitoring Dashboard

How to run the feature locally and do the manual integration checks the constitution requires (Principle II).

## 1. Setup

1. Add a teacher to `src/server/authorization/authorized_users.json`:

   ```json
   {
     "authorized_emails": ["researcher@example.org"],
     "teacher_emails": ["teacher@example.org"]
   }
   ```

   With `ENABLE_GOOGLE_AUTH=false`, the bypass login has both roles, which is enough for local checks.

2. Optional `.env` settings: `DASHBOARD_ANALYSIS_MODEL=gpt-4.1` and `DASHBOARD_DB_PATH`. `OPENAI_API_KEY` is already required.

3. Start the stack:

   ```bash
   docker compose up --build
   ```

   `src/server/data/` is created and mounted, and `dashboard.db` is created on first start.

## 2. Class setup (US1, US2)

1. Open `http://localhost:5173/teacher`. You should see an empty class with an "Add your first student" prompt.
2. Add the students "Maya", "Leo" and "Ana". Each should get a 6-character code and a "Copy link" button.

## 3. Student session (US2, US4, US5)

1. Open Maya's link (`/kiva?code=…`) in a **private window**, signed in with a non-teacher account.
2. Choose "Child vocabulary training", a book and a chapter. The form should show "Student code: K7MPQ4 — Hi, Maya!".
3. Run a full session:
   - claim to know and correctly explain 1 word;
   - finish all steps for a second word;
   - give a wrong answer to the "use it in a sentence" step for a third.
4. End the session. Within 2 minutes, `/teacher/students/<maya>` should show one session with detail "Ready".
5. Open the session and check:
   - **Already knew it**: one word.
   - **Taught**: three words.
   - The third word shows *Own sentence: tried, not yet*, and its review matches what KIVA said.
   - The summary is 120 words or fewer, matches the outcomes, and contains no quotes from the student.
   - Nowhere on the page is there a transcript, audio or the student's raw words.

## 4. Edge checks

| Check | Expected |
|---|---|
| Type an invalid code in the settings form | A friendly "We didn't recognize that code" message, and the session is not started |
| Regenerate Maya's code, then reuse the old link | Rejected. Maya's past sessions are still listed. |
| Leo starts a session and closes the tab after warm-up | The session is labeled "Ended early" with no words and is excluded from "needs attention" |
| Disconnect `OPENAI_API_KEY` (bad key) for one session | Detail shows "Detailed results not available — Retry". Retry works once the key is restored. |
| Signed in as a teacher-only account, open `/sessions` | Hidden in navigation. The API returns 403. |
| A second teacher account | Sees only their own class. Hitting the first teacher's student URL returns "Not found". |
| Set Maya's reading level to Grade 6 by hand | Shows "Grade 6 (set by teacher)" with the estimate alongside. Clearing it restores the estimate. |
| Resize to tablet width (768 px) | Class table and session detail remain usable with no horizontal page scroll |

## 5. Regression (constitution happy path)

Start any non-KIVA activity **without** a student code. It should behave exactly as before: the session is saved under the random `user_id` and doesn't appear on any dashboard.

## 6. Automated checks

```bash
cd src/server && python -m unittest discover -s tests
```

This covers `metrics.py` (reading level, status, completion) and the analysis validators.

```bash
pre-commit run --all-files
```
