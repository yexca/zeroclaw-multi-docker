# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat work.
# Add tasks below when you want {agent} to check something periodically.
#
# Official heartbeat limitations:
# - HEARTBEAT.md is read by ZeroClaw's heartbeat worker, not injected into normal chat prompts.
# - The official worker does not automatically know who to message unless heartbeat delivery is configured.
# - With two_phase enabled, the model may conservatively skip routine or non-time-sensitive tasks.
# - Empty files, comments, and lines that do not start with "- " are ignored.
#
# Examples:
# - Check my email for important messages
# - Review my calendar for upcoming events
# - Run `git status` on my active projects
