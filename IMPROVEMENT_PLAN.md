# Cogitator Improvement Plan

Generated from codebase analysis. Organized by severity and category.

---

## CRITICAL BUGS (Fix Immediately)

### 1. `retention_adjustment()` Always Returns 0.0
**File:** `workflows/learning_engine.py:596-645`
**Problem:** `load_retention_history()` stores `word_count`, `has_hook`, `has_cta`, `performance` but `retention_adjustment()` tries to match on `has_dialogue`, `has_excitement`, `has_laughter`, `duration` — keys that are never stored. The match always fails, so the function always returns 0.0.
**Impact:** The entire YouTube-based retention learning system is non-functional.
**Fix:** Either store the correct keys in `load_retention_history()` or update the matching logic in `retention_adjustment()` to use the keys that are actually stored.

### 2. `get_successful_scripts()` Missing `min_views` Parameter
**File:** `workflows/learning_engine.py:1052,1101`
**Problem:** Calls `get_successful_scripts(limit=100, min_views=10)` but the function only accepts `limit`. This raises `TypeError` at runtime.
**Impact:** Virality model training and performance analysis fail silently.
**Fix:** Add `min_views` parameter to `get_successful_scripts()` or remove the argument from callers.

### 3. `PIPELINE_STOP_REQUESTED` May Not Propagate
**Files:** `workflows/cogitator.py:301`, `workflows/pipeline/pipeline_runner.py:56,74,158`
**Problem:** `pipeline_runner.py` imports `PIPELINE_STOP_REQUESTED` by value from `cogitator.py`. Setting it in one module doesn't affect the other. The API stop endpoint may never be seen by the running pipeline.
**Impact:** Pipeline cannot be stopped via the API.
**Fix:** Use a shared mutable object (dict/list) or `threading.Event` instead of a module-level boolean.

---

## HIGH SEVERITY

### 4. Dual Context Managers (v1/v2) With Different Return Formats
**Files:** `workflows/context_manager.py`, `workflows/context_manager_v2.py`
**Problem:** Two parallel context manager systems coexist. `backend/main.py` imports from both. They return different data structures (v1 wraps in `context` key, v2 returns flat dict).
**Impact:** Data inconsistency between pipeline and API.
**Fix:** Consolidate into one context manager. Migrate v1 callers to v2 or vice versa.

### 5. `_cs_load_context()` Duplicated With Divergent Implementations
**Files:** `workflows/context_extractor.py:231`, `workflows/cogitator.py:1933`
**Problem:** Two separate implementations of the same function. The `cogitator.py` version includes alias loading from `verified_context.json`; the `context_extractor.py` version does not.
**Impact:** Alias resolution silently fails when called from `context_extractor.py`.
**Fix:** Extract to a shared utility function.

### 6. WebSocket Has No Authentication
**File:** `backend/main.py:1814`
**Problem:** The `/ws` endpoint accepts connections from anyone without API key verification.
**Impact:** Any client on the network can receive real-time pipeline status and logs.
**Fix:** Add token-based authentication to the WebSocket handshake.

### 7. Race Condition on `pipeline_status` Dict
**Files:** `workflows/ws_manager.py:13-20`, `backend/main.py:337-418`
**Problem:** `pipeline_status` is a plain dict shared between background threads and the asyncio event loop with no synchronization.
**Impact:** Data corruption or crashes under concurrent access.
**Fix:** Use `threading.Lock` or `asyncio.Lock` for all accesses.

### 8. Event Loop Usage From Background Thread
**File:** `workflows/ws_manager.py:69`
**Problem:** `asyncio.get_event_loop().run_until_complete()` called from a non-main thread. In Python 3.10+ this may raise errors.
**Impact:** Log tailing may fail.
**Fix:** Use `asyncio.run_coroutine_threadsafe()` (already used elsewhere in the codebase).

---

## MEDIUM SEVERITY

### 9. `match_tiktok_to_clips()` Never Matches Against Actual Clips
**File:** `workflows/tiktok_analytics.py:510-577`
**Problem:** Queries both `clips` and `scripts` tables but only matches against `scripts`. The `local_clips` variable is fetched but never used.
**Impact:** TikTok videos cannot be matched to individual clip segments.
**Fix:** Add matching logic for the `local_clips` query results.

### 10. 15 Bare `except:` Clauses
**Files:** Multiple (see analysis)
**Problem:** Bare `except:` catches `SystemExit` and `KeyboardInterrupt`, making the application difficult to stop cleanly and masking real errors.
**Impact:** Difficult debugging, unclean shutdowns.
**Fix:** Replace all bare `except:` with `except Exception:`.

### 11. Hardcoded `~/Cogitator` Paths (14 Locations)
**Files:** 12 different files
**Problem:** Most modules hardcode `os.path.expanduser("~/Cogitator")` instead of using the dynamic `_find_workspace()` function from `cogitator.py`.
**Impact:** Breaks if workspace is moved or `WORKSPACE` env var is set differently.
**Fix:** Centralize workspace path resolution and import from a single source.

### 12. Orphaned Frontend Pages
**Files:** `frontend/src/pages/Metrics.tsx`, `frontend/src/pages/TikTokAnalytics.tsx`
**Problem:** These pages exist but are never imported or routed in `App.tsx`.
**Impact:** Dead code, maintenance burden.
**Fix:** Delete both files.

### 13. Dead API Functions in Frontend
**File:** `frontend/src/lib/api.ts`
**Problem:** `getLearnings()`, `getGraphSearch()`, `getGraphStats()`, `deleteGame()`, `mergeContext()` are defined but never imported by any component.
**Impact:** Dead code.
**Fix:** Remove unused exports or wire them to UI.

### 14. Dead Python Functions
**File:** `workflows/performance_database.py`
**Problem:** `get_metrics_for_video()`, `get_generation_params()`, `update_generation_param()`, `calculate_relative_performance()` are never called.
**Impact:** Dead code.
**Fix:** Remove or wire into pipeline/API.

### 15. README Documentation Errors
**File:** `README.md`
**Problems:**
- Says "6 phases" but pipeline has 7
- Wrong HTTP method for `/api/scripts/{id}/metadata` (says PUT, is GET)
- Wrong header name (`X-Goog-Api-Key` vs `X-API-Key`)
- Duplicated "Starting the Web Server" section
- Claims Zustand is used (it's not)
- Incomplete protected endpoints list
**Impact:** Misleading documentation.
**Fix:** Update README to match actual implementation.

### 16. Version Inconsistency
**Files:** `VERSION` (2.5.1), `package.json` (2.1.0), `Layout.tsx` (2.0.0), `Settings.tsx` (2.0.0)
**Problem:** Four different version strings across the project.
**Impact:** Confusing for users and developers.
**Fix:** Centralize version in one source (e.g., `VERSION` file) and read from it everywhere.

### 17. `.env` Has Invalid Hex Color
**File:** `.env:20`
**Problem:** `SRT_FONT_COLOR=FFFFF` is 5 hex characters (should be 3 or 6).
**Impact:** Subtitle rendering may fail or use fallback color.
**Fix:** Change to `FFFFFF` or `FFF`.

### 18. Unprotected API Endpoints
**File:** `backend/main.py`
**Problem:** ~30 GET endpoints have no API key verification, including `/api/scripts` (exposes all scripts), `/api/config` (exposes configuration), `/api/status` (exposes workspace info).
**Impact:** Data exposure on local network.
**Fix:** Add API key verification to sensitive GET endpoints or document the security model clearly.

---

## LOW SEVERITY

### 19. No 404 Catch-All Route
**File:** `frontend/src/App.tsx`
**Problem:** Unknown URLs show a blank page with no feedback.
**Fix:** Add `<Route path="*" element={<NotFound />} />`.

### 20. Hardcoded WebSocket Port
**File:** `frontend/src/pages/Dashboard.tsx:26`
**Problem:** `ws://${window.location.hostname}:8000/ws` hardcodes port 8000.
**Fix:** Use `window.location.port` or derive from config.

### 21. `SECURITY.md` Incomplete
**File:** `SECURITY.md:73-82`
**Problem:** Lists only 5 protected endpoints but code has 23+.
**Fix:** Update to match actual implementation.

### 22. `audio_analysis.py` Unreachable `except:` Block
**File:** `workflows/audio_analysis.py:162-165`
**Problem:** `except:` after `except Exception:` is unreachable dead code.
**Fix:** Remove the bare `except:` block.

### 23. `extract_context.py` Hardcoded Game Title
**File:** `workflows/extract_context.py:17`
**Problem:** `GAME_TITLE = "Shadow of the Tomb Raider"` is hardcoded.
**Fix:** Make it configurable or remove from repository.

### 24. Duplicate `import os` in Backend
**File:** `backend/main.py:1136`
**Problem:** `import os` re-executed inside a function body (already imported at top level).
**Fix:** Remove redundant import.

### 25. `calculate_relative_performance` Imported but Unused
**File:** `backend/main.py:1265`
**Problem:** Imported in `/api/learning/dashboard` but never called.
**Fix:** Remove unused import.

### 26. Frontend `api.ts` 403 Retry Doesn't Check Response Status
**File:** `frontend/src/lib/api.ts:58-72`
**Problem:** On 403 retry, calls `retry.json()` without checking `retry.ok` first.
**Fix:** Check `retry.ok` before parsing JSON.

### 27. `Performance.tsx` Cross-Platform Table Case-Sensitive Join
**File:** `frontend/src/pages/Performance.tsx:650`
**Problem:** Joins YouTube `content_type` with TikTok `game` using `.toLowerCase()` but casing may differ.
**Fix:** Normalize both sides before comparison.

### 28. Mempalace Only Uses v1 Context Manager
**File:** `workflows/mempalace_integration.py:20`
**Problem:** Imports only from `context_manager` (v1), ignoring v2 entity tracking.
**Fix:** Migrate to v2 or maintain compatibility.

---

## TECHNICAL DEBT

### 29. Inconsistent Import Patterns
**Problem:** Mix of bare imports (`from foo import bar`) and qualified imports (`from workflows.foo import bar`). Bare imports only work with specific CWD.
**Files:** `cogitator.py`, `context_manager_v2.py`, `performance_database.py`, `learning_engine.py`, `constants.py`
**Fix:** Standardize on qualified imports with `workflows.` prefix.

### 30. Global State Without Locks
**Files:** `cogitator.py` (PIPELINE_RUNNING, PIPELINE_STOP_REQUESTED, _SCRIPT_ID_MAP, GROQ_KEY_INDEX, GEMINI_KEY_INDEX)
**Problem:** Module-level variables modified from multiple threads without synchronization.
**Fix:** Use `threading.Lock` for all shared state.

### 31. Duplicate Log Tailing
**Files:** `backend/main.py:373-388`, `workflows/ws_manager.py:48-81`
**Problem:** Both tail the same log file from different threads, risking duplication.
**Fix:** Use a single log tailing mechanism.

### 32. `context_manager.py` Duplicate `CONTEXT_DIR` Definition
**File:** `workflows/context_manager.py:34,260`
**Problem:** `CONTEXT_DIR` defined twice with identical value.
**Fix:** Remove duplicate.

---

## Priority Order

1. **Critical bugs** (1-3): Fix immediately — they break core functionality
2. **High severity** (4-8): Fix next — they affect reliability and security
3. **Medium severity** (9-18): Fix in next sprint — they affect code quality
4. **Low severity** (19-28): Fix when convenient — minor improvements
5. **Technical debt** (29-32): Ongoing cleanup
