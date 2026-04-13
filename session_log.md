# Architecture Session — A + B + C (2026-04-13)

## Phase A: Response Function Unification
- Unified `_p1_respond_on_opp_turn` + `_p2_respond_on_pro_turn` → `_respond_on_opponent_turn`
- Added `_force_of_vigor_generic(responder, active, ...)` (symmetric FoV)
- Interactions: STP, Fatal Push, Snuff Out, Bolt/Heat, Flash Bowmasters, FoV, Wasteland
- Old functions kept as deprecated wrappers; sim.py call site updated
- Tests: 147/0
- Symmetry (n=100): dimir/dimir_b 114%, ur_delver/burn 94%, bug/storm 100%
