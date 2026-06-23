# PROACTIVE.md

# Optional zeroclaw_multi_docker proactive service notes.
#
# This file is not read automatically by official ZeroClaw.
# It is a project-level convention for an optional proactive service that can
# invoke each agent on its own schedule and let the agent decide whether there
# is a useful reason to contact the user.
#
# Why this exists:
# - Official HEARTBEAT.md is task-oriented and conservative by default.
# - Official heartbeat delivery needs explicit target/to configuration before it can message the user.
# - Official two-phase heartbeat may skip routine checks.
# - A per-agent proactive service can give each agent its own rhythm and outbound judgment.
#
# Suggested behavior for a proactive invocation:
# - Review current memory, HEARTBEAT.md, and any recent context made available by the service.
# - Contact the user only when there is a concrete, timely, and useful reason.
# - Keep outbound messages short and avoid interrupting for low-value updates.
# - If there is no useful reason to contact the user, respond with "skip".
#
# This file becomes effective only when:
# - the optional proactive service reads it, or
# - an official injected file such as AGENTS.md explicitly tells the agent to read it.
