import { tool } from "@opencode-ai/plugin"

export const login = tool({
  description: "Google OAuth Login für Heypiggy (6-Step CUA Flow)",
  args: {},
  async execute(args, ctx) {
    const proc = Bun.spawn([
      "python3", "-c",
      "from cli.modules.auto_google_login import execute; import json; print(json.dumps(execute()))"
    ], {
      cwd: ctx.worktree,
      stdout: "pipe",
      stderr: "pipe"
    })
    const out = await new Response(proc.stdout).text()
    try {
      const result = JSON.parse(out)
      if (result.status === "ok") {
        return `✅ Login erfolgreich — PID=${result.pid}, WID=${result.wid}`
      }
      return `❌ Login fehlgeschlagen: ${result.reason || "unbekannt"}`
    } catch {
      return out || "Login ausgeführt (kein JSON-Ergebnis)"
    }
  }
})

export const balance = tool({
  description: "Heypiggy-Guthaben prüfen",
  args: {},
  async execute(args, ctx) {
    const proc = Bun.spawn(["python3", "survey-cli/survey.py", "balance"], {
      cwd: ctx.worktree,
      stdout: "pipe",
      stderr: "pipe"
    })
    const out = await new Response(proc.stdout).text()
    return out || "Balance geprüft"
  }
})

export const snapshot = tool({
  description: "Compact Snapshot einer Survey-Seite generieren",
  args: {
    wsUrl: tool.schema.string().describe("CDP WebSocket URL des Tabs")
  },
  async execute(args, ctx) {
    const proc = Bun.spawn([
      "python3", "-c",
      `from tools.tool_snapshot import snapshot; import json; print(json.dumps(snapshot("${args.wsUrl}")))`
    ], {
      cwd: ctx.worktree,
      stdout: "pipe",
      stderr: "pipe"
    })
    const out = await new Response(proc.stdout).text()
    return out || "Snapshot erstellt"
  }
})
