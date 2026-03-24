# Pluggable tools folder
# Drop new tool modules here — they'll be auto-discovered if they export a TOOLS list.
# Each tool module should define:
#   TOOLS = [tool1, tool2, ...]  — list of @tool decorated functions
#   ROLES = ["builder", "qa", ...]  — which agent roles can use these tools (optional, defaults to all)
