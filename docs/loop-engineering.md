# Local Loop Engineering

PM manages scope and acceptance; the local DevOps agent operates the shared
`phuongphh/fleet-engineering` runner. Claude is the persisted default, with owner
requests for a task override or a new default. Local task branches are excluded
from legacy auto-PR so the shared runner is the only PR publisher.

The new Product CI runs existing engine and gateway unit suites in disposable
GitHub runners, without production credentials. It does not claim live database,
RAG/provider or end-to-end Telegram coverage, or verification of current tax law.
Failing tests or collection errors block readiness; do not skip them to activate
the coding profile. Integration acceptance is required for work that needs it.

Dev is on the owner's Mac, operated by local DevOps. Production stays on VPS
under the Production DevOps agent through the existing approved prod release
path. This PR does not deploy or change business/tax rules.
