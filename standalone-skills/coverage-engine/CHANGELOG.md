# Changelog

## [2.0.0] - 2026-05-19
### Added
- Standalone skill package with SKILL.md, requirements.txt, run.py
- Pure Python VCD parser (no vdump.py dependency)
- Full-signal per-bit toggle analysis
- Activity level classification (NONE/LOW/MEDIUM/HIGH/VERY_HIGH)
- Coverage gap detection with severity ranking
- Zero stuck-signal verification

### Changed
- Migrated from engines/ to standalone-skills/coverage-engine/

## [1.0.0] - 2026-04-22
### Added
- Initial VCD toggle coverage analysis
