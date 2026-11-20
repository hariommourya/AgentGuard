# AgentGuard

A local hackathon prototype for reviewing AI agent tool calls. One trusted task authorizes reading a synthetic inbox and displaying a summary. Every other proposed tool call is held by the independent policy function.

## Start

Use Python 3.11 or later. Extract the ZIP, open a terminal in the folder containing app.py, and run:

    python app.py

Open http://127.0.0.1:8765 and click **Run comparison**. On Windows, `py app.py` also works. The offline demo uses only the Python standard library. Press Ctrl+C to stop.

## A one-minute walkthrough

1. Select **Forwarding request** and run the comparison. Open M03 to see the email, its origin and its classifier result.
2. Read the authorized task aloud. Both lanes receive the same scripted proposal. The replay records one simulated outbound event. AgentGuard holds that proposal and still displays the inbox summary.
3. Click **Dismiss held action**. The audit trail retains both the hold and the reviewer's denial. Recent runs reopen from SQLite after restart.
4. Select **Indirect sharing request**. The keyword detector misses it. The action gate still holds the proposed forward because the task grants read-only access.
5. Select **Ordinary inbox** to show the normal path.

## Gemini mode

Set GEMINI_API_KEY in your local environment before launching. The summary engine selector then offers Gemini API. Only selecting that engine sends the three synthetic emails and the task to Google's generateContent endpoint. GEMINI_MODEL overrides the default model identifier gemini-2.5-flash if your account uses another model. Keep credentials out of the project files. API failures produce a visible error. Select Offline fixture to continue locally.

## How the implementation works

- **Trust tagging** is assigned at ingestion. The fixed task comes from the console and each mock email has a server-assigned ID. Email text cannot set its authority.
- **Instruction isolation** puts Gemini's system instruction in a separate API field and wraps email records as data. The summarizer has no tools. Model output is escaped for display.
- **Action gate** evaluates a tool and trusted source against the fixed summary task before guarded dispatch. The classifier supplies evidence only. Pending actions can be dismissed. Expanding permissions would require a separate authorization workflow.
- **Audit** records the run and its decisions in one SQLite transaction in audit.sqlite3. The local database is editable by its owner.
- **Scope** is one inbox task. The replay uses fixture-defined proposals so stage results are reproducible. Counts are mock events. There is no email integration or live attack generation. Gemini generates summary text only. The offline summary is extractive. A real deployment would require authenticated users, argument-level capabilities, complete mediation across integrations and protected audit storage.

## Files and verification

app.py serves the console. guard.py implements the fixtures, summarizers, dispatcher, policy and storage. style.css controls the layout. Run `python -m unittest -v` to check all three fixtures, unknown actions and the browser submission/review flow against a temporary database.

