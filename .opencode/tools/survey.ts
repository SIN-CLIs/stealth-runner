import { tool } from "@opencode-ai/plugin"

export const run = tool({
  description: "NEMO Survey Loop starten — führt automatisch Umfragen aus",
  args: {
    max: tool.schema.number().optional().describe("Maximale Anzahl Surveys (default: 10)"),
    mode: tool.schema.enum(["nim", "legacy", "loop"]).optional().describe("Ausführungs-Modus")
  },
  async execute(args, ctx) {
    const max = args.max || 10
    const mode = args.mode || "loop"
    const proc = Bun.spawn(["python3", "run_survey.py", "--mode", mode, "--max", String(max)], {
      cwd: ctx.worktree,
      stdout: "pipe",
      stderr: "pipe"
    })
    const out = await new Response(proc.stdout).text()
    return out || "Survey loop gestartet"
  }
})

export const scan = tool({
  description: "Heypiggy Dashboard nach Surveys scannen",
  args: {},
  async execute(args, ctx) {
    const proc = Bun.spawn(["python3", "run_survey.py", "--mode", "scan"], {
      cwd: ctx.worktree,
      stdout: "pipe",
      stderr: "pipe"
    })
    const out = await new Response(proc.stdout).text()
    return out || "Scan abgeschlossen"
  }
})

export const status = tool({
  description: "Survey-Daemon Status + Balance prüfen",
  args: {},
  async execute(args, ctx) {
    const proc = Bun.spawn(["python3", "survey-cli/survey.py", "status"], {
      cwd: ctx.worktree,
      stdout: "pipe",
      stderr: "pipe"
    })
    const out = await new Response(proc.stdout).text()
    return out || "Status geprüft"
  }
})
