# Skip Existing Date Save Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skip the daily SQLite import when the latest CSV date already exists in the database.

**Architecture:** Keep the change inside `save.py` by adding one database lookup for a target date and one orchestration helper that decides whether to scan files. Reuse the existing date-resolution logic so the daily workflow behavior stays simple and predictable.

**Tech Stack:** Python 3, `sqlite3`, `unittest`

---

### Task 1: Add failing tests for existing-date skip logic

**Files:**
- Modify: `tests/test_save.py`
- Test: `tests/test_save.py`

- [ ] **Step 1: Write the failing test**

```python
def test_should_skip_scan_when_latest_date_already_exists(self):
    database = FakeDatabase(existing_dates={"2026-03-27"})
    self.assertTrue(should_skip_scan(database, "2026-03-27", scan_all=False))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_save.py`
Expected: FAIL with `ImportError` or `AttributeError` for the new helper.

- [ ] **Step 3: Write minimal implementation**

```python
def should_skip_scan(database, date_prefix, scan_all=False):
    if scan_all or not date_prefix:
        return False
    return database.has_records_for_date(date_prefix)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_save.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_save.py save.py
git commit -m "fix: skip duplicate daily sqlite imports"
```

### Task 2: Integrate database date check into save.py main flow

**Files:**
- Modify: `save.py`
- Test: `tests/test_save.py`

- [ ] **Step 1: Write the failing test**

```python
def test_should_not_skip_scan_when_date_missing(self):
    database = FakeDatabase(existing_dates=set())
    self.assertFalse(should_skip_scan(database, "2026-03-27", scan_all=False))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_save.py`
Expected: FAIL because the helper or database method is incomplete.

- [ ] **Step 3: Write minimal implementation**

```python
class SQLiteDatabase(BaseDatabase):
    def has_records_for_date(self, date_str):
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM holdings WHERE date = ? LIMIT 1",
                (date_str,),
            ).fetchone()
        return row is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_save.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_save.py save.py
git commit -m "fix: avoid rewriting unchanged ARK daily data"
```
