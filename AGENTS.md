# Project working rules

- Canonical project root is `D:\钓鱼经验机`. All project work, virtual environments, temporary files, caches, logs, screenshots and build outputs belong under this D-drive folder. The old C-drive copy is stale; do not develop there.
- User authorized development of the local fishing assistant, including separate ordinary reel and bait-reload delays, splash-only detection, and a Windows interface.
- User confirmed zoom requires holding the right mouse button, not a toggle click. Default and local zoom mode must be `hold`: hold while waiting for a bite, release before hooking and on pause/focus loss/error/exit.
- User requested two left clicks for each cast. Use a 0.15-second gap after the first release; cancel the second press on pause or focus loss. Hooking and the standalone single-click diagnostic remain one left click.
- User requested the current calibrated regions as first-run defaults: on a 2560 x 1600 client, splash (510, 311, 1651, 932), bait (2356, 1365, 110, 71), expressed as normalized coordinates. Existing local settings must not be overwritten.
- User intends an open-source tool and selected the MIT license. Keep README concise: preset-first workflow, low-reflection fishing spots, splash/bait crop requirements and basic hardware/memory guidance. Omit per-machine benchmark details from README. Keep the fuller license/use-scope explanation covering MIT terms, game-asset rights and game rules.
- User authorized publishing the tested v0.1.3 update to GitHub as an open-source tool. Repository: `https://github.com/mfoflife/delta-fishing-assistant`, branch `codex/initial-version`. The earlier testing-phase publishing pause is lifted for this release. Do not delete the repository or force-push history.
- Do not commit raw game recordings, virtual environments, local machine settings, credentials, or generated bulk frame dumps.
- Video observations are sample-specific; never present replay detection as live-game success rate or observed human intervals as proven game cooldowns.
- Use ordinary OS screen capture and input APIs. Input must stop on pause, focus loss, errors and timeout. Do not add anti-cheat bypasses.
