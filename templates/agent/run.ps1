# Run this agent.
#
# The Set-Location is the whole point. Claude Code loads CLAUDE.md and
# .claude/settings.json from the directory it starts in, so running from
# anywhere else gives you a plain session that has never heard of this agent.
Set-Location -Path $PSScriptRoot
claude @args
