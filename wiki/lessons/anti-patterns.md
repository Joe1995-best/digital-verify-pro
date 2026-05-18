# Lessons Learned in Digital Verification

## Known Anti-Patterns

### 1. Scoreboard with no timing check
Don't just compare data — verify it arrived at the right time.

### 2. Missing X-propagation checks
Always add `$isunknown` assertions on critical control signals.

### 3. Coverage on wrong abstraction level
Cover transactions, not pin-level toggles for functional coverage.

### 4. Register model address mismatches
Always cross-check: spec → RTL → register model. Three-way consistency.

### 5. Unconstrained random tests
Without proper constraints, random tests hit <5% of state space.
