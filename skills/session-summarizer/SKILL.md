---
name: session-summarizer
description: Summarizes current session work and generates structured markdown document. Invoke when user asks to summarize session, document work, or at session end.
---

# Session Summarizer

This skill summarizes the current conversation session and generates a structured markdown document in the project root directory.

## Purpose

- Capture all work completed during the current session
- Document code changes, file modifications, and key decisions
- Create a persistent record of session activities
- Generate a well-organized markdown summary

## When to Use

Invoke this skill when:
- User explicitly asks to "summarize the session" or "document what we did"
- User requests to generate a summary report
- At the end of a productive session
- User wants to track progress or create session notes

## Output Structure

The generated markdown document includes:

### 1. Session Metadata
- Date and time
- Session duration (if available)
- Project context

### 2. Work Summary
- Main tasks completed
- Files created or modified
- Key code changes

### 3. Technical Details
- Commands executed
- Dependencies added
- Configuration changes

### 4. Decisions Made
- Important architectural decisions
- Design choices
- Trade-offs considered

### 5. Next Steps
- Pending tasks
- Future improvements
- Follow-up actions

## Usage Example

When the user says:
- "Can you summarize what we worked on?"
- "Generate a session report"
- "Document today's work"
- "Create a summary of this session"

This skill will:
1. Review the conversation history
2. Extract key activities and changes
3. Generate a structured markdown file at the project root
4. Provide a brief overview of the summary

## File Location

The summary document is created at: `{project_root}/session-summary-{YYYY-MM-DD}.md`

Multiple sessions on the same day will be numbered sequentially (e.g., `session-summary-2026-03-17-1.md`, `session-summary-2026-03-17-2.md`).

## Implementation Notes

### Review Process

1. **Scan conversation history** - Look for:
   - User requests and tasks
   - Files that were read, written, or modified
   - Commands that were executed
   - Errors encountered and resolved
   - Key decisions made

2. **Categorize activities** - Group into:
   - Bug fixes
   - Feature additions
   - Refactoring
   - Configuration changes
   - Documentation updates

3. **Extract key information** - Identify:
   - File paths modified
   - Function/class names changed
   - Important code patterns introduced
   - Dependencies added or removed

### Markdown Template

Use this structure for the generated document:

```markdown
# Session Summary - {YYYY-MM-DD}

## Overview
- **Project**: {project_name}
- **Date**: {YYYY-MM-DD HH:MM}
- **Duration**: {if available}

## Tasks Completed

### 1. {Task Name}
- Description of what was done
- Files modified: `path/to/file.py`
- Key changes: Brief description

### 2. {Task Name}
...

## Files Modified

| File | Changes |
|------|---------|
| `path/to/file1.py` | Added function X, refactored Y |
| `path/to/file2.ts` | Created new component |

## Technical Details

### Commands Executed
```bash
# List significant commands
command1
command2
```

### Dependencies
- Added: `package-name`
- Updated: `other-package`

## Decisions Made

1. **Decision**: What was decided
   - **Rationale**: Why this approach was chosen
   - **Alternatives**: Other options considered

## Next Steps

- [ ] Pending task 1
- [ ] Pending task 2
- [ ] Future improvement

## Notes

Any additional observations or important context for future sessions.
```

## Best Practices

1. **Be concise but complete** - Capture essential information without excessive detail
2. **Use relative paths** - Make file references portable
3. **Highlight breaking changes** - Clearly mark any incompatible modifications
4. **Track unresolved issues** - Note any problems that need future attention
5. **Include context** - Explain why decisions were made, not just what was done
