
p = "C:/prop-frim-bot/frontend/app/ClientDashboard.tsx"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

# Replace emoji-based nav items with clean text labels
old_nav = """  { id: "dashboard", label: "Dashboard", icon: "\U0001f4ca" },
  { id: "signals", label: "Signals", icon: "\U0001f4e1" },
  { id: "charts", label: "Charts", icon: "\U0001f4c8" },
  { id: "positions", label: "Positions", icon: "\U0001f4bc" },
  { id: "analytics", label: "Analytics", icon: "\U0001f4cb" },
  { id: "risk", label: "Risk Center", icon: "\U0001f6e1" },
  { id: "telemetry", label: "Telemetry", icon: "\u26a1" },
  { id: "ai", label: "AI Center", icon: "\U0001f9e0" },
  { id: "market", label: "Market", icon: "\U0001f30d" },
  { id: "journal", label: "Journal", icon: "\U0001f4d3" },
  { id: "settings", label: "Settings", icon: "\u2699" },"""

new_nav = """  { id: "dashboard", label: "Dashboard", icon: "DS" },
  { id: "signals", label: "Signals", icon: "SG" },
  { id: "charts", label: "Charts", icon: "CH" },
  { id: "positions", label: "Positions", icon: "PO" },
  { id: "analytics", label: "Analytics", icon: "AN" },
  { id: "risk", label: "Risk Center", icon: "RK" },
  { id: "telemetry", label: "Telemetry", icon: "TL" },
  { id: "ai", label: "AI Center", icon: "AI" },
  { id: "market", label: "Market", icon: "MK" },
  { id: "journal", label: "Journal", icon: "JN" },
  { id: "settings", label: "Settings", icon: "CF" },"""

if old_nav in c:
    c = c.replace(old_nav, new_nav)
    print("FIX 1: Nav emojis replaced with clean labels")
else:
    print("FIX 1: Old nav pattern not found - checking...")
    idx = c.find('"dashboard"')
    if idx > 0:
        print(c[idx:idx+200])

# Replace emoji stat cards with clean badges
old_tabs = """{ id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "signals", label: "Signals", icon: "📡" },
  { id: "charts", label: "Charts", icon: "📈" },
  { id: "positions", label: "Positions", icon: "💼" },
  { id: "analytics", label: "Analytics", icon: "📋" },
  { id: "risk", label: "Risk Center", icon: "🛡️" },
  { id: "telemetry", label: "Telemetry", icon: "⚡" },
  { id: "ai", label: "AI Center", icon: "🧠" },
  { id: "market", label: "Market", icon: "🌍" },
  { id: "journal", label: "Journal", icon: "📓" },
  { id: "settings", label: "Settings", icon: "⚙️" },"""

new_tabs = """{ id: "dashboard", label: "Dashboard", icon: "DS" },
  { id: "signals", label: "Signals", icon: "SG" },
  { id: "charts", label: "Charts", icon: "CH" },
  { id: "positions", label: "Positions", icon: "PO" },
  { id: "analytics", label: "Analytics", icon: "AN" },
  { id: "risk", label: "Risk Center", icon: "RK" },
  { id: "telemetry", label: "Telemetry", icon: "TL" },
  { id: "ai", label: "AI Center", icon: "AI" },
  { id: "market", label: "Market", icon: "MK" },
  { id: "journal", label: "Journal", icon: "JN" },
  { id: "settings", label: "Settings", icon: "CF" },"""

if old_tabs in c:
    c = c.replace(old_tabs, new_tabs)
    print("FIX 2: Tab emojis replaced")
else:
    print("FIX 2: Old tabs pattern not found - checking...")
    idx = c.find("NAV_ITEMS")
    if idx > 0:
        print(c[idx:idx+400])
    # Also check for the NAV_ITEMS or pages array
    for name in ["NAV_ITEMS", "pages"]:
        idx = c.find(name)
        if idx > 0:
            print(f"Found '{name}' at {idx}:")
            print(c[idx:idx+300])

# Remove the emoji from the header icon
old_header = 'className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-[10px] font-black text-white">T</div>'
new_header = 'className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-[10px] font-black text-white font-mono">T</div>'
if old_header in c:
    c = c.replace(old_header, new_header)
    print("FIX 3: Header icon cleaned")

with open(p, "w", encoding="utf-8") as f:
    f.write(c)
print("\nUI fixes applied")
