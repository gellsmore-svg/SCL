CONTEXT
A maintainer hands the framework a named process. The model stays the source of truth.

PROCESS CairnProcess (INPUT: process; OUTPUT: report)
  1. <submit-process> Hand over the named process. [HUMAN, GATED]
     BINDS: requirement-cairn-export
  2. <report-bindings> Report which requirements the steps name. [CODE, DETERMINISTIC]
     BINDS: requirement-cairn-bind, requirement-cairn-propose
