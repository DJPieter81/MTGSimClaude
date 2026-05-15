---
title: doomsday — Cabal Therapy + per-matchup pile architecture
status: proposed
date: 2026-05-09
phase: Phase 6 of B+ rubric lift
supersedes: null
---

# doomsday — Cabal Therapy + per-matchup pile architecture

## 1. Problem statement & current ceiling

Three audit rounds (PRs #111, #115, #117) only moved Doomsday-vs-Burn from 8 % → 10 % WR; the deck has hit a ceiling because the sim cannot model the two mechanics that real Doomsday lists rely on to win disrupted matchups.

## 2. Cabal Therapy mechanic gap

The engine has no representation of "look at opponent's hand (or guess via priors) and name a card to strip"; both the choose-name decision and the flashback line that fuels a second strip are absent.

## 3. Per-matchup pile architecture

Real Doomsday stacks a different five-card pile against Burn (lifegain insurance), Control (counter-protection), and Aggro (race speed); the sim stacks one generic pile that loses to all three.

## 4. Proposed `PileBuilder` abstraction

A pile-selection function takes `(player, opponent, gs, matchup_category)` and returns an ordered `Pile` dataclass (five tagged slots, no card-name strings) sourced from per-matchup tag templates declared on `DECK_META['doomsday']['piles']`.

## 5. Therapy resolver design (consults BHI)

The Therapy resolver calls `bhi.opponent_known_threats(gs, tags)` to pick the highest-EV tag to name, falls back to the deck-registry's prior over the opponent archetype when BHI is empty, and emits a `log_combo_decision(phase='interaction', chosen='therapy <tag>', reason=…)` line.

## 6. Engine touch-points & blast radius

Three files touched: `decks/doomsday.py` (call sites for `PileBuilder` + Therapy resolver), `combo_engine.py` (host the new `PileBuilder` + `therapy_name_target` pure functions), and a read-only consumer of `bhi.py`; `engine.py` is not modified.

## 7. Migration / rollout plan

Land behind a `DECK_META['doomsday']['use_pile_builder']` feature flag, A/B-sweep 200 games per matchup against the current single-pile path, and revert the flag if Doomsday-vs-Burn fails to clear 18 % WR or any other matchup regresses by ≥ 3 %.

## 8. Open questions & deferred work

Flashback Therapy timing (graveyard sacrifice priority), Lurrus companion pile interactions, sideboard pile templates (G2/G3), and whether `PileBuilder` should generalise to other tutor-pile decks (Ad Nauseam, future Painter pile lines) are all out of scope for this design.
