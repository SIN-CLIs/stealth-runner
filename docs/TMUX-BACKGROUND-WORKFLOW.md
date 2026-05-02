# TMUX Background Workflow – NEVER BLOCK THE MAIN SESSION

## Problem

`bash` commands like `screen-follow record`, long-running survey loops, etc. block the
main opencode session. The agent cannot proceed with other actions while these commands
are running.

## Solution: tmux for ALL long-running/blocking commands

### Pattern: `interactive_bash` (never `bash` for blocking commands)

```python
# NEVER DO THIS (blocks agent):
bash(command="screen-follow record --video --output /tmp/file.mp4 &")

# ALWAYS USE TMUX (non-blocking):
interactive_bash(tmux_command="new-session -d -s mytask -c /path")
interactive_bash(tmux_command='send-keys -t mytask "screen-follow record --video" Enter')
```

### Complete Multi-Pane Workflow Template

```bash
# 1. Create a detached tmux session
tmux new-session -d -s heypiggy-survey -c ~/dev/stealth-runner

# 2. Split into panes for parallel work
tmux split-window -h -t heypiggy-survey:main.0 -c ~/dev/stealth-runner
tmux split-window -v -t heypiggy-survey:main.0 -c ~/dev/stealth-runner

# 3. Send commands to panes WITHOUT blocking
# Pane 0: Screen recording
tmux_command='send-keys -t heypiggy-survey:main.0 "screen-follow record --video --output /tmp/heypiggy_session.mp4" Enter'
# Pane 1: Survey automation loop
tmux_command='send-keys -t heypiggy-survey:main.1 "python3 runner/live_omni_monitor.py" Enter'
# Pane 2: Log monitoring
tmux_command='send-keys -t heypiggy-survey:main.2 "tail -f /tmp/survey_run.log" Enter'
```

### Reading Logs from tmux (Non-Blocking)

```bash
# Read last 50 lines from any pane
bash(description="Read survey pane output", command="tmux capture-pane -t heypiggy-survey:main.1 -p -S -50")
```

### Stopping tmux Session

```bash
bash(description="Kill session", command="tmux kill-session -t heypiggy-survey")
```

## Why This Works

- `tmux new-session -d` creates in **detached** mode → no blocking
- `send-keys ... Enter` sends commands to run inside tmux → no blocking
- `capture-pane -p` reads output on demand → non-blocking
- Multiple panes allow parallel execution → screen recording + survey + logs simultaneously

## SOTA Web Research (2026)

### OpenCode Issue #6929: tmux-based subagent spawning

- Config: `{ "subagent": { "spawn": "tmux" } }`
- Agents spawn in visible tmux panes, debuggable, persistent
- Status: Feature Request (not yet merged)

### Oh My OpenCode: Background Agents

- `task(run_in_background=true)` with automatic tmux visualization
- Full config:
  ```json
  {
    "tmux": {
      "enabled": true,
      "layout": "main-vertical",
      "main_pane_size": 60,
      "agent_pane_min_width": 40
    }
  }
  ```
- Status: ALREADY IMPLEMENTED

### Claude Code: Multi-Agent tmux Pattern

- `tmux new-session -d -s agent-name "claude -p 'task'"`
- `tmux capture-pane -t session -p` for log reading
- Key: `-d` flag = detached, no blocking

### OpenCode Issue #20849: Plugin-based orchestration

- `promptAsync` + SSE for fire-and-forget without upstream changes
- Uses existing session APIs, no tmux needed

## Our Current Setup (call_omo_agent is BROKEN)

Since `call_omo_agent` tool fails with 30min timeout on ALL 9 attempts,
we use `interactive_bash` (tmux) as the primary background execution method.

### Current Multi-Pane Layout

```
┌─────────────────────┬──────────────────────────┐
│ PANE 0              │ PANE 1                   │
│ screen-follow       │ Survey Automation        │
│ Recording           │ (awaiting login)         │
├─────────────────────┴──────────────────────────┤
│ PANE 2                                         │
│ Log Monitor: tail -f /tmp/survey_run.log        │
└────────────────────────────────────────────────┘
```

### Key Rules

| ❌ NEVER DO                    | ✅ ALWAYS DO                             |
| ------------------------------ | ---------------------------------------- |
| `bash("command &")`            | `interactive_bash("new-session -d ...")` |
| `bash("long_running_command")` | Start in tmux pane, check logs later     |
| `screen-follow` via bash       | `screen-follow` via tmux pane            |
| `sleep && check` for output    | `tmux capture-pane -p -S -50`            |

## OpenCode Integration

The `interactive_bash` tool is specifically designed for tmux commands.
Use it with the `tmux_command` parameter (NOT `command`).

```python
# Non-blocking command execution
interactive_bash(tmux_command='send-keys -t session:window.pane "command" Enter')

# Non-blocking log reading
bash(description="Read logs", command="tmux capture-pane -t session:window.pane -p -S -20")
```
