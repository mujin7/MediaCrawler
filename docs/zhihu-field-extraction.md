# Zhihu detail field extraction repair

The detail path logs in with Playwright, fetches the requested answer HTML through
the HTTP client, and parses `script#js-initialData` into page entities. It does not
read all visible controls from a screenshot or the rendered DOM.

Page entities use camelCase while API objects can use snake_case. The previous
mapper only read API-style `voteup_count`, `comment_count`, `created_time`, and
`updated_time`, returning default zeros or null timestamps for page entities.
Question titles are nested under `answer.question.title`; full question details
and question statistics are in `entities.questions[question_id]`.

This repair accepts both forms, preserves genuine zeros, and uses null for missing
answer counters/timestamps. It selects the requested answer by ID instead of the
first answer in a page that may also contain recommendations.

Additional output fields:

| Output | Source |
|---|---|
| `content_html` | answer `content` |
| `question_title` | matching question `title`; nested question fallback |
| `question_detail_html` | matching question `detail` |
| `question_detail` | plain text derived from question `detail` |
| `favlists_count` | `favlistsCount` / `favlists_count`; reaction `favorites` fallback |
| `like_count` | answer `likeCount` / `like_count`; reaction `statistics.likeCount` fallback |
| `thanks_count` | `thanksCount` / `thanks_count`, retained independently of likes |
| `content_need_truncated` | `contentNeedTruncated` / `content_need_truncated` |
| `question_answer_count` | question `answerCount` / `answer_count` |
| `question_comment_count` | question `commentCount` / `comment_count` |
| `question_follower_count` | question `followerCount` / `follower_count` |
| `question_visit_count` | question `visitCount` / `visit_count` |
| `question_voteup_count` | question `voteupCount` / `voteup_count` |

Question comments, answer comments, answer likes, and comment likes have separate
meanings. Do not conflate them. A question with a known empty `detail` uses empty
strings; unavailable details use null. Image links survive in the HTML fields;
the corresponding text fields do not OCR image contents or download images.

Validated against the saved HTML of the single original target (question
369788883, answer 1000001641): answer upvotes 342, comments 135, collections 22,
likes 35; question title/detail and answer timestamps are present. This validation
was offline after saving the already-open browser page. It does not claim a
second end-to-end online crawl of the patched version.

JSON/JSONL/CSV include the extended model fields. The ORM schema is updated for
**new** SQL tables and tested with a new in-memory SQLite database. Existing SQL
databases need an explicit schema migration before using this extended ORM:
`create_all()` does not add columns to existing tables. No existing SQL database
was migrated in this task. The separate task-ledger SQLite database is managed by
`collection_tasks/build_tasks.py` and is not the crawler's content database.

Run the focused regression checks:

```bash
.venv/bin/python -m pytest -q tests/test_zhihu_answer_detail.py
```
