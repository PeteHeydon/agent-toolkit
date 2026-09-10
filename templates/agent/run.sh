#!/usr/bin/env bash
# Run this agent.
#
# The `cd` is the whole point. Claude Code loads CLAUDE.md and
# .claude/settings.json from the directory it starts in, so running from
# anywhere else gives you a plain session that has never heard of this agent.
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
exec claude "$@"
