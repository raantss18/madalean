import Lake
open Lake DSL

package «parity-notes» where

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git" @ "v4.9.0"

@[default_target]
lean_lib ParityNotes where
