import { tool } from "@opencode-ai/plugin"

export const launch = tool({
  description: "Chrome mit korrekten Flags starten (--force-renderer-accessibility + --remote-allow-origins=\"*\")",
  args: {
    port: tool.schema.number().optional().describe("CDP Port (default: 9999)"),
    url: tool.schema.string().optional().describe("URL zum Öffnen")
  },
  async execute(args, ctx) {
    const port = args.port || 9999
    const url = args.url || "https://www.heypiggy.com/?page=dashboard"
    const profile = `/tmp/heypiggy-new-${Math.floor(Date.now() / 1000)}`
    const cmd = [
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      `--remote-debugging-port=${port}`,
      `--remote-allow-origins=*`,
      "--force-renderer-accessibility",
      "--no-first-run",
      "--no-default-browser-check",
      `--user-data-dir=${profile}`,
      url
    ]
    Bun.spawn(cmd, { stdio: ["ignore", "ignore", "ignore"] })
    await Bun.sleep(8000)
    
    // Verify Chrome is running
    const check = Bun.spawn(["curl", "-s", `http://127.0.0.1:${port}/json/version`], {
      stdout: "pipe"
    })
    const result = await new Response(check.stdout).text()
    return result 
      ? `Chrome gestartet auf Port ${port}, Profile: ${profile}` 
      : `Chrome start fehlgeschlagen auf Port ${port}`
  }
})

export const kill = tool({
  description: "NUR Bot-Chrome beenden (profile=/tmp/heypiggy-new-*). NIE user Chrome!",
  args: {},
  async execute(args, ctx) {
    const ps = Bun.spawn(["ps", "aux"], { stdout: "pipe" })
    const psOut = await new Response(ps.stdout).text()
    const killed = []
    for (const line of psOut.split("\n")) {
      if (line.includes("heypiggy-new") && line.includes("Google Chrome")) {
        const parts = line.trim().split(/\s+/)
        if (parts.length > 1) {
          const pid = parseInt(parts[1])
          if (!isNaN(pid)) {
            try { process.kill(pid, "SIGTERM"); killed.push(pid) } catch {}
          }
        }
      }
    }
    return killed.length > 0 
      ? `${killed.length} Bot-Chrome beendet: PIDs ${killed.join(", ")}`
      : "Keine Bot-Chrome Prozesse gefunden"
  }
})

export const check = tool({
  description: "Prüft ob Chrome auf Port 9999 läuft und CDP bereit ist",
  args: {
    port: tool.schema.number().optional().describe("CDP Port (default: 9999)")
  },
  async execute(args, ctx) {
    const port = args.port || 9999
    const cdp = Bun.spawn(["curl", "-s", `http://127.0.0.1:${port}/json`], { stdout: "pipe" })
    const tabs = await new Response(cdp.stdout).text()
    try {
      const parsed = JSON.parse(tabs)
      return `Chrome läuft auf Port ${port}: ${parsed.length} Tabs offen`
    } catch {
      return `Chrome NICHT erreichbar auf Port ${port}`
    }
  }
})
